import argparse
import os
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM  # partner package
from .get_embedding_function import get_embedding_function
from dotenv import load_dotenv

load_dotenv("configs.env")

pdf_dir_path = os.getenv("SAVE_DIR","Data")
chroma_path = os.getenv("CHROMA_PATH")
PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
"""
#might want to return a type of rich text here is possible
#see if new db instantiation here is causing overhead


    
def query_rag(query_text: str) -> str:
    embedding_function = get_embedding_function()
    
    #init in constructor after class creation
    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=embedding_function,
    )
    
    # investigate if larger k is better or not for use case
    results = db.similarity_search_with_score(query_text, k=5)

    # Build context for the LLM.
    context_text = "\n\n---\n\n".join(
        [doc.page_content for doc, _score in results]
    )

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(
        context=context_text,
        question=query_text,
    )

        # Call local Ollama model (e.g., mistral).
    model = OllamaLLM(model="gpt-oss:120b-cloud")
    response_text = model.invoke(prompt)

    sources = [doc.metadata.get("id", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)
    return response_text


