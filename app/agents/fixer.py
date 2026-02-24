"""
Fixer Agent — Two-phase bug prevention for AutoDev AI.

Replaces the old Validator + Tester + Debugger pipeline with a single agent
that catches common, embarrassing bugs before delivering the project.

Phase 1: Deterministic checks (zero LLM cost)
  - Missing dependencies in requirements.txt / package.json
  - Truncated / syntactically broken files
  - Missing mandatory files (__init__.py, pytest.ini, .env, .gitignore)
  - Missing __init__.py in nested Python packages
  - Entry point validation
  - Duplicate dependency removal
  - Test DB isolation (conftest vs prod DB)

Phase 2: Smart LLM review (single call, tightly scoped)
  - Cross-file import consistency
  - Route/endpoint mounting verification
  - Schema-to-model alignment
  - Config reference consistency
  - Missing error handling

Language-aware: dispatches to Python or Node.js checks based on
tech_decisions["language"].
"""

import ast
import re
import json
from typing import Dict, List, Tuple
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger
from app.core.language_config import detect_language, get_language_profile


# =====================================================================
# PYTHON: IMPORT → PYPI PACKAGE MAPPING
# =====================================================================
IMPORT_TO_PACKAGE = {
    # Async DB drivers
    "asyncpg": "asyncpg",
    "aiosqlite": "aiosqlite",
    "aiomysql": "aiomysql",
    # FastAPI ecosystem
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "starlette": "starlette",
    "httpx": "httpx",
    # Pydantic
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "email_validator": "email-validator",
    # SQLAlchemy
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    # Auth / Security
    "jose": "python-jose[cryptography]",
    "jwt": "PyJWT",
    "passlib": "passlib[bcrypt]",
    "bcrypt": "bcrypt",
    # Testing
    "pytest": "pytest",
    "pytest_asyncio": "pytest-asyncio",
    "pytest_mock": "pytest-mock",
    # Utilities
    "dotenv": "python-dotenv",
    "redis": "redis",
    "celery": "celery",
    "requests": "requests",
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
    "stripe": "stripe",
}

# Standard library modules to ignore during import scanning
STDLIB_MODULES = {
    "os", "sys", "re", "json", "typing", "datetime", "uuid", "hashlib",
    "logging", "pathlib", "collections", "functools", "itertools",
    "abc", "enum", "io", "math", "random", "time", "asyncio",
    "contextlib", "dataclasses", "copy", "traceback", "unittest",
    "base64", "hmac", "secrets", "shutil", "subprocess", "tempfile",
    "textwrap", "threading", "warnings", "decimal", "fractions",
    "statistics", "string", "struct", "socket", "http", "urllib",
    "email", "html", "xml", "csv", "sqlite3", "codecs",
    "importlib", "inspect", "operator", "types", "weakref",
    "pprint", "dis", "gc", "signal", "atexit", "platform",
}

# Node.js built-in modules to ignore during require() scanning
NODE_BUILTINS = {
    "fs", "path", "http", "https", "url", "os", "util", "events",
    "stream", "crypto", "buffer", "querystring", "child_process",
    "cluster", "dns", "net", "tls", "readline", "zlib", "assert",
    "process", "module", "vm", "console", "timers",
}


# =====================================================================
# PHASE 1: PYTHON DETERMINISTIC CHECKS
# =====================================================================
def _extract_imports(source_code: str) -> set:
    """
    Uses AST to reliably extract all top-level imported module names
    from a Python source file. Returns the root package name only.
    """
    imports = set()
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        for match in re.finditer(r'^\s*(?:from|import)\s+(\w+)', source_code, re.MULTILINE):
            imports.add(match.group(1))
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def _parse_requirements(req_content: str) -> Dict[str, str]:
    """Parses requirements.txt content into {package_name_lower: original_line}."""
    packages = {}
    for line in req_content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
        if match:
            packages[match.group(1).lower().replace("-", "_")] = line
    return packages


