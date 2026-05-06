# LangGraph HITL Agent

A persistent terminal-based AI assistant built on LangGraph. Features include dynamic JSON task decomposition, stateful execution with SQLite, live text streaming, and Human-in-the-Loop (HITL) approval for arbitrary Python code execution and web search.

## Features
- **JSON Task Planner:** Automatically breaks down complex goals into a structured, trackable checklist.
- **Stateful Execution:** Remembers context and checklist status across turns using a SQLite checkpointer.
- **Human-in-the-Loop (HITL):** Pauses execution to request user approval before running potentially unsafe actions (like arbitrary Python code).
- **Rich Terminal UI:** Formatted status updates and a clean checklist display.
- **Tools:** Includes safe local code execution (file access, browser automation) and web search via Tavily.

## Setup

1. Create a Python virtual environment and install your requirements.
2. Create a `.env` file in the root directory based on the following template:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   TAVILY_API_KEY=your_tavily_api_key
   ```
   *(Note: The code is currently configured to point to an NVIDIA OpenAI-compatible endpoint. Modify the `ChatOpenAI` base URL in `src/chatbot/nodes/agent.py` and `planner.py` if using standard OpenAI).*

3. Run the agent:
   ```bash
   python src/main.py
   ```

## Architecture
- `src/main.py`: The entry point, handles the terminal UI, streaming, and SQLite persistence.
- `src/chatbot/graph.py`: Defines the LangGraph workflow and conditional routing logic.
- `src/chatbot/nodes/`: Contains the `planner` and `agent` nodes.
- `src/chatbot/tools/`: Contains the tools available to the agent (`executor_tool`, `websearch`, etc.).
