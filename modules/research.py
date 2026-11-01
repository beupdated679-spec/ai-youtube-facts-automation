import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"

def find_research(topic: str) -> dict:
    """Fetch a short Wikipedia extract to ground the script topic."""
    headers = {"User-Agent": "FactsKnowledgeVideoBot/1.0 (educational video project)"}
    params = {
        "action": "query", "generator": "search", "gsrsearch": topic,
        "gsrlimit": 1, "prop": "extracts|info", "exintro": 1,
        "explaintext": 1, "inprop": "url", "format": "json"
    }
    response = requests.get(WIKI_API, params=params, headers=headers, timeout=25)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    if not pages:
        return {"title": topic, "extract": "", "url": ""}
    page = next(iter(pages.values()))
    return {
        "title": page.get("title", topic),
        "extract": page.get("extract", "")[:7000],
        "url": page.get("fullurl", "")
    }
