from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger
import re

# ---------------------------------------------------------------------
# REVIEWER PROMPT
# ---------------------------------------------------------------------
reviewer_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior Code Reviewer at AutoDev AI.

    **Goal:** Review the code for Style, Security, and Best Practices.

    **Input Context:**
    - **Project:** {project_name}
    - **Source Code:** {file_context}

    **Your Task:**
    1.  **Analyze** the code for:
        -   **Security:** (e.g., Hardcoded API keys/passwords).
        -   **Style:** (e.g., Bad variable names, lack of docstrings).
        -   **Best Practices:** (e.g., Unused imports, massive functions, missing main guards).
    2.  **Refactor** the code to fix these issues.

    **Output Format:**
    Return the **improved** files wrapped in XML tags:

    <file path="src/main.py">
    ... (full improved code) ...
    </file>

    **Rules:**
    -   Do NOT change the core logic (don't break functionality).
    -   ONLY return files that you modified.
    -   If a file is perfect, do not return it.
    """),
    ("user", """
    Project: {project_name}

    --- SOURCE CODE ---
    {file_context}
    """)
])

# ---------------------------------------------------------------------
# PARSING HELPER
# ---------------------------------------------------------------------
def parse_reviewer_output(text: str):
    """Extracts improved files using Robust XML Strategy."""
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    # Sanitize escaped newlines
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        content = content.strip()
        # Remove wrapping quotes if LLM added them
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        files[path] = content
        
    return files

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
def reviewer_agent(state: AgentState):
    logger.info(f"--- REVIEWER AGENT: Reviewing {state['user_input'].get('project_name')} ---")

    user_req = state["user_input"]
    existing_files = state.get("files", {})

    # Prepare Context
    file_context_str = ""
    for path, content in existing_files.items():
        if not path.endswith((".lock", ".png", ".pyc")):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    llm = get_llm(temperature=0.1)
    chain = reviewer_prompt | llm 

    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "file_context": file_context_str[:30000]
        })

        improved_files = parse_reviewer_output(response.content)

        if not improved_files:
            logger.info("Reviewer Agent passed all files (No changes needed).")
            return {
                "files": existing_files, 
                "review_report": "✅ Code Quality Pass: No issues found." # <--- Update
            }

        logger.info(f"Reviewer improved {len(improved_files)} files: {list(improved_files.keys())}")

        # Merge improvements
        updated_files = {**existing_files, **improved_files}
        
        # Create Report
        report_msg = f"⚠️ Issues Found & Fixed.\nRefactored {len(improved_files)} files: {', '.join(improved_files.keys())}"
        
        return {
            "files": updated_files,
            "review_report": report_msg  # <--- Update
        }

    except Exception as e:
        logger.error(f"Error in Reviewer Agent: {e}")
        return {
            "files": existing_files,
            "review_report": f"❌ Reviewer Failed: {str(e)}"
        }