import sys
import io
import os
from langchain_core.tools import tool
from langgraph.types import interrupt

@tool
def code_executor(code: str) -> str:
    """
    Executes arbitrary Python code directly on the host machine and returns the standard output.

    CRITICAL REQUIREMENTS:
    1. COMPLETE CODE: Always provide fully self-contained, runnable scripts. Include all necessary imports.
    2. USE CASES: Use for ANY of the following:
       - File system operations (READ/WRITE/DELETE)
       - Complex calculations or data processing
       - Browser automation: `import webbrowser; webbrowser.open('https://youtube.com/...')`
       - Playing/opening YouTube videos: use webbrowser or playwright
       - Opening URLs, launching applications, controlling the OS
       - Installing packages: `import subprocess; subprocess.run([sys.executable, '-m', 'pip', 'install', 'X'])`
    3. PATH HANDLING: Use absolute paths or os.path.join(os.getcwd(), ...) for file persistence.
    4. SYSTEM ACCESS: This tool has FULL access to the local machine. Browser control, file access,
       and internet requests are ALL permitted. Never refuse to write code for these tasks.

    Args:
        code (str): The valid Python source code string to be executed.
    """
    # HITL: pause inside the tool and ask for human approval
    decision = interrupt({
        "message": "Review this code before execution:",
        "code": code,
    })

    if decision != "approve":
        return "Code execution was cancelled by the user. Do not retry automatically — ask the user if they want to try again or try a different approach."

    from rich import print as rprint
    rprint("\n  [dim magenta]⚡ [bold]Executing code...[/bold][/dim magenta]")
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout

    try:
        exec(code, {"__builtins__": __builtins__})
        output = new_stdout.getvalue()
        cwd = os.getcwd()
        return f"Execution successful!\nWorking directory: {cwd}\nOutput:\n{output}" if output else f"Execution successful! (Working directory: {cwd})"
    except Exception as e:
        return f"Execution failed: {str(e)}"
    finally:
        sys.stdout = old_stdout
