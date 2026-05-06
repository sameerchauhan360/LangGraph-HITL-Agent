import json
from langchain_core.messages import HumanMessage
from chatbot.nodes.llm import LLM

# Dedicated lightweight LLM instance for planning (no tools needed)
_planner_llm = LLM().llm

_PLANNER_PROMPT = """\
You are a task planner. Analyze if the user request requires multiple DISTINCT steps.

Respond ONLY with valid JSON — either the word null or a task array.

Rules:
- ONE action or a direct question → null
- TWO or more distinct actions → task array with a HINT for each step

Output format (array):
[{{"id": 1, "task": "brief task description", "status": "pending", "hint": "specific tool or approach to use"}}, ...]

The "hint" field must contain a SPECIFIC, ACTIONABLE suggestion:
- For financial/stock data: "Use yfinance: yf.Ticker('SYMBOL').financials for annual revenue"
- For web content: "Use requests + BeautifulSoup or the web_search tool"
- For charts/plots: "Use matplotlib.pyplot, save as PNG with plt.savefig()"
- For file operations: "Use open() with absolute path via os.path.join(os.getcwd(), 'filename')"
- For calculations: "Use pandas or plain Python math — no external API needed"
- For inflation adjustment: "Fetch CPI data from FRED API or use BLS CPI table hardcoded"
- For web automation: "Use webbrowser.open() for simple URLs, playwright for interaction"
- For data analysis: "Use pandas DataFrame, then describe() or groupby()"

Examples:
- "what is 2+2?" → null
- "search today's BTC price and save it to a file" → [
    {{"id":1,"task":"Search current BTC price","status":"pending","hint":"Use web_search tool with query 'Bitcoin price today USD'"}},
    {{"id":2,"task":"Save the price to a file","status":"pending","hint":"Use open() to write to os.path.join(os.getcwd(), 'btc_price.txt')"}}
  ]

Respond with ONLY the JSON value. No markdown, no code blocks, no explanation.

User request: {query}"""


async def planner_node(state) -> dict:
    """
    Runs once per user turn before the agent.
    Returns a JSON task plan for complex queries, or None for simple ones.
    """
    # Find the last human message
    last_human = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        None,
    )
    if not last_human:
        return {"plan": None}

    response = await _planner_llm.ainvoke(
        [HumanMessage(content=_PLANNER_PROMPT.format(query=last_human))]
    )
    raw = response.content.strip()

    # Strip accidental markdown code fences
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()

    # Handle literal "null"
    if raw.lower() == "null":
        return {"plan": None}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) >= 2:
            return {"plan": parsed}
    except Exception:
        pass

    return {"plan": None}