def fix_missing_dependencies_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Scans all .py files for imports, cross-references with requirements.txt,
    and auto-adds any missing packages.
    """
    fixes = []
    
    project_packages = set()
    for path in files:
        parts = path.replace("\\", "/").split("/")
        if parts:
            project_packages.add(parts[0])
    
    all_imports = set()
    for path, content in files.items():
        if path.endswith(".py"):
            all_imports |= _extract_imports(content)
    
    third_party_imports = all_imports - STDLIB_MODULES - project_packages
    
    req_content = files.get("requirements.txt", "")
    existing_packages = _parse_requirements(req_content)
    
    missing = []
    for imp in sorted(third_party_imports):
        imp_normalized = imp.lower().replace("-", "_")
        if imp_normalized in existing_packages:
            continue
        pypi_name = IMPORT_TO_PACKAGE.get(imp, None)
        if pypi_name:
            pypi_normalized = pypi_name.split("[")[0].lower().replace("-", "_")
            if pypi_normalized in existing_packages:
                continue
            missing.append(pypi_name)
            fixes.append(f"Added '{pypi_name}' to requirements.txt (imported as '{imp}')")
    
    if missing:
        lines = req_content.strip().splitlines() if req_content.strip() else []
        lines.extend(missing)
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for line in lines:
            key = re.match(r'^([a-zA-Z0-9_-]+)', line)
            if key:
                norm = key.group(1).lower().replace("-", "_")
                if norm not in seen:
                    seen.add(norm)
                    deduped.append(line)
            else:
                deduped.append(line)
        files["requirements.txt"] = "\n".join(deduped) + "\n"
    
    return files, fixes


def detect_truncated_files_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detects Python files that are truncated mid-function/class.
    Truncated files are removed to prevent SyntaxErrors.
    """
    warnings = []
    cleaned = {}
    
    for path, content in files.items():
        if not path.endswith(".py"):
            cleaned[path] = content
            continue
        
        if not content.strip():
            cleaned[path] = content
            continue
        
        try:
            ast.parse(content)
            cleaned[path] = content
        except SyntaxError as e:
            lines = content.splitlines()
            total_lines = len(lines)
            
            if e.lineno and e.lineno >= total_lines - 2:
                warnings.append(
                    f"TRUNCATED: '{path}' has SyntaxError near end (line {e.lineno}/{total_lines}). "
                    f"Removed to prevent errors."
                )
            else:
                warnings.append(
                    f"SYNTAX ERROR: '{path}' at line {e.lineno}: {e.msg}. Kept file."
                )
                cleaned[path] = content
    
    return cleaned, warnings


DEFAULT_PYTEST_INI = """[pytest]
asyncio_mode = auto
python_files = test_*.py
"""

DEFAULT_ENV = """DATABASE_URL=sqlite+aiosqlite:///./dev.db
SECRET_KEY=dev-secret-key-change-in-production
"""

DEFAULT_GITIGNORE_PYTHON = """__pycache__/
*.pyc
*.pyo
.env
*.db
venv/
.venv/
dist/
build/
*.egg-info/
"""

DEFAULT_GITIGNORE_NODE = """node_modules/
.env
dist/
build/
*.log
coverage/
"""


def ensure_mandatory_files_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Ensures critical Python project files exist."""
    fixes = []
    
    # __init__.py in tests directory
    has_test_files = any(p.startswith("tests/") and p.endswith(".py") for p in files)
    if has_test_files and "tests/__init__.py" not in files:
        files["tests/__init__.py"] = ""
        fixes.append("Created missing 'tests/__init__.py'")
    
    # pytest.ini
    if has_test_files and "pytest.ini" not in files:
        files["pytest.ini"] = DEFAULT_PYTEST_INI
        fixes.append("Created missing 'pytest.ini' with asyncio_mode=auto")
    
    # .env file
    uses_env = any(
        "dotenv" in content or "pydantic_settings" in content or "os.getenv" in content
        for content in files.values()
        if isinstance(content, str)
    )
    if uses_env and ".env" not in files:
        files[".env"] = DEFAULT_ENV
        fixes.append("Created missing '.env' with safe defaults")
    
    # requirements.txt
    if "requirements.txt" not in files:
        files["requirements.txt"] = "fastapi\nuvicorn\npydantic\nsqlalchemy\naiosqlite\n"
        fixes.append("Created missing 'requirements.txt' with base dependencies")
    
    # .gitignore
    if ".gitignore" not in files:
        files[".gitignore"] = DEFAULT_GITIGNORE_PYTHON
        fixes.append("Created '.gitignore' for Python project")
    
    return files, fixes


def ensure_init_files_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Ensures __init__.py exists in every directory that contains .py files."""
    fixes = []
    
    # Collect all directories that contain .py files
    dirs_with_py = set()
    for path in files:
        if path.endswith(".py"):
            parts = path.replace("\\", "/").split("/")
            # Build all parent directories
            for i in range(1, len(parts)):
                dir_path = "/".join(parts[:i])
                dirs_with_py.add(dir_path)
    
    # Ensure __init__.py in each
    for dir_path in sorted(dirs_with_py):
        init_path = f"{dir_path}/__init__.py"
        if init_path not in files:
            files[init_path] = ""
            fixes.append(f"Created missing '{init_path}'")
    
    return files, fixes


