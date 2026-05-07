import json
import os
from datetime import datetime

# Path to the JSON file where branch metadata is stored
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BRANCHES_FILE = os.path.join(DATA_DIR, "branches.json")


def _ensure_file():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not os.path.exists(BRANCHES_FILE):
        # Initialize with the default branch
        initial_data = {
            "default": {
                "parent": None,
                "summary": "Main timeline",
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
        }
        _save(initial_data)


def _load() -> dict:
    _ensure_file()
    try:
        with open(BRANCHES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    """Write branch data to the JSON file. Creates the directory if needed."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(BRANCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def get_branches() -> dict:
    """Returns all branches."""
    return _load()


def get_branch(branch_name: str) -> dict | None:
    """Gets metadata for a specific branch."""
    branches = _load()
    return branches.get(branch_name)


def branch_exists(branch_name: str) -> bool:
    """Checks if a branch exists (including archived ones)."""
    return branch_name in _load()


def get_all_descendants(branch_name: str) -> list[str]:
    """Returns all descendants (children, grandchildren, etc.) of a branch."""
    branches = _load()
    descendants = []
    queue = [branch_name]
    while queue:
        current = queue.pop(0)
        children = [name for name, meta in branches.items() if meta.get("parent") == current]
        descendants.extend(children)
        queue.extend(children)
    return descendants




def create_branch(branch_name: str, parent: str | None, summary: str):
    """Creates a new active branch in the tree."""
    branches = _load()
    branches[branch_name] = {
        "parent": parent,
        "summary": summary,
        "status": "active",
        "created_at": datetime.now().isoformat()
    }
    _save(branches)


def set_status(branch_name: str, status: str):
    """Sets the lifecycle status of a branch: active | archived."""
    branches = _load()
    if branch_name in branches:
        branches[branch_name]["status"] = status
        _save(branches)


def archive_branch(branch_name: str):
    """Marks a branch as archived (non-destructive)."""
    set_status(branch_name, "archived")


def restore_branch(branch_name: str):
    """Restores an archived branch back to active."""
    set_status(branch_name, "active")


def delete_branch(branch_name: str):
    """Permanently removes a branch from the metadata file."""
    branches = _load()
    if branch_name in branches:
        del branches[branch_name]
        _save(branches)


def update_summary(branch_name: str, summary: str):
    """Updates the summary of a branch."""
    branches = _load()
    if branch_name in branches:
        branches[branch_name]["summary"] = summary
        _save(branches)
