from chatbot.nodes.llm import LLM
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

llm_instance = LLM()

@tool
async def code_generator(task: str):
    """
    A specialized tool that generates Python code to fulfill complex tasks. 
    Pass the user's task description as the 'task' argument.
    """
    print(f"\n[STATUS] AI is generating code for task: {task}...")
    
    system_prompt = (
        "You are an expert Python developer. Generate valid, complete, and functional Python code based on the user's request. "
        "Do not truncate the code. Provide the FULL script. "
        "Return ONLY the raw code. Do not include markdown formatting or explanations."
    )
    
    # We pass the task as a human message to the internal LLM call
    from langchain_core.messages import HumanMessage
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=task)]
    
    code_output = await llm_instance.generate(messages)
    clean_code = code_output.replace("```python", "").replace("```", "").strip()
    
    return clean_code