def fix_test_db_isolation_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Checks that test conftest doesn't accidentally use prod PostgreSQL URL."""
    fixes = []
    env_content = files.get(".env", "")
    conftest_content = files.get("tests/conftest.py", "")
    
    if not conftest_content:
        return files, fixes
    
    uses_postgres = "postgresql" in env_content.lower()
    conftest_uses_sqlite = "sqlite" in conftest_content.lower()
    
    if uses_postgres and not conftest_uses_sqlite:
        fixes.append(
            "WARNING: .env uses PostgreSQL but tests/conftest.py doesn't override "
            "to SQLite. Tests may try to connect to prod DB."
        )
    
    return files, fixes


def validate_entry_point_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Verifies that a recognizable entry point file exists."""
    fixes = []
    
    entry_points = ["main.py", "app.py", "app/main.py", "src/main.py", "src/app.py"]
    has_entry = any(ep in files for ep in entry_points)
    
    if not has_entry:
        # Check for any file that creates a FastAPI/Flask app
        for path, content in files.items():
            if path.endswith(".py") and ("FastAPI()" in content or "Flask(" in content):
                has_entry = True
                break
    
    if not has_entry:
        fixes.append(
            "WARNING: No recognizable entry point found (main.py, app.py, app/main.py). "
            "Users may not know how to start the application."
        )
    
    return files, fixes


# =====================================================================
# PHASE 1: NODE.JS DETERMINISTIC CHECKS
# =====================================================================
def _extract_requires(source_code: str) -> set:
    """
    Extracts all module names from require() and import statements in JS/TS files.
    Returns only third-party modules (not relative paths starting with . or /).
    """
    modules = set()
    
    # require('module') or require("module")
    for match in re.finditer(r'''require\s*\(\s*['"]([^'"]+)['"]\s*\)''', source_code):
        mod = match.group(1)
        if not mod.startswith(".") and not mod.startswith("/"):
            modules.add(mod.split("/")[0])
    
    # import ... from 'module' or import 'module'
    for match in re.finditer(r'''(?:import\s+.*?\s+from|import)\s+['"]([^'"]+)['"]''', source_code):
        mod = match.group(1)
        if not mod.startswith(".") and not mod.startswith("/"):
            modules.add(mod.split("/")[0])
    
    return modules


def _parse_package_json(pkg_content: str) -> Tuple[set, dict]:
    """Parses package.json and returns (set of all dependency names, parsed json dict)."""
    try:
        pkg = json.loads(pkg_content)
    except (json.JSONDecodeError, TypeError):
        return set(), {}
    
    deps = set()
    for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pkg.get(dep_key, {}).keys())
    
    return deps, pkg


def validate_package_json_node(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Validates that package.json exists, has a test script, fixes common jest issues,
    and ensures all require()'d modules are listed as dependencies.
    """
    fixes = []
    
    if "package.json" not in files:
        fixes.append("WARNING: No package.json found. Node.js project cannot install dependencies.")
        return files, fixes
    
    existing_deps, pkg = _parse_package_json(files["package.json"])
    
    if not pkg:
        fixes.append("WARNING: package.json is not valid JSON. Cannot validate dependencies.")
        return files, fixes
    
    pkg_changed = False
    
    # Check for test script
    scripts = pkg.get("scripts", {})
    test_script = scripts.get("test", "")
    
    if not test_script or test_script == 'echo "Error: no test specified" && exit 1':
        if "scripts" not in pkg:
            pkg["scripts"] = {}
        pkg["scripts"]["test"] = "npx jest --forceExit --detectOpenHandles"
        pkg_changed = True
        fixes.append("Added 'test': 'npx jest --forceExit --detectOpenHandles' to package.json scripts")
    elif "jest" in test_script and "npx" not in test_script:
        pkg["scripts"]["test"] = test_script.replace("jest", "npx jest", 1)
        pkg_changed = True
        fixes.append(f"Fixed test script to use 'npx jest' (prevents jest: not found)")
    
    # Fix dual Jest config conflict
    has_jest_config_file = any(
        p in files for p in ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs")
    )
    if has_jest_config_file and "jest" in pkg:
        del pkg["jest"]
        pkg_changed = True
        fixes.append("Removed 'jest' key from package.json (conflicts with jest.config.js)")
    
    if pkg_changed:
        files["package.json"] = json.dumps(pkg, indent=2) + "\n"
    
    # Scan all JS/TS files for require()/import
    all_requires = set()
    for path, content in files.items():
        if path.endswith((".js", ".ts", ".mjs", ".cjs")):
            all_requires |= _extract_requires(content)
    
    # Filter out builtins
    third_party = all_requires - NODE_BUILTINS
    
    # Find missing dependencies
    for mod in sorted(third_party):
        mod_normalized = mod.lower()
        if mod_normalized not in {d.lower() for d in existing_deps}:
            fixes.append(f"WARNING: '{mod}' is required in code but not in package.json dependencies")
    
    return files, fixes


