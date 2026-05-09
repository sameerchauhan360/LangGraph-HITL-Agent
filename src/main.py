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
import subprocess
import tree_manager
import snapshot_manager

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
                f"  {MAGENTA}Chat branch{RESET} {DIM}(Enter = 'default'){RESET}: "
            ).strip()
        except EOFError:
            return
        if not session_name:
            session_name = "default"

        # Ensure the branch exists in metadata
        if not tree_manager.branch_exists(session_name):
            tree_manager.create_branch(session_name, parent=None, summary="Main timeline")

        # Ensure the git branch exists (may not exist on very first run)
        if not snapshot_manager.snapshot_exists(session_name):
            snapshot_manager.create_initial_branch(session_name)
            print(f"  {GRAY}[Created initial workspace branch 'agent/{session_name}']{RESET}")
        else:
            # Switch git to this branch (no-op if already on it)
            snapshot_manager.restore_snapshot(session_name)
            print(f"  {GRAY}[Workspace: agent/{session_name}]{RESET}")

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
        print(f"  {DIM}Commands: 'history' · 'quit' · '/status' · '/discard' · '/log' · '/merge <branch>'{RESET}")
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
            except (EOFError, KeyboardInterrupt):
                saved = snapshot_manager.save_snapshot(session_name)
                if saved:
                    print(f"\n  {GRAY}[Checkpoint saved on 'agent/{session_name}']{RESET}")
                print(f"\n  {GRAY}[Stream closed. Exiting.]{RESET}")
                break

            if user_input.lower() in ["quit", "exit", "q"]:
                saved = snapshot_manager.save_snapshot(session_name)
                if saved:
                    print(f"  {GRAY}[Checkpoint saved on 'agent/{session_name}']{RESET}")
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

            if user_input.startswith("/"):
                parts = user_input.split(" ", 2)
                cmd = parts[0].lower()
                
                if cmd == "/branches":
                    branches = tree_manager.get_branches()
                    print(f"\n  {CYAN}{BOLD}🌳 Branches{RESET}")
                    divider(CYAN)
                    for b_name, b_meta in branches.items():
                        status = b_meta.get("status", "active")
                        is_active = "★" if b_name == session_name else " "

                        if status == "archived":
                            color = DIM + GRAY
                            status_icon = "🗄"
                        elif b_name == session_name:
                            color = GREEN
                            status_icon = "🟢"
                        else:
                            color = RESET
                            status_icon = "⚪"

                        parent = f"(parent: {b_meta['parent']})" if b_meta.get('parent') else "(root)"
                        desc = tree_manager.get_branch_description(b_name)
                        desc_str = f" {GRAY}{desc}{RESET}" if desc else ""
                        print(f"  {color}{is_active} {status_icon} {BOLD}{b_name:<15}{RESET} {GRAY}{parent:<22}{RESET}{desc_str}")
                    divider(CYAN)
                    continue

                elif cmd == "/checkout" and len(parts) >= 2:
                    target_branch = parts[1]
                    if not tree_manager.branch_exists(target_branch):
                        print(f"\n  {RED}⚠ Branch '{target_branch}' does not exist.{RESET}")
                        continue

                    meta = tree_manager.get_branch(target_branch)
                    if meta and meta.get("status") == "archived":
                        print(f"\n  {YELLOW}⚠ Branch '{target_branch}' is archived. Use /prune to remove it or create a new branch.{RESET}")
                        continue

                    # Commit current, checkout target
                    snapshot_manager.switch_snapshot(session_name, target_branch)
                    session_name = target_branch
                    config["configurable"]["thread_id"] = session_name
                    state = await graph.aget_state(config)
                    msgs_count = len(state.values.get("messages", [])) if state else 0
                    print(f"\n  {GREEN}✔ Switched to 'agent/{session_name}' ({msgs_count} messages).{RESET}")
                    continue

                elif cmd == "/branch" and len(parts) >= 3:
                    new_branch = parts[1]
                    summary = parts[2]
                    
                    if tree_manager.branch_exists(new_branch):
                        print(f"\n  {RED}⚠ Branch '{new_branch}' already exists!{RESET}")
                        continue
                    
                    # 1. Grab current LangGraph state
                    current_state = await graph.aget_state(config)

                    # 2. Commit current + create new git branch (inherits all files)
                    snapshot_manager.copy_snapshot(session_name, new_branch)

                    # 3. Register the branch (summary stored in git config)
                    tree_manager.create_branch(new_branch, parent=session_name, summary=summary)
                    session_name = new_branch
                    config["configurable"]["thread_id"] = session_name

                    # 4. Inject LangGraph conversation state into new branch
                    if current_state and current_state.values:
                        await graph.aupdate_state(config, current_state.values)

                    print(f"\n  {GREEN}✔ Created 'agent/{session_name}' — workspace and memory inherited.{RESET}")
                    continue
                elif cmd == "/archive" and len(parts) >= 2:
                    target = parts[1]
                    if not tree_manager.branch_exists(target):
                        print(f"\n  {RED}⚠ Branch '{target}' does not exist.{RESET}")
                        continue
                    if target == session_name:
                        print(f"\n  {RED}⚠ Cannot archive the currently active branch. Switch to another branch first.{RESET}")
                        continue
                    tree_manager.archive_branch(target)
                    print(f"\n  {YELLOW}🗄 Branch '{target}' has been archived.{RESET}")
                    continue

                elif cmd == "/prune" and len(parts) >= 2:
                    target = parts[1]
                    if not tree_manager.branch_exists(target):
                        print(f"\n  {RED}⚠ Branch '{target}' does not exist.{RESET}")
                        continue
                    if target == session_name:
                        print(f"\n  {RED}⚠ Cannot prune the currently active branch. Switch to another branch first.{RESET}")
                        continue
                    confirm = input(f"\n  {RED}⚠ Permanently delete '{target}'? This cannot be undone. (y/n): {RESET}").strip().lower()
                    if confirm == "y":
                        tree_manager.delete_branch(target)
                        snapshot_manager.delete_snapshot(target)
                        print(f"  {RED}🗑 Branch '{target}' permanently deleted.{RESET}")
                    else:
                        print(f"  {GRAY}Prune cancelled.{RESET}")
                    continue

                elif cmd == "/restore" and len(parts) >= 2:
                    target = parts[1]
                    if not tree_manager.branch_exists(target):
                        print(f"\n  {RED}⚠ Branch '{target}' does not exist.{RESET}")
                        continue
                    meta = tree_manager.get_branch(target)
                    if meta and meta.get("status") != "archived":
                        print(f"\n  {YELLOW}⚠ Branch '{target}' is not archived.{RESET}")
                        continue
                    tree_manager.restore_branch(target)
                    print(f"\n  {GREEN}✔ Branch '{target}' has been restored to active.{RESET}")
                    continue

                elif cmd == "/status":
                    print(f"\n  {CYAN}{BOLD}🔍 Workspace Status — agent/{session_name}{RESET}")
                    divider(CYAN)
                    res = subprocess.run(
                        ["git", "status", "--short"],
                        cwd=os.getcwd(), capture_output=True, text=True
                    )
                    output = res.stdout.strip()
                    if output:
                        for line in output.splitlines():
                            marker = line[:2]
                            filename = line[2:]
                            if "M" in marker:
                                print(f"    {YELLOW}● Modified: {RESET}{filename}")
                            elif "A" in marker or "??" in marker:
                                print(f"    {GREEN}✚ Created:  {RESET}{filename}")
                            elif "D" in marker:
                                print(f"    {RED}🗑 Deleted:  {RESET}{filename}")
                            else:
                                print(f"    {GRAY}  {line}{RESET}")
                    else:
                        print(f"    {GREEN}✔ Workspace clean — nothing to commit.{RESET}")
                    divider(CYAN)
                    continue

                elif cmd in ["/discard", "/reset"]:
                    confirm = input(f"\n  {RED}{BOLD}⚠ Discard all changes since last checkpoint? (y/n): {RESET}").strip().lower()
                    if confirm == "y":
                        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=os.getcwd(), capture_output=True)
                        subprocess.run(["git", "clean", "-fd"], cwd=os.getcwd(), capture_output=True)
                        # Inject failure warning into agent memory so it doesn't repeat the mistake
                        warning = HumanMessage(
                            content=(
                                "[SYSTEM] The user has discarded all your recent file changes — "
                                "they were broken or did not meet expectations. The workspace has been "
                                "reverted to the last checkpoint. Do NOT repeat the same approach. "
                                "Try a completely different strategy or library."
                            )
                        )
                        await graph.aupdate_state(config, {"messages": [warning]})
                        print(f"\n  {GREEN}✔ Workspace reverted. Agent memory has been notified.{RESET}")
                    else:
                        print(f"  {GRAY}Discard cancelled.{RESET}")
                    continue

                elif cmd == "/log":
                    print(f"\n  {CYAN}{BOLD}📜 Checkpoint History — agent/{session_name}{RESET}")
                    divider(CYAN)
                    res = subprocess.run(
                        ["git", "log", f"agent/{session_name}", "--oneline", "-n", "10"],
                        cwd=os.getcwd(), capture_output=True, text=True
                    )
                    log = res.stdout.strip()
                    if log:
                        for line in log.splitlines():
                            sha, _, msg = line.partition(" ")
                            print(f"    {BLUE}{sha}{RESET}  {GRAY}{msg}{RESET}")
                    else:
                        print(f"    {GRAY}No checkpoints yet on this branch.{RESET}")
                    divider(CYAN)
                    continue

                elif cmd == "/merge" and len(parts) >= 2:
                    source = parts[1]
                    if not tree_manager.branch_exists(source):
                        print(f"\n  {RED}⚠ Branch '{source}' does not exist.{RESET}")
                        continue
                    print(f"\n  {CYAN}🔀 Merging 'agent/{source}' → 'agent/{session_name}'...{RESET}")
                    res = subprocess.run(
                        ["git", "merge", f"agent/{source}"],
                        cwd=os.getcwd(), capture_output=True, text=True
                    )
                    if res.returncode == 0:
                        print(f"  {GREEN}✔ Merge successful!{RESET}")
                    else:
                        print(f"\n  {RED}⚠ Merge conflict detected.{RESET}")
                        print(f"  {GRAY}{res.stdout or res.stderr}{RESET}")
                        print(f"  {YELLOW}Resolve conflicts in your editor, then run: git add . && git commit{RESET}")
                    continue

                else:
                    print(f"\n  {RED}⚠ Unknown command or missing arguments.{RESET}")
                    print(f"  {GRAY}Usage: /branches | /branch <name> <desc> | /checkout <name> | /archive <name> | /restore <name> | /prune <name> | /status | /discard | /log | /merge <name>{RESET}")
                    continue

            await run_turn(
                graph, {"messages": [HumanMessage(content=user_input)]}, config
            )


if __name__ == "__main__":
    asyncio.run(main())
