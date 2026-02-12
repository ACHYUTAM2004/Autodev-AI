import re
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger

# ---------------------------------------------------------------------
# ROBUST PROMPT
# ---------------------------------------------------------------------
debugger_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior QA & Debugging Engineer at AutoDev AI.
    
    **Goal:** Fix the failing code based on the Test Output.
    
    **Input Context:**
    - **Files:** The current file contents.
    - **Error:** The error log from the Tester Agent.
    
    **Knowledge Base (Common Fixes):**
    1.  **Error:** `ArgumentError: ... includes dataclasses argument(s): 'default_factory'`
        -   **Fix:** SQLAlchemy `mapped_column` does NOT accept `default_factory`. Change it to `default=...` or remove it.
    
    2.  **Error:** `TypeError: Client.__init__() got an unexpected keyword argument 'app'`
        -   **Fix:** The installed `httpx` version is too new. Downgrade to `httpx==0.25.2` in `requirements.txt`.
    
    3.  **Error:** `fixture 'mocker' not found`
        -   **Fix:** Add `pytest-mock` to `requirements.txt`.
        
    4.  **Error:** `pydantic_core.ValidationError` (Field required)
        -   **Fix:** Ensure a `.env` file exists with the required variables.

    **Instructions:**
    -   Analyze the error log.
    -   Return the CORRECTED file content.
    -   If the error is in `requirements.txt` (missing dependency), return the updated `requirements.txt`.
    
    **Output Format:**
    Return ONLY the corrected file(s) in XML format:
    
    <file path="src/models.py">
    ... (corrected code) ...
    </file>
    """),
    ("user", """
    Files: {existing_files}
    
    Test Output (Error Log):
    {test_output}
    """)
])

# ---------------------------------------------------------------------
# PARSING HELPER
# ---------------------------------------------------------------------
def parse_debugger_output(text: str) -> Dict[str, str]:
    """Extracts fixed files from XML-style output."""
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    # Sanitize escaped newlines (common LLM bug)
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        # Clean up quotes if wrapped
        content = content.strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        files[path] = content
        
    return files

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
def debugger_agent(state: AgentState):
    logger.info(f"--- DEBUGGER AGENT: Fixing {state['user_input'].get('project_name')} ---")
    
    user_req = state["user_input"]
    existing_files = state.get("files", {})
    test_results = state.get("test_results", {})
    
    # 1. Prepare File Context (Stringify the files)
    file_context_str = ""
    for path, content in existing_files.items():
        # Skip binary or irrelevant files to save tokens
        if not path.endswith((".lock", ".png", ".jpg", ".pyc", ".zip")):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    llm = get_llm(temperature=0.1)
    chain = debugger_prompt | llm 
    
    try:
        response = chain.invoke({
            # --- FIX: Match the variable name in the prompt ---
            "existing_files": file_context_str[:50000],  # Was "file_context"
            "test_output": test_results.get("output", "No logs available.")
        })
        
        # Parse the XML output to get the fixed files
        # (Reusing the same parser from Coder Agent logic if available, 
        # or a simple regex parser here)
        from app.agents.tester import parse_tester_output 
        # Note: We can reuse the tester/coder parser since the format is the same XML
        
        # For robustness, let's use a local parsing similar to Coder
        import re
        fixed_files = {}
        # Parse XML: <file path="...">...</file>
        pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
        matches = re.findall(pattern, response.content, re.DOTALL)
        
        for path, content in matches:
            # Clean up content (remove markdown fences if LLM added them)
            content = content.replace("```python", "").replace("```", "").strip()
            fixed_files[path] = content
            
        # Merge fixed files into existing files
        new_files = {**existing_files, **fixed_files}
        
        return {
            "files": new_files,
            "debug_iterations": state["debug_iterations"] + 1
        }
        
    except Exception as e:
        logger.error(f"Debugger failed: {e}")
        return {"debug_iterations": state["debug_iterations"] + 1}