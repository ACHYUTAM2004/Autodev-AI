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
    ("system", """You are the Senior Debugger at AutoDev AI.
    
    **Goal:** Fix the code based on the provided Test Execution Logs.
    
    **Input Context:**
    1. **Project:** {project_name}
    2. **Test Output:** {test_output} (Contains errors/failures)
    3. **Source Code:** {file_context}
    
    **Your Task:**
    1. Analyze the error trace (e.g., ImportErrors, AssertionErrors, SyntaxErrors).
    2. Identify which file needs fixing.
    3. Rewrite the *entire* file with the fix applied.
    
    **Output Format:**
    Return the fixed file(s) wrapped in XML tags:
    
    <file path="src/main.py">
    ... (full fixed code) ...
    </file>
    
    **Rules:**
    - ONLY return the files that need changes.
    - Return the FULL content of the fixed file, not just a diff.
    - Do not change logic that is already working.
    """),
    ("user", """
    Project: {project_name}
    
    --- TEST EXECUTION LOGS ---
    {test_output}
    
    --- CURRENT FILES ---
    {file_context}
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
    test_results = state.get("test_results", {})
    existing_files = state.get("files", {})
    
    # 1. Prepare Context
    # Limit logs to last 2000 chars to focus on the immediate error
    error_log = test_results.get("output", "")
    if len(error_log) > 5000:
        error_log = "..." + error_log[-5000:]
        
    file_context_str = ""
    for path, content in existing_files.items():
        if not path.endswith((".lock", ".png", ".pyc")):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    # 2. Invoke LLM
    llm = get_llm(temperature=0.1) # Low temp for precision
    chain = debugger_prompt | llm
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "test_output": error_log,
            "file_context": file_context_str[:30000] # Context window limit
        })
        
        # 3. Parse Fixes
        fixed_files = parse_debugger_output(response.content)
        
        if not fixed_files:
            logger.warning("Debugger Agent suggested no changes.")
            return {"files": existing_files} # No changes made
            
        logger.info(f"Debugger fixed {len(fixed_files)} files: {list(fixed_files.keys())}")
        
        # 4. Merge Fixes
        updated_files = {**existing_files, **fixed_files}
        
        # Get current iteration count
        current_iter = state.get("debug_iterations", 0)
        
        return {
            "files": updated_files,
            "debug_iterations": current_iter + 1  # <--- MUST INCREMENT THIS
        }

    except Exception as e:
        logger.error(f"Error in Debugger Agent: {e}")
        return {"errors": [f"Debugger failed: {str(e)}"]}