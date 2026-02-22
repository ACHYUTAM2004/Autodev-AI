import os
import re
import sys
import time
import json
import hashlib
import subprocess
from typing import Union, List, Dict, Tuple
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.config import settings
from app.core.logger import logger
from app.core.language_config import detect_language, get_language_profile

# ---------------------------------------------------------------------
# TESTER PROMPT (Language-Agnostic Shell)
# ---------------------------------------------------------------------
tester_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Test Automation Engineer for AutoDev AI.
    
    **CRITICAL: UNDERSTAND BEFORE WRITING (Chain of Thought)**
    Before writing a single test, you MUST internally:
    1.  **Map the codebase**: Identify ALL endpoints/routes/functions. List them mentally.
    2.  **Design test DB setup FIRST**: Figure out how tests will connect to an isolated
        database BEFORE writing any test cases. Get the fixtures/setup right first.
    3.  **Plan coverage**: For EACH endpoint, decide what tests are needed (happy path,
        validation errors, not-found, edge cases). Count: N endpoints × ~4 tests each.
    
    **COVERAGE COMPLETENESS GATE (MANDATORY):**
    After writing all tests, count:
    1. Number of endpoints/routes in the source code: E
    2. Number of endpoints covered by at least one test: T
    3. If T < E, you are NOT done. Add tests for the missing endpoints.
    
    **TEST INDEPENDENCE (ZERO COUPLING):**
    - Each test MUST work if run alone, in any order, or in parallel.
    - NEVER rely on a previous test's side effects (e.g., "create" before "get").
    - Each test creates its OWN test data in the test body or fixture.
    
    **ANTI-FLAKE RULES:**
    - NEVER use sleep/delays, random data, real timestamps, or external services.
    - NEVER assert on auto-generated IDs by exact value — only assert they exist.
    - Use deterministic test data (hardcoded strings, not random).
    
    **SETUP-FIRST THINKING:**
    The #1 cause of test failure is broken setup, NOT bad assertions.
    Spend 80% of your thinking on getting the test client + DB setup correct.
    The actual test cases are the easy part.
    
    Think step-by-step internally, but DO NOT output the reasoning.
    Only output the final test files.
    
    **LANGUAGE-SPECIFIC RULES:**
    {language_rules}
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
    
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
        
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\n", "\n")
        
    content = content.replace("\\'", "'").replace('\\"', '"')
    
    return content

def parse_tester_output(text: Union[str, list]) -> Tuple[Dict[str, str], str]:
    """Robustly extracts files and framework from LLM output."""
    
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    files = {}
    framework = "pytest"  # Default, overridden by <framework> tag
    
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
# SMART CONTEXT BUILDER (Language-Aware)
# ---------------------------------------------------------------------
_SKIP_ALWAYS = (".lock", ".png", ".jpg", ".jpeg", ".gif", ".pyc", ".zip", ".tar", ".gz", ".map")

def build_smart_context(files: Dict[str, str], profile: dict, max_chars: int = 25000) -> str:
    """
    Builds LLM context from project files with intelligent prioritization.
    Uses the language profile to determine which file types are high priority.
    """
    high_prio_ext = profile.get("high_priority_ext", (".py",))
    low_prio_ext = profile.get("low_priority_ext", (".txt", ".ini", ".cfg", ".env", ".toml", ".md"))
    skip_ext = profile.get("skip_extensions", _SKIP_ALWAYS)
    
    high_prio = []
    low_prio = []
    
    for path, content in files.items():
        if path.endswith(skip_ext):
            continue
        if path.endswith(high_prio_ext):
            high_prio.append((path, content))
        else:
            low_prio.append((path, content))
    
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
            logger.debug(f"Context budget exceeded, skipping: {path} ({len(entry)} chars)")
    
    return "".join(context_parts)

# ---------------------------------------------------------------------
# SUBPROCESS RUNNER
# ---------------------------------------------------------------------
def run_command(command: Union[str, List[str]], cwd: str, timeout: int = 300) -> Tuple[bool, str, str, float]:
    """Runs a subprocess command and returns (success, stdout, stderr, elapsed_seconds)."""
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
    """Writes content to file ONLY if it differs from what's on disk."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            if f.read() == content:
                return False
    except (FileNotFoundError, UnicodeDecodeError):
        pass
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return True

# ---------------------------------------------------------------------
# TEST SETUP & EXECUTION (Language-Aware)
# ---------------------------------------------------------------------
def setup_and_run_tests(
    project_name: str,
    files: Dict[str, str],
    framework: str,
    tech_stack: Dict[str, str]
) -> Tuple[bool, str]:
    """
    Sets up the project environment and executes tests.
    Dispatches to Python or Node.js execution paths based on tech_stack language.
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
    # 2. Environment Setup (Language-Dispatched)
    # ------------------------------------------------------------------
    language = detect_language(tech_stack)
    is_windows = sys.platform.startswith("win")
    success = False

    if language == "python":
        success, py_logs = _run_python_tests(project_path, framework, tech_stack, is_windows)
        logs.extend(py_logs)

    elif language == "node":
        success, node_logs = _run_node_tests(project_path, tech_stack)
        logs.extend(node_logs)

    else:
        logs.append(f"--- WARNING: Unsupported language '{language}', skipping tests ---")

    # Save full logs to disk
    log_path = os.path.join(project_path, "test_execution.log")
    full_log = "\n".join(logs)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(full_log)
    
    return success, full_log


