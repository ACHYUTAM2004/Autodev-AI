import re
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger

# ---------------------------------------------------------------------
# 1. SUPERCHARGED PROMPT (CoT + Blindness Fix)
# ---------------------------------------------------------------------
debugger_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior AI Software Architect and Debugging Lead at AutoDev AI.
    
    **Goal:** Fix ALL errors in the provided code to make the tests pass.
    
    **CRITICAL INSTRUCTION: DEEP REASONING (Chain of Thought)**
    You must output a `<plan>` tag before writing code. Inside the plan:
    1.  **Quote**: Copy the specific error message from the logs.
    2.  **Root Cause**: Why is this happening? (e.g., "Test expects 404 but got 200", "Missing dependency", "Fixture scope mismatch").
    3.  **Strategy**: Detail the specific steps to fix it.
    
    **CRITICAL INSTRUCTION: FIXING "BLINDNESS"**
    - The Coder might have forgotten to create essential files.
    - **IF A FILE IS MISSING, CREATE IT.**
    - Common missing files: `tests/conftest.py`, `.env`, `pytest.ini`, `tests/__init__.py`.
    - Do not complain that a file is missing. Just output the `<file path="...">` tag with the new content.
    
    **KNOWLEDGE BASE (Common Pitfalls):**
    1.  **ScopeMismatch (Pytest):** If you see "You tried to access the function scoped fixture mocker...", you MUST change your fixture scope or use `session_mocker` from `pytest-mock`.
    2.  **404 vs 200 (FastAPI):** If tests fail with 404, check if `httpx` is hitting the correct base URL or if the DB was reset correctly in `conftest.py`.
    3.  **Missing Dependencies:** If `ModuleNotFoundError`, check `requirements.txt`.
    4.  **Pydantic V2:** Use `model_validate` instead of `from_orm`.
    
    **Output Format:**
    Return the response in this exact XML structure:
    
    <plan>
    1. Error: "Fixture 'mocker' not found".
    2. Cause: Missing pytest-mock dependency.
    3. Strategy: Add pytest-mock to requirements.txt.
    </plan>
    
    <file path="requirements.txt">
    fastapi
    pytest-mock
    </file>
    
    **Rules:**
    - Return the FULL content of any file you modify or create.
    - Do not use markdown blocks (```python) inside the XML tags.
    """),
    ("user", """
    --- PROJECT FILES ---
    {existing_files}
    
    --- TEST FAILURE LOG ---
    {test_output}
    """)
])

# ---------------------------------------------------------------------
# 2. ROBUST PARSING HELPER
# ---------------------------------------------------------------------
def parse_debugger_output(text: str) -> Dict[str, str]:
    """Extracts plan and fixed files from XML-style output."""
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    # Sanitize escaped newlines (common LLM bug)
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    # 1. Extract and Log the Plan (For visibility)
    plan_match = re.search(r'<plan>(.*?)</plan>', text, re.DOTALL)
    if plan_match:
        plan_content = plan_match.group(1).strip()
        logger.info(f"🧠 DEBUGGER PLAN:\n{plan_content}")

    # 2. Extract Files
    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        content = content.strip()
        # Remove markdown code fences if the LLM accidentally added them
        content = re.sub(r'^```[a-z]*\n', '', content)
        content = re.sub(r'\n```$', '', content)
        
        # Unescape common quote issues
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
            
        files[path] = content
        
    return files

# ---------------------------------------------------------------------
# 3. AGENT FUNCTION
# ---------------------------------------------------------------------
def debugger_agent(state: AgentState):
    logger.info(f"--- DEBUGGER AGENT: Fixing {state['user_input'].get('project_name')} ---")
    
    existing_files = state.get("files", {})
    test_results = state.get("test_results", {})
    
    # 1. Prepare Context
    file_context_str = ""
    for path, content in existing_files.items():
        # Skip binary/lock files to save tokens
        if not path.endswith((".lock", ".png", ".jpg", ".pyc", ".zip", "package-lock.json")):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    # 2. Invoke LLM
    llm = get_llm(temperature=0.1) 
    chain = debugger_prompt | llm 
    
    try:
        response = chain.invoke({
            "existing_files": file_context_str[:60000], 
            "test_output": test_results.get("output", "No logs available.")[-20000:] 
        })
        
        # 3. Parse Output
        fixed_files = parse_debugger_output(response.content)
        
        if not fixed_files:
            logger.warning("⚠️ Debugger returned no files. It might have failed to find a fix.")
        else:
            # Check for NEW files (Blindness Fix verification)
            new_paths = set(fixed_files.keys()) - set(existing_files.keys())
            if new_paths:
                logger.info(f"✨ Debugger CREATED new files: {new_paths}")
        
        # 4. Merge Updates (This logic handles both edits AND creations)
        new_files = {**existing_files, **fixed_files}
        
        return {
            "files": new_files,
            "debug_iterations": state["debug_iterations"] + 1
        }
        
    except Exception as e:
        logger.error(f"❌ Debugger failed: {e}")
        return {"debug_iterations": state["debug_iterations"] + 1}