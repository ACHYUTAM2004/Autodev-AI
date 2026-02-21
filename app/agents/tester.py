import os
import re
import sys
import time
import hashlib
import subprocess
from typing import Union, List, Dict, Tuple
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.config import settings
from app.core.logger import logger

# ---------------------------------------------------------------------
# TESTER PROMPT
# ---------------------------------------------------------------------
tester_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Test Automation Engineer for AutoDev AI.
    
    **Goal:** 1. Read the provided source code.
    2. Write thorough, deterministic unit tests that will catch real bugs.
    3. Specify the testing framework (e.g., 'pytest', 'unittest').
    
    **Test Quality Rules (CRITICAL):**
    
    1.  **Deterministic Assertions:** NEVER use weak assertions like:
        - `assert response is not None` ← USELESS
        - `assert response.status_code != 500` ← TOO WEAK
        
        ALWAYS use EXACT assertions:
        - `assert response.status_code == 201`
        - `assert data["name"] == "test_item"`
        - `assert len(data) == 1`
        - `assert "id" in data`
    
    2.  **CRUD Coverage:** For every endpoint, test:
        - **Create (POST):** Correct status code (201), response body contains created data
        - **Read (GET):** Returns 200 with correct data, returns 404 for non-existent ID
        - **Update (PUT/PATCH):** Returns updated data, returns 404 for missing
        - **Delete (DELETE):** Returns 200/204, subsequent GET returns 404
        - **Validation:** Invalid input returns 422 with error details
    
    3.  **Edge Cases (MANDATORY):**
        - Empty string inputs where strings are required
        - Non-existent IDs (e.g., ID=99999) should return 404
        - Missing required fields should return 422
        - Duplicate entries if uniqueness is implied
    
    4.  **Async Test Setup (If app is async):**
        YOU MUST generate `tests/conftest.py` with:
        - A separate test database URL (e.g., `sqlite+aiosqlite:///./test.db`)
        - `@pytest_asyncio.fixture` for the async client
        - Table creation and teardown per test session
        - `httpx.AsyncClient` with `ASGITransport` and correct `base_url="http://test"`
        
    5.  **Test Isolation:** Each test should be independent. Do not rely on test execution order.
    
    **Output Format:**
    Do NOT return JSON. Return the test files wrapped in XML-style tags:
    
    <file path="tests/test_main.py">
    import pytest
    from app.main import app
    ...
    </file>
    
    <framework>pytest</framework>
    
    **Important:** - The 'path' must be relative.
    - If testing Python, prefer 'pytest'.
    - Do NOT include installation commands.
    - **If creating a test folder, YOU MUST include an empty <file path="tests/__init__.py"></file>.**
    - **YOU MUST generate a `tests/conftest.py`** with proper async DB setup if the app uses async.
    """),
    ("user", """
    Project: {project_name}
    Tech Stack: {tech_stack}
    
    --- SOURCE CODE ---
    {file_context}
    """)
])

# ---------------------------------------------------------------------
# PARSING & SANITIZATION HELPERS
# ---------------------------------------------------------------------
def sanitize_content(content: str) -> str:
    """Cleans up common LLM formatting artifacts from generated code."""
    content = content.strip()
    
    # Remove wrapping quotes if the LLM added them (JSON style)
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
        
    # Fix literal "\\n" to actual newlines
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\n", "\n")
        
    # Unescape quotes: client.post(\'/users\') -> client.post('/users')
    content = content.replace("\\'", "'").replace('\\"', '"')
    
    return content

def parse_tester_output(text: Union[str, list]) -> Tuple[Dict[str, str], str]:
    """Robustly extracts files and framework from LLM output."""
    
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    files = {}
    framework = "pytest" 
    
    # Extract Files
    file_pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(file_pattern, text, re.DOTALL)
    for path, content in matches:
        files[path] = sanitize_content(content)
        
    # Extract Framework
    framework_pattern = r'<framework>(.*?)</framework>'
    fw_match = re.search(framework_pattern, text, re.DOTALL)
    if fw_match:
        framework = fw_match.group(1).strip()
        
    return files, framework

# ---------------------------------------------------------------------
# SMART CONTEXT BUILDER
# ---------------------------------------------------------------------
# File priority tiers for LLM context (higher priority = included first)
_HIGH_PRIORITY = (".py",)
_LOW_PRIORITY = (".txt", ".ini", ".cfg", ".env", ".toml", ".md")
_SKIP_EXTENSIONS = (".lock", ".png", ".jpg", ".jpeg", ".gif", ".pyc", ".zip", ".tar", ".gz")

def build_smart_context(files: Dict[str, str], max_chars: int = 25000) -> str:
    """
    Builds LLM context from project files with intelligent prioritization.
    
    - Prioritizes source files (.py) over config files.
    - Never truncates mid-file: either includes the full file or skips it.
    - Skips binary/lock files entirely.
    """
    high_prio = []
    low_prio = []
    
    for path, content in files.items():
        if path.endswith(_SKIP_EXTENSIONS):
            continue
        if path.endswith(_HIGH_PRIORITY):
            high_prio.append((path, content))
        else:
            low_prio.append((path, content))
    
    # Sort each tier: shorter files first (include more files within budget)
    high_prio.sort(key=lambda x: len(x[1]))
    low_prio.sort(key=lambda x: len(x[1]))
    
    context_parts = []
    remaining = max_chars
    
    for path, content in high_prio + low_prio:
        entry = f"\n--- FILE: {path} ---\n{content}\n"
        if len(entry) <= remaining:
            context_parts.append(entry)
            remaining -= len(entry)
        else:
            # Skip this file entirely rather than truncating mid-file
            logger.debug(f"Context budget exceeded, skipping: {path} ({len(entry)} chars)")
    
    return "".join(context_parts)

# ---------------------------------------------------------------------
# SUBPROCESS RUNNER
# ---------------------------------------------------------------------
def run_command(command: Union[str, List[str]], cwd: str, timeout: int = 300) -> Tuple[bool, str, str, float]:
    """
    Runs a subprocess command and returns (success, stdout, stderr, elapsed_seconds).
    Separates stdout/stderr for cleaner log handling.
    """
    try:
        cmd_str = " ".join(command) if isinstance(command, list) else command
        logger.info(f"--- EXEC: {cmd_str} in {cwd} ---")
        use_shell = isinstance(command, str)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        start = time.time()
        result = subprocess.run(
            command, cwd=cwd, shell=use_shell,
            capture_output=True, text=True, timeout=timeout, env=env
        )
        elapsed = round(time.time() - start, 2)
        
        return result.returncode == 0, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        logger.error(f"TIMEOUT after {timeout}s: {cmd_str}")
        return False, "", f"Command timed out after {timeout}s", 0.0
    except Exception as e:
        logger.error(f"SYSTEM EXECUTION ERROR: {str(e)}")
        return False, "", str(e), 0.0

# ---------------------------------------------------------------------
# CACHING HELPERS
# ---------------------------------------------------------------------
def _hash_file(filepath: str) -> str:
    """Returns MD5 hash of a file's contents, or empty string if file missing."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return ""

