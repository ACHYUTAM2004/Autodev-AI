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
    
    **Goal:** Fix ALL errors in the provided code to make EVERY test pass.
    This is debug iteration {debug_iteration} of maximum 2. You MUST fix everything NOW.
    
    **CRITICAL INSTRUCTION: DEEP REASONING (Chain of Thought)**
    You must output a `<plan>` tag before writing code. Inside the plan:
    1.  **Quote**: Copy EVERY distinct error message from the logs (not just the first one).
    2.  **Root Cause**: For EACH error, explain why it is happening.
    3.  **Cascading Impact**: After fixing Error #1, what NEW errors will be revealed? Fix those too.
    4.  **Strategy**: Detail the specific steps to fix ALL errors at once.
    
    **CRITICAL INSTRUCTION: FIXING "BLINDNESS"**
    - The Coder might have forgotten to create essential files.
    - **IF A FILE IS MISSING, CREATE IT.**
    - Common missing files: `tests/conftest.py`, `.env`, `pytest.ini`, `tests/__init__.py`.
    - Do not complain that a file is missing. Just output the `<file path="...">` tag with the new content.
    
    **EXPANDED ERROR TAXONOMY (MEMORIZE THIS):**
    For each error type, apply the EXACT fix pattern:
    
    | Error Pattern | Root Cause | Fix |
    |---|---|---|
    | `ModuleNotFoundError: No module named 'X'` | Missing from requirements.txt OR wrong import path | Add to requirements.txt AND verify the import path matches the directory structure |
    | `ImportError: cannot import name 'Y' from 'X'` | Y doesn't exist in module X (typo or wrong module) | Check the actual exports of module X, fix the import |
    | `AttributeError: 'X' object has no attribute 'Y'` | Method/property doesn't exist on that class | Check class definition, fix the attribute name or add missing method |
    | `TypeError: X() got an unexpected keyword argument 'Y'` | Function signature doesn't match the call | Align function parameters with call sites |
    | `422 Unprocessable Entity` | Request body doesn't match Pydantic schema | Fix the test request payload OR the Pydantic schema |
    | `404 Not Found` | Route not registered, wrong URL path, or httpx base_url wrong | Check `app.include_router()`, route prefix, and test client `base_url` |
    | `ScopeMismatch` | Function-scoped fixture depends on session-scoped | Make all related fixtures the same scope |
    | `fixture 'X' not found` | Missing conftest.py or fixture not defined there | Create/fix conftest.py with the fixture |
    | `sqlalchemy.exc.OperationalError` | DB tables not created or wrong DB URL | Ensure `create_all()` runs before tests with correct engine |
    | `RuntimeError: Event loop is closed` | Async test teardown issue | Use `pytest-asyncio` with correct scope, use `@pytest_asyncio.fixture` |
    | `AssertionError: assert 200 == 201` | Wrong status code returned by endpoint | Check endpoint return, ensure `status_code=201` for POST/create |
    | `pydantic.errors.PydanticUserError` | Using Pydantic V1 syntax with V2 | Use `ConfigDict`, `model_validate`, `from_attributes=True` |
    | `assert None is not None` on `tzinfo` | SQLite strips timezone info from `DateTime(timezone=True)` | Remove `tzinfo` assertions in tests using SQLite, or use naive datetime comparisons |
    | `assert 'url/' == 'url'` (trailing slash) | Pydantic `HttpUrl` normalizes URLs (adds trailing `/`) | Compare against `str(HttpUrl(...))` normalized form, not raw input |
    | `assert 307 == 404` | FastAPI `redirect_slashes=True` (default) causes 307 redirect | Set `FastAPI(redirect_slashes=False)` or fix test expectations |
    | `IntegrityError: UNIQUE constraint failed` | Test transaction isolation broken — `commit()` persists across tests | Use proper nested transaction pattern: connection → begin → bind session → rollback |
    | Unhandled `Exception` causes raw 500 | Utility raises `Exception`, endpoint doesn't catch it as `HTTPException` | Wrap utility calls in try/except, raise `HTTPException(status_code=500)` |
    
    **FULL ERROR CASCADE ANALYSIS (MANDATORY):**
    After identifying and fixing the first error:
    1. Mentally re-run ALL tests with your fix applied.
    2. Ask: "Does fixing Error #1 unmask Error #2?" (e.g., fixing an import error lets the
       test run further, but then a fixture error appears).
    3. Ask: "Does my fix INTRODUCE any new errors?" (e.g., fixing a schema might break
       a different test that relied on the old schema).
    4. Continue until you are confident ALL tests will pass.
    
    **FILE DEPENDENCY GRAPH (BUILD THIS INTERNALLY):**
    Before writing fixes, mentally map:
    - main.py → imports routers → each router imports models, schemas, db
    - conftest.py → imports app → uses AsyncClient with app
    - test_*.py → imports conftest fixtures → calls API endpoints
    
    Verify EVERY edge in this graph is satisfied by the files you output.
    
    **CONSISTENCY VALIDATION (MANDATORY BEFORE OUTPUT):**
    Before outputting files, verify ALL of these:
    - [ ] requirements.txt includes every imported third-party package
    - [ ] Every `from X import Y` resolves to an actual file and symbol
    - [ ] async tests use `pytest-asyncio` and `asyncio_mode = auto` in pytest.ini
    - [ ] conftest.py fixtures match the app structure (correct import path, correct DB setup)
    - [ ] Environment variables in code match those in .env
    - [ ] DB URLs in test conftest are separate from production .env
    - [ ] All router prefixes match what tests expect
    - [ ] All Pydantic schemas use V2 syntax (ConfigDict, from_attributes)
    - [ ] Every `await` is on an async function, every async function is awaited
    - [ ] No circular imports exist

    **COMPLETENESS GATE (FINAL CHECK):**
    Before outputting your response, count:
    1. Number of DISTINCT errors in the test log: N
    2. Number of errors your fixes address: M
    3. If M < N, you are NOT done. Go back and fix the remaining errors.
    4. Verify no NEW errors are introduced by your changes.
    
    **Minimal Diff Discipline:**
    - Modify only what is necessary to fix errors.
    - Do not rewrite entire files unless the file is fundamentally broken.
    - Preserve existing working logic.
    - BUT: if a file needs multiple small fixes, output the FULL corrected file.

    **ITERATION AWARENESS:**
    Debug iteration: {debug_iteration} of 2.
    - If this is iteration 1: Be thorough but focused.
    - If this is iteration 2: This is your LAST CHANCE. Be maximally aggressive — fix EVERYTHING,
      even things that look like they might be fine. Better to over-fix than to miss something.
    
    **Output Format:**
    Return the response in this exact XML structure:
    
    <plan>
    1. Error: "Fixture 'mocker' not found".
    2. Cause: Missing pytest-mock dependency.
    3. Strategy: Add pytest-mock to requirements.txt.
    4. Cascade: After fixing this, test_X.py will run further and hit...
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
    --- DEBUG ITERATION: {debug_iteration} of 2 ---
    
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
    llm = get_llm(temperature=0.0) 
    chain = debugger_prompt | llm 
    
    try:
        response = chain.invoke({
            "existing_files": file_context_str[:60000], 
            "test_output": test_results.get("output", "No logs available.")[-20000:],
            "debug_iteration": state.get("debug_iterations", 0) + 1
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