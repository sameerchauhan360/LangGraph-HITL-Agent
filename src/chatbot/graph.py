from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from chatbot.state import AgentState
from chatbot.nodes.planner import planner_node
from chatbot.nodes.agent import agent_node, tools
from chatbot.tools.websearch import reset_search_state


def route_agent(state: AgentState) -> str:
    """
    After the agent responds:
    - If it made tool calls → go to tools node
    - If there are still pending tasks in the plan → loop back to agent (fresh search budget)
    - Otherwise → END
    """
    last_message = state["messages"][-1]

    # Tool calls take priority
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Keep going if there are unfinished plan tasks
    plan = state.get("plan")
    if plan and any(t["status"] == "pending" for t in plan):
        reset_search_state()  # fresh search budget for each new plan step
        return "agent"

    return END

# ── Build Graph ───────────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))

# Planner always runs first, then passes to agent
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "agent")

# Plan-aware routing: tools → tools node, pending tasks → agent, done → END
workflow.add_conditional_edges("agent", route_agent)
workflow.add_edge("tools", "agent")

# graph is compiled in main.py with AsyncSqliteSaver

