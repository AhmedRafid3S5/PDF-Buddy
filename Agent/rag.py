import argparse
import os
import json
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from ollama import chat
from .get_embedding_function import get_embedding_function
from Utils.search_tool import mostRevelantLink, optimise_search_query
from Utils.web_loader import read_page
from dotenv import load_dotenv

load_dotenv("configs.env")

pdf_dir_path = os.getenv("SAVE_DIR","Data")
chroma_path = os.getenv("CHROMA_PATH")


PROMPT_TEMPLATE = """
Answer the question based only on the following context and any provided images.
{image_note}
If no text context is provided, rely on the images to answer. If any text and images provided do not talk about the same subject or topic, use the current page image (Image 1) to answer query.
Use your own knowledge to answer the question if necessary
Respond in Markdown.

{context}

---

Answer the question based on the above context: {question}
"""
#might want to return a type of rich text here is possible
#see if new db instantiation here is causing overhead

def _is_context_sufficient(query: str, context: str, model: str) -> bool:
    """Ask the model whether the retrieved context is enough to answer."""
    if not context or context == "(No relevant text retrieved.)":
        return False

    prompt = f"""You have the following retrieved context and a user question.
Answer only YES or NO: Is the context sufficient to give a complete, accurate answer?

Context:
{context[:2000]}

Question: {query}
Answer:"""

    response = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response["message"]["content"].strip().upper()
    return answer.startswith("YES")


def _is_snippet_sufficient(query: str, snippet: str, model: str) -> bool:
    """Ask the model whether the search snippet is enough or full page is needed."""
    prompt = f"""You have a short web search snippet and a user question.
Answer only YES or NO: Is this snippet enough to give a complete, accurate answer?
Do NOT say YES for vague or partial snippets.

Snippet: {snippet}
Question: {query}
Answer:"""

    response = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = response["message"]["content"].strip().upper()
    return answer.startswith("YES")
    
def _build_metadata_hint(results: list[tuple]) -> str:
    sources = set()
    pages = set()
    for doc, _score in results:
        source = doc.metadata.get("source")
        page = doc.metadata.get("page")
        if source:
            sources.add(os.path.basename(source))
        if page is not None:
            pages.add(int(page) + 1)

    if not sources and not pages:
        return ""

    sources_part = ", ".join(sorted(sources)) if sources else "unknown"
    pages_part = ", ".join(str(page) for page in sorted(pages)) if pages else "unknown"
    return f"Metadata: pdf={sources_part}; pages={pages_part}"


MODEL = "gemma4:31b-cloud"

def query_rag(query_text: str, extra_images=None, fallback_images=None) -> str:
    embedding_function = get_embedding_function()
    db = Chroma(persist_directory=chroma_path, embedding_function=embedding_function)

    initial_results = db.similarity_search_with_score(query_text, k=5)
    metadata_hint = _build_metadata_hint(initial_results)
    retrieval_query = f"{query_text}\n{metadata_hint}" if metadata_hint else query_text
    results = db.similarity_search_with_score(retrieval_query, k=5)

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _ in results])
    if not context_text:
        context_text = "(No relevant text retrieved.)"

    # --- page images (your existing logic) ---
    pages_by_source: dict[str, set[int]] = {}
    for doc, _ in results:
        source = doc.metadata.get("source")
        page = doc.metadata.get("page")
        if source is None or page is None:
            continue
        pages_by_source.setdefault(source, set()).add(int(page) + 1)

    page_images: list[str] = []
    for source_path, pages in pages_by_source.items():
        sidecar_path = os.path.splitext(source_path)[0] + ".pages.json"
        if not os.path.exists(sidecar_path):
            continue
        with open(sidecar_path, "r", encoding="utf-8") as f:
            page_map = json.load(f)
        for page_num in sorted(pages):
            image = page_map.get(str(page_num))
            if image:
                page_images.append(image)

    all_images = list(extra_images or [])
    if results:
        all_images.extend(page_images)
    elif fallback_images:
        all_images.extend(fallback_images)

    # --- web search fallback ---
    web_citation: str | None = None
    web_context: str = ""

    if not _is_context_sufficient(query_text, context_text, MODEL):
        search_query = optimise_search_query(query_text, context_text)
        print(f"[Web search] Query: {search_query}")

        try:
            search_result = mostRevelantLink(search_query)
            snippet = search_result.get("snippet", "")
            url = search_result.get("link", "")
            title = search_result.get("title", url)

            print(f"[Web search] Snippet: " + snippet)

            if _is_snippet_sufficient(query_text, snippet, MODEL):
                web_context = f"Web snippet ({title}):\n{snippet}"
                web_citation = url
                print(f"[Web search] Snippet sufficient.")
            else:
                print(f"[Web search] Snippet insufficient, loading full page...")
                full_text = read_page(url, fallback_snippet=snippet, verbose=False)
                web_context = f"Web page content ({title}):\n{full_text[:4000]}"
                print(f"[Web search] Web Content: " + web_context)
                web_citation = url

        except Exception as e:
            print(f"[Web search] Failed: {e}")

    # merge contexts
    combined_context = context_text
    if web_context:
        combined_context += f"\n\n---\n\n{web_context}"

    # citation instruction appended to prompt
    citation_instruction = (
        f"\n\nAt the end of your response, cite the source as a markdown link: [Source]({web_citation})"
        if web_citation else ""
    )

    image_note = (
        "Image 1 is the current page image. Images 2..N are additional pages in order."
        if all_images else "No images were provided for this query."
    )

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        context=combined_context,
        question=query_text + citation_instruction,
        image_note=image_note,
    )

    # deduplicate images
    seen, unique_images = set(), []
    for img in all_images:
        if img not in seen:
            seen.add(img)
            unique_images.append(img)

    response = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt, "images": unique_images}],
    )
    return response["message"]["content"]