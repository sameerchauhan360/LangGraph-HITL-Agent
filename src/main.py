import asyncio
import sys
import os
from dotenv import load_dotenv

# Load .env FIRST — before any LangChain/LangSmith imports read the env
load_dotenv()

sys.path.append(os.path.join(os.getcwd(), "src"))


from chatbot.graph import workflow
from chatbot.tools.websearch import reset_search_state
from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.types import Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from rich.console import Console

console = Console(highlight=False)

DB_PATH = os.path.join(os.getcwd(), "chat_history.db")

# ── ANSI Color Palette ─────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"


def header(text: str, color: str = CYAN):
    width = 54
    bar = "─" * width
    print(f"\n{color}{BOLD}┌{bar}┐{RESET}")
    print(f"{color}{BOLD}│  {text:<{width - 2}}│{RESET}")
    print(f"{color}{BOLD}└{bar}┘{RESET}")


def divider(color: str = GRAY):
    print(f"{color}{'─' * 56}{RESET}")


def status(text: str):
    print(f"\n{GRAY}{DIM}  ◆ {text}{RESET}")


def code_box(code: str, title: str = "PROPOSED CODE"):
    width = 56
    print(f"\n{YELLOW}{BOLD}┌── {title} {'─' * (width - len(title) - 4)}┐{RESET}")
    for line in code.splitlines():
        # Truncate long lines for display
        display = line[: width - 2]
        print(f"{YELLOW}│{RESET} {CYAN}{display:<{width - 2}}{YELLOW}│{RESET}")
    print(f"{YELLOW}└{'─' * width}┘{RESET}")


def bot_prefix():
    print(f"\n  {BLUE}{BOLD}● Bot{RESET}  ", end="", flush=True)


def user_prompt() -> str:
    return input(f"\n  {GREEN}{BOLD}● You{RESET}  ")


def hitl_prompt() -> str:
    return (
        input(f"\n  {YELLOW}{BOLD}[HITL]{RESET} Execute this code? {DIM}(y/n){RESET}: ")
        .strip()
        .lower()
    )


def plan_checklist(plan: list[dict]):
    """Renders the task plan as a visual checklist in the terminal."""
    icons = {"pending": "⬜", "done": "✅", "failed": "❌"}
    width = 52
    count = len(plan)
    print(f"\n  {YELLOW}{BOLD}📋 Plan — {count} subtask{'s' if count != 1 else ''}{RESET}")
    print(f"  {YELLOW}┌{'─' * width}┐{RESET}")
    for task in plan:
        icon = icons.get(task.get("status", "pending"), "⬜")
        text = task["task"]
        if len(text) > width - 5:
            text = text[: width - 8] + "..."
        print(f"  {YELLOW}│{RESET} {icon} {text:<{width - 4}} {YELLOW}│{RESET}")
    print(f"  {YELLOW}└{'─' * width}┘{RESET}")


async def handle_interrupt(graph, snapshot, config) -> Command | None:
    """Finds and handles an interrupt in the current snapshot. Returns Command or None."""
    interrupt_payload = None
    for task in snapshot.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            interrupt_payload = task.interrupts[0].value
            break

    if interrupt_payload:
        code = interrupt_payload.get("code", "")
        code_box(code)
        confirm = hitl_prompt()
        return Command(resume="approve" if confirm == "y" else "reject")

    return Command(resume="skip")


