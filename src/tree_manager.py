import json
import os
import subprocess
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BRANCHES_FILE = os.path.join(DATA_DIR, "branches.json")
PROJECT_ROOT = os.path.dirname(DATA_DIR)


def _ensure_file():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(BRANCHES_FILE):
        _save({"default": {"parent": None, "status": "active"}})


def _load() -> dict:
    _ensure_file()
    try:
        with open(BRANCHES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(BRANCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


# ── Git-backed metadata ────────────────────────────────────────────────────────

def get_branch_description(branch_name: str) -> str:
    """Reads the branch summary from git config."""
    res = _run_git(["config", f"branch.agent/{branch_name}.description"])
    return res.stdout.strip() if res.returncode == 0 else ""


def set_branch_description(branch_name: str, description: str):
    """Stores the branch summary in git config."""
    _run_git(["config", f"branch.agent/{branch_name}.description", description])


def get_branch_created_at(branch_name: str) -> str:
    """Gets the timestamp of the first commit on this branch."""
    res = _run_git([
        "log", f"agent/{branch_name}",
        "--format=%ai", "--reverse", "--max-count=1"
    ])
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else "unknown"


# ── Branch CRUD ───────────────────────────────────────────────────────────────

def get_branches() -> dict:
    """Returns all branches with their slim metadata."""
    return _load()


def get_branch(branch_name: str) -> dict | None:
    return _load().get(branch_name)


def branch_exists(branch_name: str) -> bool:
    return branch_name in _load()


def create_branch(branch_name: str, parent: str | None, summary: str):
    """Creates a new branch entry and stores its description in git config."""
    branches = _load()
    branches[branch_name] = {
        "parent": parent,
        "status": "active",
    }
    _save(branches)
    if summary:
        set_branch_description(branch_name, summary)


def set_status(branch_name: str, status: str):
    branches = _load()
    if branch_name in branches:
        branches[branch_name]["status"] = status
        _save(branches)


def archive_branch(branch_name: str):
    set_status(branch_name, "archived")


def restore_branch(branch_name: str):
    set_status(branch_name, "active")


def delete_branch(branch_name: str):
    branches = _load()
    if branch_name in branches:
        del branches[branch_name]
        _save(branches)
    # Also remove git config description
    _run_git(["config", "--unset", f"branch.agent/{branch_name}.description"])
