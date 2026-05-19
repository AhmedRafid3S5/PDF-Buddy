import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
	sys.path.insert(0, repo_root)

from Utils.search_tool import mostRevelantLink
from Utils.web_loader import read_page

query = "Effect of randomization in quick sort"

result = mostRevelantLink(query)
url, snippet, title = result["link"], result["snippet"], result["title"]
print("Snippet: " + snippet)
print("Title: " + title)
print("Link: " + url)

web_txt = read_page(url, snippet)
print(web_txt)