async def run_turn(graph, current_input, config):
    """Runs one full turn (stream + interrupt handling)."""
    from langgraph.errors import GraphRecursionError

    while True:
        plan_shown = False
        bot_prefix()
        current_msg_id = None

        try:
            async for event_type, data in graph.astream(
                current_input,
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if event_type == "updates":
                    planner_update = data.get("planner", {})
                    if not plan_shown and planner_update.get("plan"):
                        print()  # end the "● Bot  " line
                        plan_checklist(planner_update["plan"])
                        bot_prefix()
                        plan_shown = True

                elif event_type == "messages":
                    msg, metadata = data
                    if (
                        isinstance(msg, AIMessageChunk)
                        and msg.content
                        and metadata.get("langgraph_node") == "agent"
                    ):
                        if current_msg_id != msg.id:
                            if current_msg_id is not None:
                                print("\n")
                                bot_prefix()
                                
                            current_msg_id = msg.id
                        
                        clean_content = msg.content.replace("\r\n", "\n").replace("\r", "")
                        print(clean_content, end="", flush=True)

        except GraphRecursionError:
            print(f"\n  {RED}⚠  Loop detected — agent got stuck. Try rephrasing.{RESET}")
            return
        except Exception as e:
            err = str(e)
            if "unexpected tokens" in err or "APIError" in type(e).__name__:
                print(f"\n  {YELLOW}⚠  API tool-call error (model glitch). Re-send your message.{RESET}")
                return
            raise

        print()  # newline after streaming

        snapshot = await graph.aget_state(config)
        if not snapshot.next:
            return  # Done

        current_input = await handle_interrupt(graph, snapshot, config)


async def main():
    header("  HITL  Chatbot", CYAN)
    print(f"\n{GRAY}  Persistent · Tool-enabled · Human-in-the-loop{RESET}\n")

    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
        graph = workflow.compile(checkpointer=memory)

        # ── Session selection ──────────────────────────────────────────────────
        try:
            session_name = input(
                f"  {MAGENTA}Chat name{RESET} {DIM}(Enter = 'default'){RESET}: "
            ).strip()
        except EOFError:
            return
        if not session_name:
            session_name = "default"

        config = {"configurable": {"thread_id": session_name}, "recursion_limit": 30}

        # ── Load state ────────────────────────────────────────────────────────
        existing = await graph.aget_state(config)
        if existing and existing.values.get("messages"):
            msgs = existing.values["messages"]
            print(
                f"\n  {CYAN}↩  Resuming{RESET} {BOLD}'{session_name}'{RESET} {GRAY}— {len(msgs)} messages{RESET}"
            )
        else:
            print(f"\n  {GREEN}✦  New chat:{RESET} {BOLD}'{session_name}'{RESET}")

        divider()
        print(f"  {DIM}Commands: 'history' · 'quit'{RESET}")
        divider()

        # ── Recover pending interrupt from a crashed session ───────────────────
        if existing and existing.next:
            interrupt_payload = None
            for task in existing.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_payload = task.interrupts[0].value
                    break

            if interrupt_payload:
                print(
                    f"\n  {YELLOW}{BOLD}⚠  Pending approval recovered from last session{RESET}"
                )
                code = interrupt_payload.get("code", "")
                code_box(code, "PENDING CODE")
                confirm = hitl_prompt()
                resume_cmd = Command(resume="approve" if confirm == "y" else "reject")
                await run_turn(graph, resume_cmd, config)

        # ── Main chat loop ─────────────────────────────────────────────────────
        while True:
            try:
                user_input = user_prompt().strip()
            except EOFError:
                print(f"\n  {GRAY}[Stream closed. Exiting.]{RESET}")
                break

            if user_input.lower() in ["quit", "exit", "q"]:
                print(f"\n  {GRAY}Goodbye!{RESET}\n")
                break

            if not user_input:
                continue

            if user_input.lower() == "history":
                state = await graph.aget_state(config)
                msgs = state.values.get("messages", []) if state else []
                if not msgs:
                    print(f"\n  {GRAY}No history yet.{RESET}")
                else:
                    divider(CYAN)
                    print(f"  {CYAN}{BOLD}History — {len(msgs)} messages{RESET}")
                    divider(CYAN)
                    for m in msgs:
                        role = (
                            f"{GREEN}You{RESET}"
                            if m.type == "human"
                            else f"{BLUE}Bot{RESET}"
                        )
                        content = (
                            m.content if isinstance(m.content, str) else str(m.content)
                        )
                        snippet = content[:180] + ("…" if len(content) > 180 else "")
                        print(f"  {role}: {GRAY}{snippet}{RESET}")
                    divider(CYAN)
                continue

            await run_turn(
                graph, {"messages": [HumanMessage(content=user_input)]}, config
            )


if __name__ == "__main__":
    asyncio.run(main())