def _read_cached_hash(hash_path: str) -> str:
    """Reads a cached hash from a marker file."""
    try:
        with open(hash_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def _write_file_if_changed(filepath: str, content: str) -> bool:
    """
    Writes content to file ONLY if it differs from what's on disk.
    Returns True if a write was performed, False if skipped.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            if f.read() == content:
                return False  # Content identical, skip write
    except (FileNotFoundError, UnicodeDecodeError):
        pass  # File doesn't exist or can't be read — write it
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True

# ---------------------------------------------------------------------
# TEST SETUP & EXECUTION
# ---------------------------------------------------------------------
def setup_and_run_tests(
    project_name: str,
    files: Dict[str, str],
    framework: str,
    tech_stack: Dict[str, str]
) -> Tuple[bool, str]:
    """
    Sets up the project environment and executes tests.
    Optimized to skip redundant work on debug re-runs.
    """
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    os.makedirs(project_path, exist_ok=True)
    
    # ------------------------------------------------------------------
    # 1. Write Files (only changed ones)
    # ------------------------------------------------------------------
    written = 0
    skipped = 0
    for filepath, content in files.items():
        full_path = os.path.join(project_path, filepath)
        if _write_file_if_changed(full_path, content):
            written += 1
        else:
            skipped += 1
    
    logs = [f"--- Files: {written} written, {skipped} unchanged ---"]

    # ------------------------------------------------------------------
    # 2. Environment Setup
    # ------------------------------------------------------------------
    language = tech_stack.get("language", "python").lower()
    is_windows = sys.platform.startswith("win")
    success = False

    if "python" in language:
        venv_dir = os.path.join(project_path, "venv")
        if is_windows:
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        else:
            python_exe = os.path.join(venv_dir, "bin", "python")
            pip_exe = os.path.join(venv_dir, "bin", "pip")

        # A. Create venv (ONLY if it doesn't exist)
        if not os.path.exists(python_exe):
            logs.append("--- Creating Venv (First Run Only) ---")
            ok, out, err, t = run_command([sys.executable, "-m", "venv", "venv"], project_path)
            logs.append(f"  [{t}s] {err.strip() if err.strip() else 'OK'}")
            if not ok:
                return False, "\n".join(logs)
            
            # Upgrade pip once
            logs.append("--- Upgrading Pip (First Run Only) ---")
            ok, out, err, t = run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"], project_path)
            logs.append(f"  [{t}s] Done")
        else:
            logs.append("--- Venv exists, skipping creation ---")

        # B. Install requirements.txt (ONLY if it changed)
        req_path = os.path.join(project_path, "requirements.txt")
        req_hash_path = os.path.join(venv_dir, ".req_hash")
        
        if os.path.exists(req_path):
            current_hash = _hash_file(req_path)
            cached_hash = _read_cached_hash(req_hash_path)
            
            if current_hash != cached_hash:
                logs.append("--- Installing/Updating Dependencies (requirements.txt changed) ---")
                ok, out, err, t = run_command(
                    [python_exe, "-m", "pip", "install", "-r", "requirements.txt"],
                    project_path
                )
                if ok:
                    # Cache the hash on success
                    with open(req_hash_path, "w") as f:
                        f.write(current_hash)
                    logs.append(f"  [{t}s] Dependencies installed")
                else:
                    logs.append(f"  [{t}s] FAILED:\n{err[-2000:]}")
                    return False, "\n".join(logs)
            else:
                logs.append("--- requirements.txt unchanged, skipping install ---")
        else:
            logs.append("--- WARNING: No requirements.txt found, skipping dependency install ---")

        # C. Install test framework & tools (ONLY on first run)
        tools_marker = os.path.join(venv_dir, ".tools_installed")
        if not os.path.exists(tools_marker):
            if framework and framework.lower() != "unittest":
                logs.append(f"--- Installing {framework} (First Run Only) ---")
                run_command([python_exe, "-m", "pip", "install", framework], project_path)
                
                if "fastapi" in tech_stack.get("framework", "").lower():
                    logs.append("--- Installing httpx (First Run Only) ---")
                    run_command([python_exe, "-m", "pip", "install", "httpx"], project_path)
            
            with open(tools_marker, "w") as f:
                f.write("done")
        else:
            logs.append("--- Framework & tools already installed, skipping ---")

        # D. Run Tests with compact output
        logs.append(f"--- Running Tests ({framework}) ---")
        if "django" in tech_stack.get("framework", "").lower():
            test_cmd = [python_exe, "manage.py", "test"]
        else:
            test_cmd = [python_exe, "-m", framework, "--tb=short", "-q"]
        
        ok, out, err, t = run_command(test_cmd, project_path)
        # Combine test output (pytest prints results to stdout)
        test_output = (out + "\n" + err).strip()
        logs.append(f"  [{t}s] {'PASSED' if ok else 'FAILED'}")
        logs.append(test_output)
        success = ok

    elif "node" in language or "javascript" in language:
        if not os.path.exists(os.path.join(project_path, "node_modules")):
            logs.append("--- Installing Node Dependencies (First Run) ---")
            ok, out, err, t = run_command("npm install", project_path)
            if not ok:
                return False, out + "\n" + err
        else:
            logs.append("--- Updating Node Dependencies ---")
            run_command("npm install", project_path)

        logs.append("--- Running Tests ---")
        ok, out, err, t = run_command("npm test", project_path)
        logs.append(f"  [{t}s] {'PASSED' if ok else 'FAILED'}")
        logs.append((out + "\n" + err).strip())
        success = ok

    # Save full logs to disk (for human inspection)
    log_path = os.path.join(project_path, "test_execution.log")
    full_log = "\n".join(logs)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(full_log)
    
    return success, full_log

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
# Maximum characters of test output to pass into state (for debugger)
_MAX_OUTPUT_CHARS = 15000

def tester_agent(state: AgentState) -> dict:
    """
    Test Agent — generates and executes tests.
    
    Optimization: On debug re-runs (test_files already exist in state),
    skips the LLM call entirely and just re-runs the existing tests.
    """
    project_name = state["user_input"].get("project_name")
    logger.info(f"--- TEST AGENT: Verifying {project_name} ---")
    
    user_req = state["user_input"]
    tech_decisions = state.get("tech_decisions", {})
    existing_files = state.get("files", {})
    existing_test_files = state.get("test_files", {})
    debug_iterations = state.get("debug_iterations", 0)
    
    # ------------------------------------------------------------------
    # OPTIMIZATION: Skip LLM on debug re-runs
    # If the debugger just fixed code and test files already exist,
    # we only need to re-run the tests — NOT regenerate them.
    # ------------------------------------------------------------------
    if existing_test_files and debug_iterations > 0:
        logger.info("♻️  Debug re-run detected — reusing existing test files (skipping LLM call)")
        all_files = {**existing_files, **existing_test_files}
        
        success, output = setup_and_run_tests(
            project_name, all_files,
            "pytest",  # Framework is already decided
            tech_decisions
        )
        
        logger.info(f"Test Re-run Result: {'Passed ✅' if success else 'Failed ❌'}")
        
        return {
            "files": all_files,
            "test_files": existing_test_files,
            "test_results": {
                "tests_passed": success,
                "output": output[-_MAX_OUTPUT_CHARS:],
                "command": "Re-run (no LLM call)"
            }
        }
    
    # ------------------------------------------------------------------
    # FIRST RUN: Generate tests via LLM
    # ------------------------------------------------------------------
    logger.info("🧪 First test run — generating tests via LLM")
    tech_stack_str = f"{tech_decisions.get('language')} / {tech_decisions.get('framework')}"

    # Build smart context (prioritized, never mid-file truncated)
    file_context_str = build_smart_context(existing_files)

    llm = get_llm(temperature=0.1)
    chain = tester_prompt | llm 
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "tech_stack": tech_stack_str,
            "file_context": file_context_str
        })
        
        # Parse LLM output
        test_files_dict, framework = parse_tester_output(response.content)
        
        if not test_files_dict:
            logger.warning("⚠️ Tester LLM returned no test files!")
        
        # Merge: source files + newly generated test files
        all_files = {**existing_files, **test_files_dict}
        
        # Execute tests
        success, output = setup_and_run_tests(
            user_req.get("project_name"), all_files, framework, tech_decisions
        )
        
        logger.info(f"Test Execution Result: {'Passed ✅' if success else 'Failed ❌'}")
        
        return {
            "files": all_files,
            "test_files": test_files_dict,  # Store separately for debug-loop reuse
            "test_results": {
                "tests_passed": success,
                "output": output[-_MAX_OUTPUT_CHARS:],
                "command": f"Automated {framework} in venv"
            }
        }
    except Exception as e:
        logger.error(f"❌ Error in Test Agent: {e}")
        return {
            "test_results": {
                "tests_passed": False,
                "output": str(e),
                "command": "unknown"
            }
        }