def detect_truncated_files_node(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detects JS/TS files that are truncated by checking brace balance.
    """
    warnings = []
    cleaned = {}
    
    for path, content in files.items():
        if not path.endswith((".js", ".ts", ".mjs", ".cjs")):
            cleaned[path] = content
            continue
        
        if not content.strip():
            cleaned[path] = content
            continue
        
        open_braces = content.count("{")
        close_braces = content.count("}")
        
        if open_braces > close_braces + 2:
            warnings.append(
                f"LIKELY TRUNCATED: '{path}' has {open_braces} '{{' "
                f"but only {close_braces} '}}'. File may be incomplete."
            )
        
        stripped = content.rstrip()
        if stripped.endswith((",", "+", "=", "{")):
            warnings.append(
                f"TRUNCATED: '{path}' ends with '{stripped[-1]}', suggesting incomplete code."
            )
        
        cleaned[path] = content
    
    return cleaned, warnings


def ensure_mandatory_files_node(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Ensures critical Node.js project files exist."""
    fixes = []
    
    # .env file
    uses_env = any(
        "process.env" in content or "dotenv" in content
        for content in files.values()
        if isinstance(content, str)
    )
    if uses_env and ".env" not in files:
        files[".env"] = "PORT=3000\nMONGODB_URI=mongodb://localhost:27017/dev_db\nSECRET_KEY=dev-secret-key\n"
        fixes.append("Created missing '.env' with safe defaults for Node.js")
    
    # .gitignore
    if ".gitignore" not in files:
        files[".gitignore"] = DEFAULT_GITIGNORE_NODE
        fixes.append("Created '.gitignore' for Node.js project")
    
    return files, fixes


def validate_entry_point_node(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Verifies that a recognizable Node.js entry point exists."""
    fixes = []
    
    entry_points = ["server.js", "index.js", "app.js", "src/index.js", "src/server.js", "src/app.js"]
    has_entry = any(ep in files for ep in entry_points)
    
    if not has_entry:
        fixes.append(
            "WARNING: No recognizable entry point found (server.js, index.js, app.js). "
            "Users may not know how to start the application."
        )
    
    return files, fixes


# =====================================================================
# PHASE 2: SMART LLM REVIEW (Single focused call)
# =====================================================================
_FIXER_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a Senior Code Reviewer for AutoDev AI.

**Your ONLY job:** Scan the project files below and fix OBVIOUS cross-file bugs.
You are NOT writing tests, NOT debugging runtime errors. You are catching silly mistakes 
the code generator made that a human reviewer would spot in 30 seconds.

**CHECK ONLY THESE 5 THINGS:**

1. **Import Consistency:** Does `from app.models.user import User` actually have a 
   corresponding `app/models/user.py` file that defines `User`? Fix broken import paths.

2. **Route Mounting:** Are all routers/routes actually included in the main app?
   - Python: Every `APIRouter()` should have a matching `app.include_router()`.
   - Node.js: Every route file should have a matching `app.use()` in the main file.

3. **Schema ↔ Model Alignment:** Do API request/response schemas match the database model fields?
   (e.g., schema expects `username` but model has `name`)

4. **Config/Env References:** Does the code reference environment variables that don't exist 
   in the `.env` file? Add missing vars to `.env` with safe defaults.

5. **Basic Error Handling:** Do DB-writing endpoints have try/except (Python) or try/catch (Node)?
   If not, wrap them minimally.

**RULES:**
- Only output files you CHANGED. Do NOT re-output unchanged files.
- If everything looks fine, output NOTHING (empty response).
- Output COMPLETE file content for any file you modify (not partial diffs).
- Do NOT add tests, do NOT add new features, do NOT refactor working code.
- Be conservative: if you're unsure whether something is a bug, leave it alone.

**Output Format:**
<file path="path/to/file">
... full corrected content ...
</file>

If no fixes needed, respond with exactly: <no_fixes/>
"""),
    ("user", """
**Project Language:** {language}
**Tech Stack:** {tech_stack}

--- PROJECT FILES ---
{file_context}
""")
])


