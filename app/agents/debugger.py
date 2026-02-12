import re
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger

# ---------------------------------------------------------------------
# 1. HYBRID PROMPT (CoT + Knowledge Base)
# ---------------------------------------------------------------------
debugger_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior QA & Debugging Engineer at AutoDev AI.
    
    **Goal:** Fix ALL errors in the provided code based on the Test Output.
    
    **CRITICAL INSTRUCTION: Chain of Thought**
    You MUST think before you code. Do not just guess.
    1.  **Analyze**: Read the error log. Match it against your Knowledge Base below.
    2.  **Plan**: Describe the fix step-by-step.
    3.  **Execute**: Write the corrected code.

    **Knowledge Base (Common Fixes):**
    1.  **Error:** `ArgumentError: ... includes dataclasses argument(s): 'default_factory'`
        -   **Fix:** SQLAlchemy `mapped_column` does NOT accept `default_factory`. Change it to `default=...` or remove it.
    
    2.  **Error:** `TypeError: Client.__init__() got an unexpected keyword argument 'app'`
        -   **Fix:** The installed `httpx` version is too new. Downgrade to `httpx==0.25.2` in `requirements.txt`.
    
    3.  **Error:** `fixture 'mocker' not found`
        -   **Fix:** Add `pytest-mock` to `requirements.txt`.
        
    4.  **Error:** `pydantic_core.ValidationError` (Field required)
        -   **Fix:** Ensure a `.env` file exists with the required variables.
    
    **Output Format:**
    Return the response in this exact XML structure:
    
    <plan>
    1. The error "ModuleNotFoundError: httpx" matches Knowledge Base item #2.
    2. I will add 'httpx==0.25.2' to requirements.txt.
    3. I will also verify imports in tests/test_main.py.
    </plan>
    
    <file path="requirements.txt">
    fastapi
    httpx==0.25.2
    pytest
    </file>
    
    **Rules:**
    - Return the FULL content of any file you modify.
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
        # Skip binary/lock files
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
        
        # 4. Merge Updates
        new_files = {**existing_files, **fixed_files}
        
        return {
            "files": new_files,
            "debug_iterations": state["debug_iterations"] + 1
        }
        
    except Exception as e:
        logger.error(f"❌ Debugger failed: {e}")
        return {"debug_iterations": state["debug_iterations"] + 1}