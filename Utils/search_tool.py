from langchain_community.tools import DuckDuckGoSearchRun, DuckDuckGoSearchResults
import json
from ollama import chat

def mostRevelantLink(query):
    search = DuckDuckGoSearchResults(output_format="json")
    results_str = search.invoke(query)
    results = json.loads(results_str)

    return results[0] # returns a single object {snippet,title,link}

def optimise_search_query(user_query: str, context_summary: str = "") -> str:
    """Rewrite the user query into an effective web search query."""
    prompt = f"""You are a search query optimiser.
Rewrite the following user question into a concise, specific web search query (max 10 words).
Remove pronouns and conversational language. Add technical keywords if relevant.
{"Context already retrieved: " + context_summary if context_summary else ""}

User question: {user_query}
Search query:"""

    response = chat(
        model="gemma4:31b-cloud",
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"].strip().strip('"')