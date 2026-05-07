# 🚀 Proposed Pending Features

These feature suggestions are carefully curated for your stateful terminal-based AI assistant. They are highly feasible to implement within your current Python/LangGraph architecture, make strong conceptual sense, and will drastically improve the developer experience.

---

### 1. 🔌 Model Context Protocol (MCP) Client
Enable the agent to connect to any MCP Server (local or remote) to fetch dynamic tools on the fly.
- **Why it's useful**: Instead of writing custom tools for every database, API, or service (such as GitHub, Slack, Brave Search, or SQLite), the agent can plug directly into the fast-growing open-source MCP ecosystem.
- **How it would work**:
  - A `/mcp connect <url_or_command>` CLI command.
  - The client queries the MCP server's schemas, compiles them into LangChain-compatible `StructuredTool` objects, and dynamically binds them to the LLM node on startup.
- **Feasibility**: **High** (the `mcp` Python SDK is lightweight and easy to integrate).

---

### 2. 🪓 Containerized Sandboxed Execution
Run python execution scripts in a lightweight, isolated Docker container or restricted sandbox instead of directly on your host machine.
- **Why it's useful**: Running code on your native OS is risky and forces you to micro-manage every prompt via HITL. Sandboxing provides absolute safety. It allows the agent to run testing, compiling, and data-processing tasks fully autonomously without nagging you for minor operations.
- **How it would work**:
  - When the agent triggers `code_executor`, the system runs a temporary Docker container, mounts a temp copy of the workspace, executes the script, and returns the stdout.
  - Dangerous commands are contained inside the disposable sandbox.
- **Feasibility**: **High** (using the standard `docker` Python client library).

---

### 3. 🧠 Cross-Timeline Semantic Memory (Vector DB)
A shared, long-term knowledge base that persists across different branching timelines.
- **Why it's useful**: Right now, if the agent solves a complex bug in `branch_A`, that knowledge is completely lost if you switch to `branch_B`. A shared vector database allows the agent to save key facts (e.g., *"Learned that library X has a bug where Y must be initialized first"*) and search them semantically across all branches.
- **How it would work**:
  - Incorporate a local vector store like `chromadb` or `lancedb` (running side-by-side with your SQLite DB).
  - Provide a `remember` tool that embeds notes, and a background mechanism that retrieves contextually similar notes based on the current prompt.
- **Feasibility**: **High** (no external server required, runs entirely locally in memory/disk).

---

### 4. 🧪 Self-Correction & Verification Node (Critique Loop)
An automated syntax and import check node that intercepts code *before* it is shown to the user.
- **Why it's useful**: Saves you from rejecting code due to trivial python syntax errors or missing library imports.
- **How it would work**:
  - Introduce a `validator` node in the LangGraph flow between `agent` and `human_approval`.
  - The validator runs the proposed script through an AST check (`ast.parse`) or a quick linter check. If it fails, the graph redirects back to the agent with a traceback, correcting the code autonomously before you ever see it.
- **Feasibility**: **Extremely High** (purely python-logic-based).

---

### 5. 🛠️ Dynamic Tool Learning (Self-Improving Agent)
Allow the agent to dynamically build, test, and register its own permanent custom tools.
- **Why it's useful**: If the agent notices you are asking it to repeat a task (e.g., converting CSV to JSON, resizing images, fetching logs), it can write a specialized Python tool, place it in a local directory, and register it so it is available forever.
- **How it would work**:
  - The agent writes a standard Python file with a `@tool` decorator into a `src/chatbot/tools/learned/` folder.
  - On startup (or via a `/reload` command), `main.py` uses `importlib` to scan this directory and auto-load any new tools.
- **Feasibility**: **Medium-High** (requires dynamic module loading).

---

### 6. ⏳ Background Task Execution (Non-Blocking Tools)
Allow tools that take a long time (e.g. scraping 50 pages, running heavy test suites, running server compiles) to run asynchronously in the background.
- **Why it's useful**: You don't have to wait for the agent to finish execution to continue talking. You can chat, change branches, or read files while a background compilation or scrape is running.
- **How it would work**:
  - An async tool execution queue.
  - The terminal main loop uses `asyncio.create_task` to let the tool run in the background, while keeping the user input prompt alive and active.
  - When the background task finishes, it posts a live desktop/terminal notification.
- **Feasibility**: **Medium-High** (requires adjustments to the asyncio prompt loop).
