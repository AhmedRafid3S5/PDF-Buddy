import argparse
import os
import json
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from ollama import chat
from .get_embedding_function import get_embedding_function
from dotenv import load_dotenv

load_dotenv("configs.env")

pdf_dir_path = os.getenv("SAVE_DIR","Data")
chroma_path = os.getenv("CHROMA_PATH")
PROMPT_TEMPLATE = """
Answer the question based only on the following context and any provided images.
{image_note}
If no text context is provided, rely on the images to answer. If any text and images provided do not talk about the same subject or topic, use the current page image (Image 1) to answer query.
Respond in Markdown.

{context}

---

Answer the question based on the above context: {question}
"""
#might want to return a type of rich text here is possible
#see if new db instantiation here is causing overhead


    
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


def query_rag(query_text: str, extra_images=None, fallback_images=None) -> str:
    embedding_function = get_embedding_function()
    
    #init in constructor after class creation
    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=embedding_function,
    )
    
    # investigate if larger k is better or not for use case
    initial_results = db.similarity_search_with_score(query_text, k=5)
    metadata_hint = _build_metadata_hint(initial_results)
    retrieval_query = (
        f"{query_text}\n{metadata_hint}" if metadata_hint else query_text
    )
    results = db.similarity_search_with_score(retrieval_query, k=5)

    # retrieve relevant page numbers per source
    pages_by_source: dict[str, set[int]] = {}
    for doc, _score in results:
        source = doc.metadata.get("source")
        page = doc.metadata.get("page")
        if source is None or page is None:
            continue
        pages_by_source.setdefault(source, set()).add(int(page) + 1)

    # load only these relevant page images
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

    all_images: list[str] = []
    if extra_images:
        all_images.extend(extra_images)

    if results:
        all_images.extend(page_images)
    elif fallback_images:
        all_images.extend(fallback_images)

    # Build context for the LLM.
    context_text = "\n\n---\n\n".join(
        [doc.page_content for doc, _score in results]
    )
    if not context_text:
        context_text = "(No relevant text retrieved.)"

    # Preserve order while removing duplicates.
    seen_images = set()
    unique_images: list[str] = []
    for image in all_images:
        if image in seen_images:
            continue
        seen_images.add(image)
        unique_images.append(image)
    all_images = unique_images

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    if all_images:
        image_note = (
            "Image 1 is the current page image. Images 2..N are additional pages in order."
        )
    else:
        image_note = "No images were provided for this query."

    prompt = prompt_template.format(
        context=context_text,
        question=query_text,
        image_note=image_note,
    )

    response = chat(
        model="gemma4:31b-cloud",
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": all_images,
            }
        ],
    )
    response_text = response["message"]["content"]

    sources = [doc.metadata.get("id", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)
    return response_text