def _run_python_tests(project_path: str, framework: str, tech_stack: dict, is_windows: bool) -> Tuple[bool, List[str]]:
    """Python test execution: venv creation, pip install, pytest."""
    logs = []
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
            return False, logs
        
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
                with open(req_hash_path, "w") as f:
                    f.write(current_hash)
                logs.append(f"  [{t}s] Dependencies installed")
            else:
                logs.append(f"  [{t}s] FAILED:\n{err[-2000:]}")
                return False, logs
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

    # D. Run Tests
    logs.append(f"--- Running Tests ({framework}) ---")
    if "django" in tech_stack.get("framework", "").lower():
        test_cmd = [python_exe, "manage.py", "test"]
    else:
        test_cmd = [python_exe, "-m", framework, "--tb=short", "-q"]
    
    ok, out, err, t = run_command(test_cmd, project_path)
    test_output = (out + "\n" + err).strip()
    logs.append(f"  [{t}s] {'PASSED' if ok else 'FAILED'}")
    logs.append(test_output)
    
    return ok, logs


def _run_node_tests(project_path: str, tech_stack: dict) -> Tuple[bool, List[str]]:
    """Node.js test execution: npm install, npm test."""
    logs = []
    
    pkg_json_path = os.path.join(project_path, "package.json")
    node_modules_path = os.path.join(project_path, "node_modules")
    pkg_hash_path = os.path.join(project_path, ".pkg_hash")
    
    if not os.path.exists(pkg_json_path):
        logs.append("--- ERROR: No package.json found. Cannot run Node.js tests. ---")
        return False, logs
    
    # A. Install dependencies (only if package.json changed or node_modules doesn't exist)
    current_hash = _hash_file(pkg_json_path)
    cached_hash = _read_cached_hash(pkg_hash_path)
    
    if not os.path.exists(node_modules_path) or current_hash != cached_hash:
        logs.append("--- Installing Node Dependencies (npm install) ---")
        ok, out, err, t = run_command("npm install", project_path)
        if ok:
            with open(pkg_hash_path, "w") as f:
                f.write(current_hash)
            logs.append(f"  [{t}s] Dependencies installed")
        else:
            logs.append(f"  [{t}s] npm install FAILED:\n{(out + err)[-2000:]}")
            return False, logs
    else:
        logs.append("--- package.json unchanged, skipping npm install ---")
    
    # B. Run Tests
    logs.append("--- Running Tests (npm test) ---")
    ok, out, err, t = run_command("npm test", project_path)
    test_output = (out + "\n" + err).strip()
    logs.append(f"  [{t}s] {'PASSED' if ok else 'FAILED'}")
    logs.append(test_output)
    
    return ok, logs


# ---------------------------------------------------------------------
# AGENT FUNCTION (Language-Aware)
# ---------------------------------------------------------------------
_MAX_OUTPUT_CHARS = 15000

def tester_agent(state: AgentState) -> dict:
    """
    Test Agent — generates and executes tests.
    Language-aware: uses the correct prompt rules, context priorities,
    and test framework based on tech_decisions.
    """
    project_name = state["user_input"].get("project_name")
    logger.info(f"--- TEST AGENT: Verifying {project_name} ---")
    
    user_req = state["user_input"]
    tech_decisions = state.get("tech_decisions", {})
    existing_files = state.get("files", {})
    existing_test_files = state.get("test_files", {})
    debug_iterations = state.get("debug_iterations", 0)
    
    # Get language profile
    profile = get_language_profile(tech_decisions)
    language = detect_language(tech_decisions)
    default_framework = profile["default_test_framework"]
    
    logger.info(f"  Language: {language}, Default framework: {default_framework}")
    
    # ------------------------------------------------------------------
    # OPTIMIZATION: Skip LLM on debug re-runs
    # ------------------------------------------------------------------
    if existing_test_files and debug_iterations > 0:
        logger.info("♻️  Debug re-run detected — reusing existing test files (skipping LLM call)")
        all_files = {**existing_files, **existing_test_files}
        
        success, output = setup_and_run_tests(
            project_name, all_files,
            default_framework,
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

    # Build smart context using language-aware priorities
    file_context_str = build_smart_context(existing_files, profile)

    llm = get_llm(temperature=0.1)
    chain = tester_prompt | llm 
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "tech_stack": tech_stack_str,
            "file_context": file_context_str,
            "language_rules": profile["tester_rules"],
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
            "test_files": test_files_dict,
            "test_results": {
                "tests_passed": success,
                "output": output[-_MAX_OUTPUT_CHARS:],
                "command": f"Automated {framework} in {'venv' if language == 'python' else 'node_modules'}"
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