from langchain_tavily import TavilySearch
from langchain_core.tools import tool
import os
from dotenv import load_dotenv

load_dotenv()

# Per-turn query deduplication cache
_searched_queries: set[str] = set()
_search_count: int = 0
MAX_SEARCHES_PER_TURN = 6  # raised to support multi-step plans


@tool
def web_search(query: str) -> str:
    """
    A tool that searches the internet for real-time information.
    Call this whenever the user's request requires up-to-date or factual information
    that cannot be answered from training data alone (e.g., news, sports scores,
    current events, live data).
    Pass the user's question as the 'query' argument.
    IMPORTANT: Do NOT call this with the same or very similar query more than once.
    """
    global _search_count

    normalized = query.strip().lower()

    if normalized in _searched_queries:
        return (
            f"[SEARCH SKIPPED] Already searched for '{query}'. "
            "Use the results already returned or answer based on what you know."
        )

    if _search_count >= MAX_SEARCHES_PER_TURN:
        return (
            f"[SEARCH LIMIT REACHED] Maximum of {MAX_SEARCHES_PER_TURN} searches per turn. "
            "Answer based on information already gathered."
        )

    _searched_queries.add(normalized)
    _search_count += 1

    from rich import print as rprint
    rprint(f"\n  [dim cyan]🔍 [bold]Research Agent[/bold] is searching the web for: [italic]'{query}'[/italic]...[/dim cyan]")

    search = TavilySearch(api_key=os.getenv("TAVILY_API_KEY"))
    results = search.run(query)

    if isinstance(results, dict) and "results" in results:
        formatted = [
            f"- {item['title']}: {item['content']} - url: {item.get('url', '')}"
            for item in results["results"][:4]
        ]
        return "\n".join(formatted)

    return str(results)


def reset_search_state():
    """Call at the start of each user turn to reset the dedup cache."""
    global _searched_queries, _search_count
    _searched_queries = set()
    _search_count = 0
