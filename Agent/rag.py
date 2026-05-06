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


def query_rag(query_text: str) -> str:
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

    # Build context for the LLM.
    context_text = "\n\n---\n\n".join(
        [doc.page_content for doc, _score in results]
    )

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        context=context_text,
        question=query_text,
    )

    response = chat(
        model="gemma4:31b-cloud",
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": page_images,
            }
        ],
    )
    response_text = response["message"]["content"]

    sources = [doc.metadata.get("id", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)
    return response_text


