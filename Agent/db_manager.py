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

    #Calculate chunk IDs and append that info as attribute to chunk object
    chunks_with_ids = calculate_chunk_ids(chunks)

    #add of update documents
    existing_items = db.get(include=[])
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB: {len(existing_ids)}")

    new_chunks: list[Document] = [] # enforce variable type using : list[Document]
    for chunk in chunks_with_ids:
        if chunk.metadata["id"] not in existing_ids:
            new_chunks.append(chunk) #only add to list of new chunks if chunk not already in the database

    #check if new_chunks list has elements, then add them to db, finally log them
    if new_chunks:
        print(f"👉 Adding new documents: {len(new_chunks)}")
        new_chunks_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, id=new_chunks_ids)
        #db.persist() # may not be required for this usecase

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

