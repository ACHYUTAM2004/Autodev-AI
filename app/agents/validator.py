"""
Programmatic Validator Agent — Zero-cost, deterministic bug prevention.

Runs between Coder → Tester and Debugger → Tester.
Language-aware: dispatches to Python-specific or Node.js-specific checks
based on tech_decisions["language"].

Python checks:
  1. Missing dependencies in requirements.txt
  2. Truncated / syntactically broken .py files
  3. Missing mandatory files (tests/__init__.py, pytest.ini, .env)
  4. Test DB isolation (ensures conftest uses SQLite, not prod DB)

Node.js checks:
  1. package.json exists and has a "test" script
  2. Truncated / syntax-broken .js/.ts files (brace matching)
  3. Missing dependencies based on require()/import scanning
"""

import ast
import re
import json
from typing import Dict, List, Tuple
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
# PYTHON CHECKS
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
        files["requirements.txt"] = "\n".join(lines) + "\n"
    
    return files, fixes


def detect_truncated_files_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detects Python files that are truncated mid-function/class.
    Truncated files are removed to prevent SyntaxErrors during test execution.
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
                    f"TRUNCATED: '{path}' has a SyntaxError at line {e.lineno}/{total_lines} "
                    f"('{e.msg}'). Removing to allow re-generation."
                )
            else:
                warnings.append(
                    f"SYNTAX ERROR: '{path}' at line {e.lineno}: {e.msg} (kept for debugger)"
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

def ensure_mandatory_files_python(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Ensures critical Python project files exist."""
    fixes = []
    
    has_test_files = any(p.startswith("tests/") and p.endswith(".py") for p in files)
    if has_test_files and "tests/__init__.py" not in files:
        files["tests/__init__.py"] = ""
        fixes.append("Created missing 'tests/__init__.py'")
    
    if has_test_files and "pytest.ini" not in files:
        files["pytest.ini"] = DEFAULT_PYTEST_INI
        fixes.append("Created missing 'pytest.ini' with asyncio_mode=auto")
    
    uses_env = any(
        "dotenv" in content or "pydantic_settings" in content or "os.getenv" in content
        for content in files.values()
        if isinstance(content, str)
    )
    if uses_env and ".env" not in files:
        files[".env"] = DEFAULT_ENV
        fixes.append("Created missing '.env' with safe defaults")
    
    if "requirements.txt" not in files:
        files["requirements.txt"] = "fastapi\nuvicorn\npydantic\nsqlalchemy\naiosqlite\n"
        fixes.append("Created missing 'requirements.txt' with base dependencies")
    
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
            "to SQLite. Tests may try to connect to prod DB. "
            "Consider adding a SQLite test URL in conftest.py."
        )
    
    return files, fixes


# =====================================================================
# NODE.JS CHECKS
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
            modules.add(mod.split("/")[0])  # Get root package: @scope/pkg → @scope
    
    # import ... from 'module' or import 'module'
    for match in re.finditer(r'''(?:import\s+.*?\s+from|import)\s+['"]([^'"]+)['"]''', source_code):
        mod = match.group(1)
        if not mod.startswith(".") and not mod.startswith("/"):
            modules.add(mod.split("/")[0])
    
    return modules


def _parse_package_json(pkg_content: str) -> Tuple[set, dict]:
    """
    Parses package.json and returns (set of all dependency names, parsed json dict).
    """
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
    Validates that package.json exists, has a test script, and all
    require()'d modules are listed as dependencies.
    """
    fixes = []
    
    if "package.json" not in files:
        fixes.append("WARNING: No package.json found. Node.js project cannot install dependencies.")
        return files, fixes
    
    existing_deps, pkg = _parse_package_json(files["package.json"])
    
    if not pkg:
        fixes.append("WARNING: package.json is not valid JSON. Cannot validate dependencies.")
        return files, fixes
    
    # Check for test script
    scripts = pkg.get("scripts", {})
    if "test" not in scripts or not scripts["test"] or scripts["test"] == 'echo "Error: no test specified" && exit 1':
        # Auto-fix: add a jest test script
        if "scripts" not in pkg:
            pkg["scripts"] = {}
        pkg["scripts"]["test"] = "jest --forceExit --detectOpenHandles"
        files["package.json"] = json.dumps(pkg, indent=2) + "\n"
        fixes.append("Added 'test': 'jest --forceExit --detectOpenHandles' to package.json scripts")
    
    # Scan all JS/TS files for require()/import
    all_requires = set()
    for path, content in files.items():
        if path.endswith((".js", ".ts", ".mjs", ".cjs")):
            all_requires |= _extract_requires(content)
    
    # Filter out builtins and project-local modules
    third_party = all_requires - NODE_BUILTINS
    
    # Find missing dependencies
    missing = []
    for mod in sorted(third_party):
        mod_normalized = mod.lower()
        if mod_normalized not in {d.lower() for d in existing_deps}:
            missing.append(mod)
            fixes.append(f"WARNING: '{mod}' is required in code but not in package.json dependencies")
    
    # We don't auto-add to package.json because versions matter for Node —
    # just warn so the debugger/LLM can fix it.
    
    return files, fixes


def detect_truncated_files_node(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detects JS/TS files that are truncated by checking brace balance.
    A file with more { than } is likely truncated mid-function.
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
        
        # Simple brace balance check
        open_braces = content.count("{")
        close_braces = content.count("}")
        
        if open_braces > close_braces + 2:  # Allow small tolerance for template literals
            warnings.append(
                f"LIKELY TRUNCATED: '{path}' has {open_braces} opening braces "
                f"but only {close_braces} closing braces. File may be incomplete."
            )
            # Don't remove — just warn. Node runtime errors are more descriptive than Python's.
        
        # Check for obvious syntax issues (file ends mid-string)
        stripped = content.rstrip()
        if stripped.endswith((",", "+", "=", "{")):
            warnings.append(
                f"TRUNCATED: '{path}' ends with '{stripped[-1]}', suggesting incomplete code."
            )
        
        cleaned[path] = content
    
    return cleaned, warnings


# =====================================================================
# AGENT FUNCTION (Language-Aware Dispatcher)
# =====================================================================
def validator_agent(state: AgentState) -> dict:
    """
    Programmatic validator — zero LLM calls, pure Python.
    
    Dispatches to Python-specific or Node.js-specific checks based on
    tech_decisions["language"].
    """
    logger.info("--- VALIDATOR AGENT: Running programmatic checks ---")
    
    tech_decisions = state.get("tech_decisions", {})
    language = detect_language(tech_decisions)
    profile = get_language_profile(tech_decisions)
    
    logger.info(f"  Validating for language: {language}")
    
    files = dict(state.get("files", {}))  # Make a mutable copy
    all_fixes = []
    all_warnings = []
    
    checks = profile.get("validator_checks", [])
    
    # --- Python Checks ---
    if "mandatory_files" in checks and language == "python":
        files, fixes = ensure_mandatory_files_python(files)
        all_fixes.extend(fixes)
    
    if "imports" in checks:
        files, fixes = fix_missing_dependencies_python(files)
        all_fixes.extend(fixes)
    
    if "truncation" in checks:
        files, warnings = detect_truncated_files_python(files)
        all_warnings.extend(warnings)
    
    if "test_db" in checks:
        files, warnings = fix_test_db_isolation_python(files)
        all_warnings.extend(warnings)
    
    # --- Node.js Checks ---
    if "package_json" in checks:
        files, fixes = validate_package_json_node(files)
        all_fixes.extend(fixes)
    
    if "truncation_js" in checks:
        files, warnings = detect_truncated_files_node(files)
        all_warnings.extend(warnings)
    
    if "mandatory_files" in checks and language == "node":
        # For Node, ensure .env exists if code references process.env
        uses_env = any(
            "process.env" in content or "dotenv" in content
            for content in files.values()
            if isinstance(content, str)
        )
        if uses_env and ".env" not in files:
            files[".env"] = "PORT=3000\nMONGODB_URI=mongodb://localhost:27017/dev_db\nSECRET_KEY=dev-secret-key\n"
            all_fixes.append("Created missing '.env' with safe defaults for Node.js")
    
    # Log results
    if all_fixes:
        logger.info(f"🔧 Validator applied {len(all_fixes)} fixes:")
        for fix in all_fixes:
            logger.info(f"   ✅ {fix}")
    
    if all_warnings:
        logger.warning(f"⚠️  Validator found {len(all_warnings)} warnings:")
        for warn in all_warnings:
            logger.warning(f"   ⚠️  {warn}")
    
    if not all_fixes and not all_warnings:
        logger.info("✅ Validator: All checks passed, no issues found.")
    
    return {"files": files}
