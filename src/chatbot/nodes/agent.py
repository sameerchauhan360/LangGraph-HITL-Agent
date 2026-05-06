from langchain_core.messages import SystemMessage
from chatbot.nodes.llm import LLM
from chatbot.tools.executor_tool import code_executor
from chatbot.tools.websearch import web_search

# LLM with tools bound — used for the main reasoning/execution loop
_llm = LLM().llm
tools = [code_executor, web_search]
llm_with_tools = _llm.bind_tools(tools)

_BASE_SYSTEM = """\
You are an elite reasoning and execution agent.

Rules:

1. Think first.
   - Decompose the task, identify constraints, form a plan before acting.

2. Use tools intelligently.
   - Choose the minimum effective tool chain.
   - For time-sensitive queries, confirm dates and recency first.
   - Do NOT repeat the same web search query more than once.
   - FINANCIAL DATA: Always use the `yfinance` Python library for stock prices, revenue, and earnings.
     NEVER try to scrape macrotrends.net, Yahoo Finance HTML, or similar financial sites — they block bots.
     Example: `import yfinance as yf; info = yf.Ticker("NVDA").financials`

3. Execute efficiently.
   - Do not narrate routine tool usage.
   - Avoid filler, repetition, raw logs, or unnecessary commentary.

4. Adapt and recover.
   - If one approach fails, try ONE different strategy. If that also fails, use well-known approximations and state they are estimates.
   - Do NOT loop on the same failing approach.

5. Stay accurate.
   - Never hallucinate facts, sources, or results.

6. Optimize for outcomes.
   - Deliver concise, actionable, high-signal responses.

REJECTION: If a tool is cancelled, ask once: "Retry? (y/n)". Only proceed on 'y'.\
"""


async def agent_node(state) -> dict:
    """
    Plan-aware agent node.

    If a task plan exists in state, it prepends a checklist context message
    so the LLM knows which steps are pending and which are done.
    """
    plan: list[dict] | None = state.get("plan")
    trimmed_messages = state["messages"][-25:]

    messages_to_send = [SystemMessage(content=_BASE_SYSTEM)]

    if plan:
        icons = {"pending": "⬜", "done": "✅", "failed": "❌"}
        checklist = "\n".join(
            f"  {icons.get(t['status'], '⬜')} {t['id']}. {t['task']}"
            for t in plan
        )
        # Find the current pending task
        next_task = next((t for t in plan if t["status"] == "pending"), None)
        if next_task:
            hint_text = f"\n💡 Hint for this step: {next_task['hint']}" if next_task.get("hint") else ""
            next_task_text = (
                f"\nYour ONLY job right now: complete task {next_task['id']} — '{next_task['task']}'"
                f"{hint_text}"
            )
        else:
            next_task_text = "\nAll tasks are complete. Summarize the results."

        plan_context = SystemMessage(
            content=(
                "TASK CHECKLIST:\n"
                f"{checklist}\n\n"
                "RULES:\n"
                "- Execute EXACTLY ONE pending task per response.\n"
                "- Do NOT combine multiple tasks into one code block.\n"
                "- After completing a task, stop and wait. The system will call you again for the next task.\n"
                f"{next_task_text}"
            )
        )
        messages_to_send.append(plan_context)

    messages_to_send.extend(trimmed_messages)

    response = await llm_with_tools.ainvoke(messages_to_send)

    # Auto-advance the plan: if the agent gave a final text response (no tool call),
    # it means it just completed the current task — mark it done.
    updated_plan = plan
    if plan and not response.tool_calls:
        updated_plan = []
        marked = False
        for task in plan:
            if not marked and task["status"] == "pending":
                updated_plan.append({**task, "status": "done"})
                marked = True
            else:
                updated_plan.append(task)

    return {"messages": [response], "plan": updated_plan}
