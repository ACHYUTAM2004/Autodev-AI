import re
from typing import Union, List
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger

# ---------------------------------------------------------------------
# 1. STANDARD PROMPT (No Self-Correction)
# ---------------------------------------------------------------------
coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior Full-Stack Developer at AutoDev AI.
    
    **Goal:** Write production-ready, clean, and SECURE code based on the Architect's plan.
    
    **Input Context:**
    - **Stack:** {tech_stack}
    - **Architecture:** {architecture}
    - **Plan:** {plan}
    
    **STRICT RULES:**
    
    1.  **Dependency Safety (GOLDEN STACK):**
        -   You MUST pin these EXACT versions in `requirements.txt` to ensure stability and compatibility:
            `fastapi==0.109.2`
            `uvicorn==0.27.1`
            `pydantic==2.6.1`
            `pydantic-settings==2.1.0`
            `sqlalchemy==2.0.27`
            `aiosqlite==0.19.0`
            `httpx==0.27.0`
            `pytest==8.0.0`
            `pytest-asyncio==0.23.5` (Critical for 'auto' mode)
            `pytest-mock==3.12.0`
        
    2.  **Configuration & Security:**
        -   NEVER hardcode secrets. Use `os.getenv()`.
        -   **YOU MUST generate a `.env` file** with default development values.
        -   **YOU MUST generate a `pytest.ini` file** containing exactly:
            ```ini
            [pytest]
            asyncio_mode = auto
            python_files = test_*.py
            ```
        
    3.  **Testing Readiness:**
        -   If creating a `tests/` folder, YOU MUST include an empty `<file path="tests/__init__.py"></file>`.
        -   In `tests/conftest.py`, use `pytest_asyncio` fixtures if the app is async.
        
    4.  **File Formatting:**
        -   Do NOT use escaped newlines (\\n) inside the code string. Write actual newlines.
     
    5.  **SQLAlchemy 2.0 Compliance (CRITICAL):**
        -   Use `Mapped[type]` and `mapped_column()`.
        -   **NEVER** use `default_factory` inside `mapped_column()`.
        -   Use `default=datetime.now` (Python-side) or `server_default=func.now()` (DB-side).
     
    6.  **Pre-Flight Quality Checklist (MANDATORY INTERNAL THINKING):**
        Before outputting any files, you MUST internally verify:

        - All imports exist and match requirements.txt.
        - No unused imports.
        - No circular imports.
        - Async functions use async/await correctly.
        - Dependency injection matches FastAPI standards.
        - Database sessions are properly opened and closed.
        - All routers are included in main app.
        - No missing __init__.py where packages are used.
        - Tests (if present) will not fail due to fixture or DB setup mismatch.

        Think step-by-step internally, but DO NOT output the reasoning.
        Only output final corrected files.

    7.  **Test Anticipation Mode:**
        Write code as if strict Pytest tests already exist.
        Assume tests will check:
        - Correct HTTP status codes
        - Validation errors
        - Edge cases (empty input, invalid ID)
        - Async execution correctness
        - Database persistence

    8.  **Minimal Surface Area Principle:**
        - Do not generate unnecessary files.
        - Do not introduce extra dependencies.
        - Keep implementation simple and deterministic.

    9.  **Zero-Assumption Rule:**
        If something is not specified in the plan, implement the safest minimal version.

    10. **Pydantic V2 Compliance:**
        -   Use `model_config = ConfigDict(...)` instead of `class Config:`.
        -   Use `model_validate` instead of `parse_obj`.
        -   Use `RootModel` instead of `__root__`.

    
    **Output Format:**
    Return the file content wrapped in XML tags exactly like this:
    
    <file path="src/main.py">
    from fastapi import FastAPI
    ...
    </file>
    
    <file path=".env">
    DATABASE_URL=sqlite+aiosqlite:///./dev.db
    </file>
    
    <file path="requirements.txt">
    fastapi==0.109.2
    httpx==0.27.0
    ...
    </file>
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Constraints: {constraints}
    """)
])

# ---------------------------------------------------------------------
# 2. PARSING & SANITIZATION HELPER
# ---------------------------------------------------------------------
def sanitize_content(content: str) -> str:
    """Cleans up common LLM formatting errors."""
    content = content.strip()
    
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
    elif content.startswith("'") and content.endswith("'"):
        content = content[1:-1]
        
    if "\\n" in content and "\n" not in content:
        logger.warning("Detected escaped newlines in single-line output. Fixing...")
        content = content.replace("\\n", "\n")
        
    return content

def parse_xml_output(text: Union[str, List]) -> dict:
    """Extracts file paths and content using Regex."""
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        files[path] = sanitize_content(content)
        
    return files

# ---------------------------------------------------------------------
# 3. AGENT FUNCTION (Reverted to Standard)
# ---------------------------------------------------------------------
def coder_agent(state: AgentState):
    user_req = state["user_input"]
    plan = state.get("plan", [])
    tech_decisions = state.get("tech_decisions", {})
    
    logger.info(f"--- CODER AGENT: Writing code for {user_req.get('project_name')} ---")

    # Context Variables
    stack_str = f"{tech_decisions.get('language', 'Python')} using {tech_decisions.get('framework', 'FastAPI')}"
    arch_str = f"Database: {tech_decisions.get('database', 'SQLite')}, Auth: {tech_decisions.get('auth', 'None')}"
    plan_str = "\n".join(plan) if isinstance(plan, list) else str(plan)
    
    # Invoke LLM
    llm = get_llm(temperature=0.0) 
    chain = coder_prompt | llm 
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {}),
            "tech_stack": stack_str,
            "architecture": arch_str,
            "plan": plan_str
        })

        files_dict = parse_xml_output(response.content)
        
        if not files_dict:
            logger.warning("Coder Agent produced no files. Raw output snippet:")
            raw = response.content
            if isinstance(raw, list): raw = "".join(str(x) for x in raw)
            logger.warning(raw[:500])
        
        logger.info(f"Coder generated {len(files_dict)} files.")
        
        # Return files only (Iteration logic handled elsewhere)
        return {
            "files": files_dict
        }
        
    except Exception as e:
        logger.error(f"Error in Coder Agent: {e}")
        return {"errors": [f"Coder Agent failed: {str(e)}"]}