import re
from typing import Union, List
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger

# ---------------------------------------------------------------------
# ROBUST PROMPT (XML-STYLE)
# ---------------------------------------------------------------------
coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior Full-Stack Developer at AutoDev AI.
    
    **Goal:** Write production-ready, clean, and SECURE code based on the Architect's plan.
    
    **Input Context:**
    - **Stack:** {tech_stack}
    - **Plan:** {plan}
    
    **STRICT RULES (You will be penalized for breaking these):**
    
    1.  **Dependency Safety:**
        -   If using **FastAPI**, you MUST pin `httpx==0.25.2` in `requirements.txt` (newer versions break TestClient).
        -   If using **Pytest**, you MUST include `pytest-mock` and `pytest-asyncio`.
        -   If using **SQLAlchemy**, you MUST include `aiosqlite` (for async SQLite) or `asyncpg` (for Postgres).
        
    2.  **Configuration & Security:**
        -   NEVER hardcode secrets. Use `os.getenv()`.
        -   **YOU MUST generate a `.env` file** with default development values.
        -   Example .env content: `DATABASE_URL=sqlite+aiosqlite:///./test.db`, `SECRET_KEY=dev-secret-key`.
        
    3.  **Testing Readiness:**
        -   If creating a `tests/` folder, YOU MUST include an empty `<file path="tests/__init__.py"></file>`.
        -   In `tests/conftest.py`, use `pytest_asyncio` fixtures if the app is async.
        
    4.  **File Formatting:**
        -   Do NOT use escaped newlines (\\n) inside the code string. Write actual newlines.
        -   Do NOT include comments like `` inside Python files.
     
    5.  **SQLAlchemy 2.0 Compliance (CRITICAL):**
        -   Use `Mapped[type]` and `mapped_column()`.
        -   **NEVER** use `default_factory` inside `mapped_column()`. It is NOT supported.
        -   Use `default=datetime.now` (Python-side) or `server_default=func.now()` (DB-side).
        -   Do NOT mix Pydantic `Field(...)` logic into SQLAlchemy Models.
    
    **Output Format:**
    Return the file content wrapped in XML tags exactly like this:
    
    <file path="src/main.py">
    from fastapi import FastAPI
    ...
    </file>
    
    <file path=".env">
    DATABASE_URL=sqlite+aiosqlite:///./dev.db
    SECRET_KEY=dev-key
    </file>
    
    <file path="requirements.txt">
    fastapi
    uvicorn
    sqlalchemy
    aiosqlite
    pydantic-settings
    pytest
    pytest-mock
    pytest-asyncio
    httpx==0.25.2
    </file>
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Constraints: {constraints}
    """)
])

# ---------------------------------------------------------------------
# PARSING & SANITIZATION HELPER
# ---------------------------------------------------------------------
def sanitize_content(content: str) -> str:
    """Cleans up common LLM formatting errors."""
    content = content.strip()
    
    # 1. Remove wrapping quotes if the LLM added them (e.g., "import os...")
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
    elif content.startswith("'") and content.endswith("'"):
        content = content[1:-1]
        
    # 2. Fix escaped newlines (The "requirements.txt" fix)
    # If the content contains literal "\n" but NO actual newlines, it's a single-line mess.
    if "\\n" in content and "\n" not in content:
        logger.warning("Detected escaped newlines in single-line output. fixing...")
        content = content.replace("\\n", "\n")
        
    return content

def parse_xml_output(text: Union[str, List]) -> dict:
    """Extracts file paths and content using Regex."""
    # Handle list input (Gemini quirk)
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    # Regex to find <file path="...">CONTENT</file>
    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        files[path] = sanitize_content(content)
        
    return files

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
def coder_agent(state: AgentState):
    logger.info(f"--- CODER AGENT: Writing code for {state['user_input'].get('project_name')} ---")
    
    user_req = state["user_input"]
    plan = state.get("plan", [])
    tech_decisions = state.get("tech_decisions", {})
    
    stack_str = f"{tech_decisions.get('language', 'Python')} using {tech_decisions.get('framework', 'FastAPI')}"
    arch_str = f"Database: {tech_decisions.get('database', 'SQLite')}, Auth: {tech_decisions.get('auth', 'None')}"
    
    plan_str = "\n".join(plan) if isinstance(plan, list) else str(plan)
    
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
        return {"files": files_dict}
        
    except Exception as e:
        logger.error(f"Error in Coder Agent: {e}")
        return {"errors": [f"Coder Agent failed: {str(e)}"]}