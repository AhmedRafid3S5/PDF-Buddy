import os
import re
import requests
from dotenv import load_dotenv
load_dotenv("configs.env")
from langchain_community.document_loaders import WebBaseLoader

def is_content_empty(text: str) -> bool:
    """Check if the scraped content is meaninglessly short."""
    return not text or len(text.strip()) < 200


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_page(url: str, header_template: dict | None) -> str | None:
    # 1. Check if the URL is reachable before loading
    try:
        headers = header_template or {}
        probe = requests.get(url, headers=headers, timeout=10)

        if probe.status_code == 403:
            print(f"Access denied (403) for {url} — site is blocking scrapers.")
            return None
        if probe.status_code == 429:
            print(f"Rate limited (429) for {url} — too many requests.")
            return None
        if probe.status_code != 200:
            print(f"Unexpected status {probe.status_code} for {url}.")
            return None

    except requests.exceptions.ConnectionError:
        print(f"Connection error: could not reach {url}.")
        return None
    except requests.exceptions.Timeout:
        print(f"Request timed out for {url}.")
        return None

    # 2. Load with WebBaseLoader
    try:
        loader = WebBaseLoader(web_path=url, header_template=header_template) \
                 if header_template else WebBaseLoader(web_path=url)
        docs = loader.load()
    except Exception as e:
        print(f"WebBaseLoader failed: {e}")
        return None

    # 3. Validate the content
    if not docs:
        print("No documents returned by loader.")
        return None

    page_text = docs[0].page_content

    if is_content_empty(page_text):
        print("Page loaded but content is empty or too short — possibly JS-rendered or blocked.")
        return None

    return normalize_whitespace(page_text)

def read_page(url, fallback_snippet, verbose=True):
        user_agent = os.getenv("USER_AGENT")
        header_template = {"User-Agent": user_agent} if user_agent else None
        page_text = load_page(url, header_template)

        if page_text is None:
                if verbose:
                        print(
                                "Could not retrieve content. Consider: trying another URL from search results."
                        )
                return fallback_snippet

        if verbose:
                print(page_text)
        return page_text.rstrip()
   