def _build_review_context(files: Dict[str, str], profile: dict, max_chars: int = 50000) -> str:
    """Builds a concise file context string for the LLM review, prioritizing source files."""
    high_ext = profile.get("high_priority_ext", ())
    low_ext = profile.get("low_priority_ext", ())
    skip_ext = profile.get("skip_extensions", ())
    
    high_priority = []
    low_priority = []
    
    for path, content in files.items():
        if path.endswith(skip_ext) or path.endswith(("package-lock.json",)):
            continue
        if path.endswith(high_ext):
            high_priority.append((path, content))
        elif path.endswith(low_ext):
            low_priority.append((path, content))
        else:
            low_priority.append((path, content))
    
    context = ""
    char_count = 0
    
    for path, content in high_priority + low_priority:
        entry = f"\n--- FILE: {path} ---\n{content}\n"
        if char_count + len(entry) > max_chars:
            break
        context += entry
        char_count += len(entry)
    
    return context


def run_llm_review(files: Dict[str, str], tech_decisions: dict, profile: dict) -> Tuple[Dict[str, str], List[str]]:
    """
    Phase 2: A single, focused LLM call that reviews all files for cross-file 
    consistency issues. Returns only the files that need fixes.
    """
    fixes = []
    language = detect_language(tech_decisions)
    
    file_context = _build_review_context(files, profile)
    
    if not file_context.strip():
        return {}, fixes
    
    stack_str = f"{tech_decisions.get('language', 'Python')} / {tech_decisions.get('framework', 'FastAPI')} / {tech_decisions.get('database', 'SQLite')}"
    
    llm = get_llm(temperature=0.0)
    chain = _FIXER_REVIEW_PROMPT | llm
    
    try:
        response = chain.invoke({
            "language": language,
            "tech_stack": stack_str,
            "file_context": file_context,
        })
        
        response_text = response.content
        if isinstance(response_text, list):
            response_text = "".join(str(item) for item in response_text)
        
        # Check for "no fixes needed"
        if "<no_fixes/>" in response_text or "<no_fixes />" in response_text:
            logger.info("  ✅ LLM review: No cross-file issues found.")
            return {}, fixes
        
        # Parse file outputs
        pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        fixed_files = {}
        for path, content in matches:
            content = content.strip()
            # Remove markdown code fences if accidentally added
            content = re.sub(r'^```[a-z]*\n', '', content)
            content = re.sub(r'\n```$', '', content)
            fixed_files[path] = content
            fixes.append(f"LLM fixed cross-file issue in '{path}'")
        
        if fixed_files:
            logger.info(f"  🔍 LLM review fixed {len(fixed_files)} file(s)")
        else:
            logger.info("  ✅ LLM review: No actionable issues found.")
        
        return fixed_files, fixes
        
    except Exception as e:
        logger.warning(f"  ⚠️ LLM review failed (non-fatal): {e}")
        return {}, [f"LLM review skipped due to error: {str(e)}"]


