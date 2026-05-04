import argparse
import os
import shutil

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_chroma import Chroma
from .get_embedding_function import get_embedding_function
from dotenv import load_dotenv

load_dotenv("configs.env")

pdf_dir_path = os.getenv("SAVE_DIR","Data")
chroma_path = os.getenv("CHROMA_PATH")


#def main():
#    # Check if the database should be cleared (using the --reset flag).
#    parser = argparse.ArgumentParser()
#    parser.add_argument("--reset", action="store_true", help="Reset the database.")
#    args = parser.parse_args()
#    if args.reset:
#        print("✨ Clearing Database")
#        clear_database()
#
#    # Create (or update) the data store.
#    documents = load_documents()
#    chunks = split_documents(documents)
#    add_to_chroma(chunks)


# loads all pdf in directory
# this way we can build a context for the conversation session
# TODO: Figure out the amount of context the LLM remembers
def load_documents() -> list[Document]:
    loader = PyPDFDirectoryLoader(pdf_dir_path)
    return loader.load()

def split_documents(documents: list[Document])-> list[Document]:
     text_splitter = RecursiveCharacterTextSplitter(
         chunk_size= 800,
         chunk_overlap = 100,
         length_function=len,
         is_separator_regex=False,
     )
     return text_splitter.split_documents(documents)

def clear_database()-> None:
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)

def clear_pdf() -> None:
    if os.path.exists(pdf_dir_path):
        shutil.rmtree(pdf_dir_path)

#question : does call to db like this become resource intensive?
#TODO : Find out
def add_to_chroma(chunks: list[Document]) -> None:
    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=get_embedding_function(),
    )

    # Calculate chunk IDs and append that info to each chunk's metadata.
    chunks_with_ids = calculate_chunk_ids(chunks)

    # Collect all candidate IDs.
    chunk_ids = [chunk.metadata["id"] for chunk in chunks_with_ids]

    # Check which of these IDs already exist in the DB, in batches.
    existing_ids: set[str] = set()
    batch_size = 1000
    for start in range(0, len(chunk_ids), batch_size):
        batch_ids = chunk_ids[start : start + batch_size]
        existing_items = db.get(ids=batch_ids, include=[])
        existing_ids.update(existing_items.get("ids", []))

    print(f"Number of existing documents in DB: {len(existing_ids)}")

    # Filter out chunks whose IDs are already present.
    new_chunks: list[Document] = [
        chunk for chunk in chunks_with_ids
        if chunk.metadata["id"] not in existing_ids
    ]

    if new_chunks:
        print(f"👉 Adding new documents: {len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        # REMEMBER : ids is the correct arg, not id
        db.add_documents(documents=new_chunks, ids=new_chunk_ids)
        # db.persist()  # enable if you want to persist after each run
    else:
        print("✅ No new documents to add")
    
def calculate_chunk_ids(chunks: list[Document]) -> list[Document]:
    """
    Create IDs like 'data/monopoly.pdf:6:2'
    Format: Page Source : Page Number : Chunk Index
    """
    last_page_id: str | None = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        # If the page ID is the same as the last one, increment the index.
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        # Calculate the chunk ID.
        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        # Add it to the page metadata.
        chunk.metadata["id"] = chunk_id

    return chunks

