# 🛠️ Extending Your Agent with Git CLI Commands & Hybrid Memory

This document outlines the design and implementation for adding the **4 new Git CLI commands** and the **Hybrid Memory Reset** logic that we discussed.

All of these can be added directly into your existing `src/main.py` command-parsing loop.

---

## 📋 Table of Contents
1. [Command Integration Blueprint](#-command-integration-blueprint)
2. [Detailed Code Implementations](#-detailed-code-implementations)
   * [/status](#1-status)
   * [/discard](#2-discard-hybrid-memory)
   * [/merge](#3-merge)
   * [/log](#4-log)
3. [Updating the Main Command Switchboard](#-updating-the-main-command-switchboard)

---

## 🗺️ Command Integration Blueprint

Your current `main.py` parses user commands starting with `/` at line ~277:
```python
if user_input.startswith("/"):
    parts = user_input.split(" ", 2)
    cmd = parts[0].lower()
```

We can plug our new commands directly into this switchboard. By doing so, your chatbot terminal transitions from a simple chat interface into a powerful Git-backed workspace controller.

---

## 🛠️ Detailed Code Implementations

Below are the exact code blocks to handle each new command.

### 1. `/status`
Displays a concise summary of modified, created, or deleted files on the current active agent branch.

```python
elif cmd == "/status":
    print(f"\n  {CYAN}{BOLD}🔍 Workspace Status ({session_name}){RESET}")
    divider(CYAN)
    
    # Run: git status --short
    res = subprocess.run(
        ["git", "status", "--short"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True
    )
    
    status_output = res.stdout.strip()
    if status_output:
        # Highlight status markers (M = Modified, A = Added, D = Deleted, ?? = Untracked)
        for line in status_output.splitlines():
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
        print(f"    {GREEN}✔ Workspace perfectly clean. No pending changes.{RESET}")
    divider(CYAN)
    continue
```

---

### 2. `/discard` (with Hybrid Memory Injection 🏆)
Wipes uncommitted modifications and untracked files from disk, then **injects a system notification** into the agent's memory so it remembers its failure and doesn't repeat the mistake.

```python
elif cmd in ["/discard", "/reset"]:
    confirm = input(f"\n  {RED}{BOLD}⚠ Are you sure you want to discard all changes since the last checkpoint? (y/n): {RESET}").strip().lower()
    if confirm == "y":
        print(f"  {GRAY}[Resetting workspace...]{RESET}")
        
        # 1. Reset all modified files
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=os.getcwd(), capture_output=True)
        # 2. Delete all new untracked files/directories
        subprocess.run(["git", "clean", "-fd"], cwd=os.getcwd(), capture_output=True)
        
        # 3. Inject rollback notification into LangGraph state history
        # This prevents the "Memory Loop" where the agent forgets it failed and repeats the bug!
        reset_notification = HumanMessage(
            content=(
                "[SYSTEM WARNING] The user has discarded all your recent file modifications "
                "because they were broken or failed to meet expectations. The codebase files have "
                "been reverted to the last checkpoint. Please do NOT repeat the same approach — try "
                "a completely different design, library, or strategy."
            )
        )
        await graph.aupdate_state(config, {"messages": [reset_notification]})
        
        print(f"\n  {GREEN}✔ Workspace reverted. Agent memory notified of the reset!{RESET}")
    else:
        print(f"  {GRAY}Discard cancelled.{RESET}")
    continue
```

---

### 3. `/merge <branch_name>`
Merges the completed work from an experimental branch into the currently active branch.

```python
elif cmd == "/merge" and len(parts) >= 2:
    source_branch = parts[1]
    
    # Simple check if target branch exists
    if not tree_manager.branch_exists(source_branch):
        print(f"\n  {RED}⚠ Branch '{source_branch}' does not exist.{RESET}")
        continue
        
    print(f"\n  {CYAN}🔀 Merging 'agent/{source_branch}' into current branch...{RESET}")
    
    # Run: git merge agent/<source_branch>
    res = subprocess.run(
        ["git", "merge", f"agent/{source_branch}"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True
    )
    
    if res.returncode == 0:
        print(f"  {GREEN}✔ Successfully merged '{source_branch}' into '{session_name}'!{RESET}")
    else:
        print(f"\n  {RED}⚠ Merge conflict detected!{RESET}")
        print(f"  {GRAY}Git output:{RESET}\n{res.stderr or res.stdout}")
        print(f"  {YELLOW}Please open your editor (e.g. VS Code) to resolve the merge conflict.{RESET}")
    continue
```

---

### 4. `/log`
Displays a clean timeline of previous checkpoints/saves on the current branch.

```python
elif cmd == "/log":
    print(f"\n  {CYAN}{BOLD}📜 Checkpoint History ({session_name}){RESET}")
    divider(CYAN)
    
    # Run: git log --oneline -n 5
    res = subprocess.run(
        ["git", "log", f"agent/{session_name}", "--oneline", "-n", "5"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True
    )
    
    log_output = res.stdout.strip()
    if log_output:
        for line in log_output.splitlines():
            parts = line.split(" ", 1)
            sha = parts[0]
            message = parts[1] if len(parts) > 1 else ""
            print(f"    {BLUE}{sha}{RESET} {GRAY}— {message}{RESET}")
    else:
        print(f"    {GRAY}No checkpoints found on this branch yet.{RESET}")
    divider(CYAN)
    continue
```

---

## 🚦 Updating the Main Command Switchboard

To make sure users understand they have these powerful new tools at their disposal, you should update the instruction text on startup inside your `main` function (around line ~212 in `main.py`):

```python
# Update this in main.py so it lists the new commands!
divider()
print(f"  {DIM}Commands: 'history' · 'quit' · '/status' · '/discard' · '/merge <branch>' · '/log'{RESET}")
divider()
```

And update your unknown command fallback help block (around line ~397 in `main.py`):

```python
else:
    print(f"\n  {RED}⚠ Unknown command or missing arguments.{RESET}")
    print(f"  {GRAY}Usage: /branches | /branch <name> <desc> | /checkout <name> | /archive <name> | /status | /discard | /merge <branch> | /log{RESET}")
    continue
```
