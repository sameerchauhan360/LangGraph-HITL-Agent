# LangGraph HITL Agent

A persistent, terminal-based AI assistant built on LangGraph with **branching timelines**, **file-system snapshots**, and **human-in-the-loop** control. The agent can plan, reason, execute code, search the web — and lets you explore multiple independent lines of thought simultaneously.

---

## Features

### 🤖 Core Agent
- **JSON Task Planner** — Automatically decomposes complex goals into a structured, trackable checklist shown live in the terminal.
- **Stateful Execution** — Remembers context and plan status across sessions using a SQLite checkpointer (via LangGraph's `AsyncSqliteSaver`).
- **Live Streaming** — Responses stream token-by-token to the terminal.
- **Human-in-the-Loop (HITL)** — Pauses before executing any code or search, shows you exactly what it's about to do, and asks for approval (`y/n`).

### 🌿 Branching Timelines
- Create independent **parallel timelines** from any point in a conversation.
- Each timeline has its own isolated **conversation memory** (via separate LangGraph thread IDs).
- New timelines **inherit** the full conversation context of the parent at the moment of branching.
- Timelines are purely independent after creation — no cascading rules.
- A **fork tree** is maintained for visualization (so you can see what knowledge each timeline inherited), but it imposes no behavioral constraints.

### 📸 File-System Snapshots
- When you switch timelines, the agent **moves** your workspace files in and out — each timeline has its own isolated file state.
- Uses `.agentignore` (same syntax as `.gitignore`) to define which files and folders are tracked.
- On exit (`quit` or `Ctrl+C`), files are automatically saved to the current timeline's snapshot.
- On startup, the previous snapshot is automatically restored.

### 🧠 Auto-Summarization
- When conversation history exceeds **20 messages**, older messages are automatically summarized by the LLM into a single context block.
- The summary is persisted back into the LangGraph state — so summarization only happens once per threshold crossing, not on every turn.
- Always keeps the last **10 messages** verbatim for precise recent context.

### 🛠️ Tools
- **Code Executor** — Safely runs Python code with user approval. Supports file I/O, pip installs, and general scripting.
- **Web Search** — Searches the web via Tavily with a per-session search budget.

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

> **Note:** The agent is configured to use an OpenAI-compatible endpoint. To use a different provider, update the `base_url` in `src/chatbot/nodes/llm.py`.

### 3. Run the agent

```bash
python src/main.py
# or
uv run src/main.py
```

---

## Commands

Once inside the agent, you can use these system commands in addition to chatting:

| Command | Description |
|---|---|
| `history` | Show full conversation history for the current timeline |
| `quit` / `exit` | Save snapshot and exit |
| `/branches` | List all timelines with their status and fork tree |
| `/branch <name> <desc>` | Create a new timeline forked from the current one |
| `/checkout <name>` | Switch to a different timeline (saves current, restores target) |
| `/archive <name>` | Mark a timeline as archived (hidden but not deleted) |
| `/restore <name>` | Restore an archived timeline back to active |
| `/prune <name>` | Permanently delete a timeline and its snapshot |

---

## File-System Snapshot: `.agentignore`

The `.agentignore` file in the project root defines which files are **not** tracked by the snapshot system. It uses the same wildmatch syntax as `.gitignore`.

By default, the following are excluded:
- Agent infrastructure: `src/`, `data/snapshots/`, `data/branches.json`
- Python environment: `.venv/`, `__pycache__/`, `*.pyc`
- Version control: `.git/`
- Sensitive files: `.env`
- Build artifacts: `*.lock`, `*.toml`
- Database files: `*.db`, `*.db-shm`, `*.db-wal`

Any files the agent **creates** (scripts, outputs, downloaded data, etc.) that don't match these patterns are fully tracked and isolated per timeline.

---

## Project Structure

```
src/
├── main.py                  # Entry point: terminal UI, streaming, branching commands
├── tree_manager.py          # Branch metadata (branches.json read/write)
├── snapshot_manager.py      # File-system snapshot engine (.agentignore + move/restore)
└── chatbot/
    ├── graph.py             # LangGraph workflow and routing logic
    ├── state.py             # AgentState definition
    └── nodes/
    │   ├── agent.py         # Main reasoning node with auto-summarization
    │   ├── planner.py       # Task decomposition node
    │   └── llm.py           # LLM client configuration
    └── tools/
        ├── executor_tool.py # HITL code execution tool
        └── websearch.py     # Tavily web search tool

data/
├── branches.json            # Timeline metadata (name, parent, status, created_at)
└── snapshots/               # Per-timeline file snapshots
    ├── default/
    ├── mcp/
    └── ...

.agentignore                 # Defines files excluded from snapshot tracking
```

---

## How Branching Works

```
default  ──── /branch mcp "explore MCP protocol"
                   │
                   ├── mcp  ──── /branch deep-dive "go deeper on X"
                   │                  └── deep-dive
                   │
                   └── back on default, working independently
```

- Each node in the fork tree represents a **snapshot of knowledge** at the moment of branching.
- The tree is purely informational — it tells you what a timeline knew at birth.
- After branching, all timelines are fully independent.
- `/checkout` saves your current files and conversation, then restores the target timeline's files and conversation.
