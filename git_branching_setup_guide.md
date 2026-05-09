# 🌿 Git-Based Branching Migration & Setup Guide

This guide walks you through migrating your terminal-based LangGraph assistant from the fragile directory-moving snapshot manager (`shutil.move`) to a **native, robust Git-based branching system**.

By switching to this architecture, each chatbot branch maps 1-to-1 to a real, local Git branch prefixed with `agent/`. This ensures OS-level file safety, blazing-fast transitions, and full support for native git merges and logs.

---

## 📋 Table of Contents
1. [Migration Steps](#-migration-steps)
2. [How the Code Changes](#-how-the-code-changes)
3. [Testing Your New System](#-testing-your-new-system)
4. [Advanced Workflows: Merging Changes](#-advanced-workflows-merging-changes)
5. [Frequently Asked Questions](#-frequently-asked-questions)

---

## 🚀 Migration Steps

Follow these 4 simple steps to upgrade your repository:

### Step 1: Clean Up Old Snapshots (Optional)
Since we are moving away from folder-based snapshots, you can safely delete the legacy backup directories:
```bash
# Delete old snapshot folder to clean up your workspace
rm -rf data/snapshots/
```

### Step 2: Replace `src/snapshot_manager.py`
Open `src/snapshot_manager.py` and replace its entire contents with the updated Git-based code below. 

This code replaces ~166 lines of directory walking with standard Python `subprocess` calls to your local Git installation.

*(See the full code in the [How the Code Changes](#-how-the-code-changes) section below.)*

### Step 3: Delete `.agentignore` (Use `.gitignore` instead!)
The new system automatically respects your project's `.gitignore` file. You no longer need to maintain a separate `.agentignore` file!
```bash
# Delete the redundant ignore file
rm .agentignore
```
Make sure your standard `.gitignore` contains temporary data files and database files so they aren't committed to your Git branches:
```gitignore
# Ensure these are in your .gitignore
chat_history.db
chat_history.db-shm
chat_history.db-wal
data/branches.json
.env
.venv/
__pycache__/
```

### Step 4: Ensure Your Git Repository is Initialized
Before running the agent, make sure your project is initialized as a Git repository and has an initial commit:
```bash
# Initialize git if you haven't already
git init

# Stage and make an initial commit of your project files
git add .
git commit -m "chore: initial commit before agent branching"
```

---

## 🛠️ How the Code Changes

Here is the complete, high-performance, and drop-in code for **`src/snapshot_manager.py`**:

```python
"""
Git-Based Snapshot Manager
==========================
Handles file-system snapshotting using the local Git repository.

Each agent timeline/branch lives on a Git branch named `agent/<branch_name>`.
This avoids physical file-moving hazards, integrates beautifully with
developer workflows, and leverages Git's lightning-fast C-engine.
"""

import subprocess
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    """Helper to run a git command in the project root."""
    return subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True
    )


def _has_changes() -> bool:
    """Checks if there are any uncommitted changes in the workspace."""
    # --porcelain returns empty output if there are no changes
    res = _run_git(["status", "--porcelain"])
    return bool(res.stdout.strip())


def save_snapshot(branch_name: str) -> int:
    """
    Stages all workspace changes and commits them as a checkpoint.
    Returns 1 if a checkpoint was committed, 0 if nothing changed.
    """
    try:
        if not _has_changes():
            return 0

        # 1. Stage all changes (respects .gitignore automatically!)
        _run_git(["add", "-A"])

        # 2. Commit the checkpoint
        _run_git(["commit", "-m", f"agent: checkpoint auto-save for '{branch_name}'"])
        return 1
    except Exception as e:
        print(f"  [Git Error] Failed to save snapshot: {e}")
        return 0


def restore_snapshot(branch_name: str) -> int:
    """
    Switches the workspace files to the target agent branch.
    """
    try:
        git_branch = f"agent/{branch_name}"
        _run_git(["checkout", git_branch])
        return 1
    except Exception as e:
        print(f"  [Git Error] Failed to checkout branch '{branch_name}': {e}")
        return 0


def switch_snapshot(from_branch: str, to_branch: str) -> tuple[int, int]:
    """
    Commit current workspace changes, then checkout the target branch.
    Returns (saved=0/1, restored=0/1).
    """
    saved = save_snapshot(from_branch)
    restored = restore_snapshot(to_branch)
    return saved, restored


def copy_snapshot(from_branch: str, to_branch: str):
    """
    Creates a new branch branching from the parent branch.
    """
    try:
        # Save any changes in from_branch first
        save_snapshot(from_branch)

        # Create and checkout the new branch
        parent_git = f"agent/{from_branch}"
        new_git = f"agent/{to_branch}"
        _run_git(["checkout", "-b", new_git, parent_git])
    except Exception as e:
        print(f"  [Git Error] Failed to copy snapshot from '{from_branch}' to '{to_branch}': {e}")


def snapshot_exists(branch_name: str) -> bool:
    """Returns True if the git branch exists locally."""
    try:
        git_branch = f"agent/{branch_name}"
        # Checks if ref exists in local heads
        _run_git(["show-ref", "--verify", f"refs/heads/{git_branch}"])
        return True
    except subprocess.CalledProcessError:
        return False


def delete_snapshot(branch_name: str):
    """Permanently deletes the git branch."""
    try:
        git_branch = f"agent/{branch_name}"
        # Force-delete the branch (-D)
        _run_git(["branch", "-D", git_branch])
    except Exception as e:
        print(f"  [Git Error] Failed to delete branch '{branch_name}': {e}")
```

---

## 🧪 Testing Your New System

Start your agent in your terminal:
```bash
python src/main.py
```

Now, run through this test checklist to verify your setup:

1. **Check your branches:** 
   Type `/branches` to see your initial `default` branch in the terminal.
2. **Create an agent branch:**
   Type `/branch experiment-1 "trying to add an api key"`
   *Behind the scenes, Git has created and checked out `agent/experiment-1`.*
3. **Have the bot write code:**
   Tell the agent: *"create a file named `hello.py` that prints 'Hello World'"*. Let it run the python code to write the file.
4. **Checkout default:**
   Type `/checkout default`.
   *Notice that `hello.py` instantly vanishes from your VS Code workspace! Git has safely committed it to `agent/experiment-1` and restored your default clean state.*
5. **Checkout back:**
   Type `/checkout experiment-1`.
   *`hello.py` instantly reappears!*

---

## 🌿 Advanced Workflows: Merging Changes

If your agent successfully implements a feature or solves a bug on a branch (e.g., `agent/experiment-1`) and you want to merge it back into your principal code branch (e.g., `main` or `master`):

### 1. Close your agent session
Exit your terminal assistant by typing `quit`. This ensures all your active changes are committed to the local `agent/experiment-1` branch.

### 2. Merge via command line
Switch to your main repository branch and run a merge:
```bash
# Checkout your principal main branch
git checkout main

# Merge the agent's work
git merge agent/experiment-1
```

### 3. Handle Conflicts (If Any)
If you made changes to the same files while the agent was working, Git might prompt you with a merge conflict. Open the files in VS Code, select which changes to keep, and run:
```bash
git add .
git commit -m "merge: integrated agent/experiment-1 changes"
```

---

## ❓ Frequently Asked Questions

#### Q: Will this clutter my public GitHub commit graph?
**No.** All of these `agent/` branches, commits, and switches are strictly **local** to your laptop/desktop. Unless you explicitly run `git push origin agent/<name>`, absolutely nothing is visible on GitHub.

#### Q: What if the agent goes into an infinite loop and makes 1,000 commits?
Because Git uses highly compressed binary storage (loose objects and packfiles), local commits are extremely lightweight. However, if you want to clean up your history, you can easily delete old agent branches with `/prune <name>` or `git branch -D agent/<name>`.

#### Q: Can I run this while a local dev-server is running?
**Yes!** However, because Git swaps files instantly on disk, your dev-server (like React, Next.js, or FastAPI) might hot-reload immediately upon checkout. This is a massive feature, but keep it in mind if you switch branches while a server is listening!
