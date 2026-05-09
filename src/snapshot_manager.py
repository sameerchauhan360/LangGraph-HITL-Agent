"""
Git-Based Snapshot Manager
==========================
Handles file-system snapshotting using the local Git repository.

Each agent timeline maps 1-to-1 with a local Git branch: `agent/<branch_name>`.
- Switching branches = git checkout (atomic, instant, OS-level safe)
- Saving state      = git add -A && git commit (auto-checkpoint)
- Respects .gitignore natively — no separate .agentignore needed
"""

import subprocess
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in the project root."""
    return subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_branch(branch_name: str) -> str:
    """Returns the full git branch name for an agent timeline."""
    return f"agent/{branch_name}"


def _has_changes() -> bool:
    """Returns True if there are any uncommitted changes in the workspace."""
    res = _run_git(["status", "--porcelain"], check=False)
    return bool(res.stdout.strip())


# ── Core Operations ────────────────────────────────────────────────────────────

def save_snapshot(branch_name: str) -> int:
    """
    Stages all workspace changes and commits them as a checkpoint.
    Returns 1 if a checkpoint was committed, 0 if the workspace was already clean.
    """
    try:
        if not _has_changes():
            return 0
        _run_git(["add", "-A"])
        _run_git(["commit", "-m", f"agent: checkpoint for '{branch_name}'"])
        return 1
    except Exception as e:
        print(f"  [Git Error] Failed to save checkpoint: {e}")
        return 0


def restore_snapshot(branch_name: str) -> int:
    """
    Switches the workspace to the target agent branch.
    Returns 1 on success, 0 on failure.
    """
    try:
        _run_git(["checkout", _git_branch(branch_name)])
        return 1
    except Exception as e:
        print(f"  [Git Error] Failed to switch to '{branch_name}': {e}")
        return 0


def switch_snapshot(from_branch: str, to_branch: str) -> tuple[int, int]:
    """
    Commits current workspace changes, then checks out the target branch.
    Returns (saved=0/1, restored=0/1).
    """
    saved = save_snapshot(from_branch)
    restored = restore_snapshot(to_branch)
    return saved, restored


def copy_snapshot(from_branch: str, to_branch: str):
    """
    Commits the current branch, then creates a new child branch from it.
    The new branch inherits all files and history of from_branch.
    Also switches the workspace to the new branch immediately.
    """
    try:
        # Commit any pending changes on the parent branch first
        save_snapshot(from_branch)
        # Create and immediately checkout the new branch from the parent
        _run_git(["checkout", "-b", _git_branch(to_branch), _git_branch(from_branch)])
    except Exception as e:
        print(f"  [Git Error] Failed to create branch '{to_branch}' from '{from_branch}': {e}")


def snapshot_exists(branch_name: str) -> bool:
    """Returns True if the git branch agent/<branch_name> exists locally."""
    try:
        _run_git(["show-ref", "--verify", f"refs/heads/{_git_branch(branch_name)}"])
        return True
    except subprocess.CalledProcessError:
        return False


def delete_snapshot(branch_name: str):
    """Permanently deletes the git branch for this timeline."""
    try:
        _run_git(["branch", "-D", _git_branch(branch_name)])
    except Exception as e:
        print(f"  [Git Error] Failed to delete branch '{branch_name}': {e}")


def create_initial_branch(branch_name: str) -> bool:
    """
    Creates the initial agent branch from the current HEAD (main).
    Only used on first-ever startup when agent/default doesn't exist yet.
    """
    try:
        _run_git(["checkout", "-b", _git_branch(branch_name)])
        # Make an empty initial commit so the branch has a history root
        _run_git(["commit", "--allow-empty", "-m", f"agent: initial workspace for '{branch_name}'"])
        return True
    except Exception as e:
        print(f"  [Git Error] Failed to create initial branch '{branch_name}': {e}")
        return False


def current_git_branch() -> str:
    """Returns the current active git branch name (full name, e.g. 'agent/default')."""
    try:
        res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return res.stdout.strip()
    except Exception:
        return ""
