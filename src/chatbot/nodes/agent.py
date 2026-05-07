from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, RemoveMessage
from chatbot.nodes.llm import LLM
from chatbot.tools.executor_tool import code_executor
from chatbot.tools.websearch import web_search

# LLM with tools bound — used for the main reasoning/execution loop
_llm = LLM().llm
tools = [code_executor, web_search]
llm_with_tools = _llm.bind_tools(tools)

# Summarization threshold — when message count exceeds this, old messages are summarized
MAX_MESSAGES = 20
KEEP_RECENT = 10  # Always keep the last N messages verbatim

_SUMMARIZE_PROMPT = """\
You are a conversation summarizer. Given the following conversation excerpt, write a concise summary \
that captures all key facts, decisions, results, and context that would be needed to continue the \
conversation. Focus on concrete outcomes (e.g. code written, searches done, conclusions reached). \
Be brief but complete.

Conversation:
{conversation}

Summary:"""

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


async def _summarize_old_messages(messages: list) -> SystemMessage:
    """Summarizes old messages into a single SystemMessage to preserve context."""
    conversation = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: "
        f"{m.content if isinstance(m.content, str) else str(m.content)}"
        for m in messages
        if isinstance(m, (HumanMessage, AIMessage)) and m.content
    )
    prompt = _SUMMARIZE_PROMPT.format(conversation=conversation)
    summary_response = await _llm.ainvoke([HumanMessage(content=prompt)])
    return SystemMessage(content=f"[CONVERSATION SUMMARY — earlier context]\n{summary_response.content}")


async def agent_node(state) -> dict:
    """
    Plan-aware agent node with automatic conversation summarization.

    When the message history exceeds MAX_MESSAGES, older messages are summarized
    into a single SystemMessage to preserve context without ballooning token usage.
    """
    plan: list[dict] | None = state.get("plan")
    all_messages = state["messages"]

    # ── Summarization buffer ─────────────────────────────────────────────────────────
    # Check if there's already a summary from a previous summarization cycle
    existing_summary = None
    conversation_messages = all_messages
    for i, msg in enumerate(all_messages):
        if isinstance(msg, SystemMessage) and msg.content.startswith("[CONVERSATION SUMMARY"):
            existing_summary = msg
            conversation_messages = all_messages[i+1:]
            break

    if len(conversation_messages) > MAX_MESSAGES:
        # Split: summarize old messages, keep recent ones verbatim
        to_summarize = list(conversation_messages[:-KEEP_RECENT])
        recent_messages = list(conversation_messages[-KEEP_RECENT:])

        # Include previous summary in what we summarize
        if existing_summary:
            to_summarize = [existing_summary] + to_summarize

        print("\n  \033[90m[Summarizing older messages to free up context...]\033[0m", flush=True)
        new_summary = await _summarize_old_messages(to_summarize)
        trimmed_messages = [new_summary] + recent_messages

        # Build state update: remove old messages + existing summary, add new summary
        # This persists the compaction so we never re-summarize the same messages again
        messages_to_remove = ([existing_summary] if existing_summary else []) + to_summarize
        messages_to_persist = [RemoveMessage(id=m.id) for m in messages_to_remove if hasattr(m, "id") and m.id] + [new_summary]
        did_summarize = True
    else:
        # Under the limit — prepend existing summary if present
        if existing_summary:
            trimmed_messages = [existing_summary] + list(conversation_messages)
        else:
            trimmed_messages = list(conversation_messages)
        messages_to_persist = []
        did_summarize = False

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

    return {
        "messages": messages_to_persist + [response],
        "plan": updated_plan
    }