# =====================================================================
# AGENT FUNCTION (Language-Aware, Two-Phase)
# =====================================================================
def fixer_agent(state: AgentState) -> dict:
    """
    Fixer Agent — Two-phase bug prevention.
    
    Phase 1: Deterministic checks (zero LLM cost, language-aware)
    Phase 2: Single LLM call for cross-file consistency review
    """
    logger.info("--- FIXER AGENT: Running bug prevention checks ---")
    
    tech_decisions = state.get("tech_decisions", {})
    language = detect_language(tech_decisions)
    profile = get_language_profile(tech_decisions)
    
    logger.info(f"  Language: {language}")
    
    files = dict(state.get("files", {}))  # Mutable copy
    all_fixes = []
    all_warnings = []
    
    # =================================================================
    # PHASE 1: Deterministic Checks
    # =================================================================
    logger.info("  📋 Phase 1: Deterministic checks...")
    
    if language == "python":
        # Mandatory files (requirements.txt, pytest.ini, .env, .gitignore)
        files, fixes = ensure_mandatory_files_python(files)
        all_fixes.extend(fixes)
        
        # Missing __init__.py in nested packages
        files, fixes = ensure_init_files_python(files)
        all_fixes.extend(fixes)
        
        # Missing dependencies in requirements.txt
        files, fixes = fix_missing_dependencies_python(files)
        all_fixes.extend(fixes)
        
        # Truncated .py files
        files, warnings = detect_truncated_files_python(files)
        all_warnings.extend(warnings)
        
        # Test DB isolation
        files, warnings = fix_test_db_isolation_python(files)
        all_warnings.extend(warnings)
        
        # Entry point check
        files, warnings = validate_entry_point_python(files)
        all_warnings.extend(warnings)
    
    elif language == "node":
        # Mandatory files (.env, .gitignore)
        files, fixes = ensure_mandatory_files_node(files)
        all_fixes.extend(fixes)
        
        # package.json validation + missing deps
        files, fixes = validate_package_json_node(files)
        all_fixes.extend(fixes)
        
        # Truncated JS/TS files
        files, warnings = detect_truncated_files_node(files)
        all_warnings.extend(warnings)
        
        # Entry point check
        files, warnings = validate_entry_point_node(files)
        all_warnings.extend(warnings)
    
    # Log Phase 1 results
    if all_fixes:
        logger.info(f"  🔧 Phase 1 applied {len(all_fixes)} fixes:")
        for fix in all_fixes:
            logger.info(f"     ✅ {fix}")
    
    if all_warnings:
        logger.warning(f"  ⚠️  Phase 1 found {len(all_warnings)} warnings:")
        for warn in all_warnings:
            logger.warning(f"     ⚠️  {warn}")
    
    if not all_fixes and not all_warnings:
        logger.info("  ✅ Phase 1: All deterministic checks passed.")
    
    # =================================================================
    # PHASE 2: Smart LLM Review
    # =================================================================
    logger.info("  🧠 Phase 2: Smart LLM review for cross-file issues...")
    
    llm_fixed_files, llm_fixes = run_llm_review(files, tech_decisions, profile)
    
    if llm_fixed_files:
        files.update(llm_fixed_files)
        all_fixes.extend(llm_fixes)
    
    # Final summary
    total_fixes = len(all_fixes)
    total_warnings = len(all_warnings)
    logger.info(f"  📊 Fixer complete: {total_fixes} fixes applied, {total_warnings} warnings.")
    
    return {
        "files": files,
        "fixes_applied": all_fixes + [f"⚠️ {w}" for w in all_warnings],
    }
