from typing import Optional
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """
    Extended state that adds a structured task plan on top of LangGraph's
    built-in message list.

    `plan` is replaced (not appended) on each state update — whichever node
    writes it last wins. None means no active plan (simple query).

    Forward-compatible: each item here maps 1-to-1 with a future branch node
    in the task_tree architecture (future_plan.md).
    """
    plan: Optional[list[dict]]  # [{"id": 1, "task": "...", "status": "pending"}]
