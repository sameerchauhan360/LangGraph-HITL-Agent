"""
Snapshot Manager
================
Handles file-system snapshotting for the branching system.

Strategy: MOVE-based (not copy-based)
- Active branch's files live in the PROJECT ROOT (tracked paths)
- Inactive branches' files live in data/snapshots/<branch_name>/
- Switching branches = MOVE current files out → MOVE target files in
- This is instant on the same drive (just a metadata rename)

.agentignore: defines patterns for files that should NOT be tracked,
using the same gitignore wildmatch syntax.
"""

import os
import shutil
import pathspec


# ── Paths ─────────────────────────────────────────────────────────────────────
_SRC_DIR = os.path.dirname(__file__)                       # src/
PROJECT_ROOT = os.path.dirname(_SRC_DIR)                   # project root
SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, "data", "snapshots")
AGENTIGNORE = os.path.join(PROJECT_ROOT, ".agentignore")


def _load_spec() -> pathspec.PathSpec:
    """Load .agentignore patterns. Returns an empty spec if file doesn't exist."""
    if not os.path.exists(AGENTIGNORE):
        return pathspec.PathSpec.from_lines("gitwildmatch", [])
    with open(AGENTIGNORE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _get_tracked_files(spec: pathspec.PathSpec) -> list[str]:
    """
    Walk the project root and return relative paths of all tracked files
    (i.e., files not matched by .agentignore patterns).
    """
    tracked = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Compute relative path of current directory
        rel_root = os.path.relpath(root, PROJECT_ROOT)

        # Prune ignored directories in-place to avoid walking into them
        dirs[:] = [
            d for d in dirs
            if not spec.match_file(
                (os.path.join(rel_root, d) + "/").replace("\\", "/")
            )
        ]

        for file in files:
            if rel_root == ".":
                rel_path = file
            else:
                rel_path = os.path.join(rel_root, file)
            rel_path_posix = rel_path.replace("\\", "/")

            if not spec.match_file(rel_path_posix):
                tracked.append(rel_path)
    return tracked


def save_snapshot(branch_name: str) -> int:
    """
    MOVE all tracked files from the project root into data/snapshots/<branch_name>/.
    Returns the number of files moved.
    """
    spec = _load_spec()
    tracked = _get_tracked_files(spec)

    if not tracked:
        return 0

    branch_snapshot = os.path.join(SNAPSHOT_DIR, branch_name)
    os.makedirs(branch_snapshot, exist_ok=True)

    # Track which directories we touched during the move
    affected_dirs: set[str] = set()

    for rel_path in tracked:
        src = os.path.join(PROJECT_ROOT, rel_path)
        dst = os.path.join(branch_snapshot, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        # Record all parent directories of this file
        parts = rel_path.replace("\\", "/").split("/")
        for i in range(1, len(parts)):
            affected_dirs.add(os.path.join(PROJECT_ROOT, *parts[:i]))

    # Only remove directories that WE emptied — sorted deepest first
    for dir_path in sorted(affected_dirs, key=lambda p: p.count(os.sep), reverse=True):
        if os.path.isdir(dir_path) and not os.listdir(dir_path):
            os.rmdir(dir_path)

    return len(tracked)


def restore_snapshot(branch_name: str) -> int:
    """
    MOVE all files from data/snapshots/<branch_name>/ back to the project root.
    Returns the number of files restored. If no snapshot exists, returns 0.
    """
    branch_snapshot = os.path.join(SNAPSHOT_DIR, branch_name)
    if not os.path.exists(branch_snapshot):
        return 0

    count = 0
    for root, dirs, files in os.walk(branch_snapshot):
        for file in files:
            src = os.path.join(root, file)
            rel_path = os.path.relpath(src, branch_snapshot)
            dst = os.path.join(PROJECT_ROOT, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            count += 1

    # Clean up the now-empty snapshot dir
    shutil.rmtree(branch_snapshot, ignore_errors=True)
    return count


def switch_snapshot(from_branch: str, to_branch: str) -> tuple[int, int]:
    """
    Save the current branch's files and restore the target branch's files.
    Returns (files_saved, files_restored).
    """
    saved = save_snapshot(from_branch)
    restored = restore_snapshot(to_branch)
    return saved, restored


def copy_snapshot(from_branch: str, to_branch: str):
    """
    Copies the snapshot of from_branch to to_branch.
    Used when creating a new child branch — the child inherits the parent's files.
    Does NOT affect the actual project files.
    """
    src_dir = os.path.join(SNAPSHOT_DIR, from_branch)
    dst_dir = os.path.join(SNAPSHOT_DIR, to_branch)

    if not os.path.exists(src_dir):
        return  # Parent has no snapshot yet, child starts empty

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)

    shutil.copytree(src_dir, dst_dir)


def snapshot_exists(branch_name: str) -> bool:
    """Returns True if a snapshot exists for the given branch."""
    path = os.path.join(SNAPSHOT_DIR, branch_name)
    return os.path.isdir(path) and bool(os.listdir(path))


def delete_snapshot(branch_name: str):
    """Permanently removes the snapshot directory for a branch."""
    path = os.path.join(SNAPSHOT_DIR, branch_name)
    if os.path.exists(path):
        shutil.rmtree(path)

