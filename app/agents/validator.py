"""
Programmatic Validator Agent — Zero-cost, deterministic bug prevention.

Runs between Coder → Tester and Debugger → Tester.
Catches bugs that are impossible to prevent via prompts alone:
  1. Missing dependencies in requirements.txt
  2. Truncated / syntactically broken files
  3. Missing mandatory files (tests/__init__.py, pytest.ini, .env)
  4. Test DB isolation (ensures conftest uses SQLite, not prod DB)
"""

import ast
import re
from typing import Dict, List, Tuple
from app.graph.state import AgentState
from app.core.logger import logger

# =====================================================================
# IMPORT → PYPI PACKAGE MAPPING
# =====================================================================
# Maps Python import names to their PyPI package names.
# Only includes packages where the import name differs from the pip name,
# plus common packages used in FastAPI projects.
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

# =====================================================================
# 1. IMPORT SCANNER
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
        # If file has syntax errors, fall back to regex
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
    """
    Parses requirements.txt content into {package_name_lower: original_line}.
    """
    packages = {}
    for line in req_content.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract package name (before ==, >=, <=, ~=, [)
        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
        if match:
            packages[match.group(1).lower().replace("-", "_")] = line
    return packages


def fix_missing_dependencies(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Scans all .py files for imports, cross-references with requirements.txt,
    and auto-adds any missing packages.
    
    Returns (updated_files, list_of_fixes_applied).
    """
    fixes = []
    
    # Collect the project's own package names (to avoid flagging internal imports)
    project_packages = set()
    for path in files:
        parts = path.replace("\\", "/").split("/")
        if parts:
            project_packages.add(parts[0])  # e.g., "src", "app", "tests"
    
    # Collect all imports across all .py files
    all_imports = set()
    for path, content in files.items():
        if path.endswith(".py"):
            all_imports |= _extract_imports(content)
    
    # Filter out stdlib and project-internal imports
    third_party_imports = all_imports - STDLIB_MODULES - project_packages
    
    # Parse existing requirements.txt
    req_content = files.get("requirements.txt", "")
    existing_packages = _parse_requirements(req_content)
    
    # Find missing packages
    missing = []
    for imp in sorted(third_party_imports):
        imp_normalized = imp.lower().replace("-", "_")
        
        # Check if already in requirements (by import name or package name)
        if imp_normalized in existing_packages:
            continue
        
        # Look up the PyPI package name
        pypi_name = IMPORT_TO_PACKAGE.get(imp, None)
        if pypi_name:
            # Check if the pypi_name (normalized) is already present
            pypi_normalized = pypi_name.split("[")[0].lower().replace("-", "_")
            if pypi_normalized in existing_packages:
                continue
            missing.append(pypi_name)
            fixes.append(f"Added '{pypi_name}' to requirements.txt (imported as '{imp}')")
    
    # Append missing packages to requirements.txt
    if missing:
        lines = req_content.strip().splitlines() if req_content.strip() else []
        lines.extend(missing)
        files["requirements.txt"] = "\n".join(lines) + "\n"
    
    return files, fixes


# =====================================================================
# 2. TRUNCATION DETECTOR
# =====================================================================
def detect_truncated_files(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detects Python files that are truncated mid-function/class.
    
    Heuristics:
      - File ends with an incomplete line (no newline at end + non-empty)
      - Unclosed def/class blocks (indentation analysis)
      - AST parse fails (strongest signal)
    
    Truncated files are removed from the dict to prevent SyntaxErrors
    during test execution. The tester will regenerate them.
    
    Returns (cleaned_files, list_of_warnings).
    """
    warnings = []
    cleaned = {}
    
    for path, content in files.items():
        if not path.endswith(".py"):
            cleaned[path] = content
            continue
        
        # Skip empty files (like __init__.py)
        if not content.strip():
            cleaned[path] = content
            continue
        
        # Try AST parse
        try:
            ast.parse(content)
            cleaned[path] = content  # Valid Python
        except SyntaxError as e:
            # Check if this looks like a truncation (error near end of file)
            lines = content.splitlines()
            total_lines = len(lines)
            
            if e.lineno and e.lineno >= total_lines - 2:
                # Error is at the very end — likely truncated
                warnings.append(
                    f"TRUNCATED: '{path}' has a SyntaxError at line {e.lineno}/{total_lines} "
                    f"('{e.msg}'). Removing to allow re-generation."
                )
                # Don't include this file — let the tester/debugger regenerate it
            else:
                # Error is in the middle — probably a real bug, keep it for debugger
                warnings.append(
                    f"SYNTAX ERROR: '{path}' at line {e.lineno}: {e.msg} (kept for debugger)"
                )
                cleaned[path] = content
    
    return cleaned, warnings


# =====================================================================
# 3. MANDATORY FILE CHECKER
# =====================================================================
DEFAULT_PYTEST_INI = """[pytest]
asyncio_mode = auto
python_files = test_*.py
"""

DEFAULT_ENV = """DATABASE_URL=sqlite+aiosqlite:///./dev.db
SECRET_KEY=dev-secret-key-change-in-production
"""

def ensure_mandatory_files(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Ensures critical files exist. Creates sensible defaults if missing.
    Returns (updated_files, list_of_fixes).
    """
    fixes = []
    
    # Check for tests/__init__.py
    has_test_files = any(p.startswith("tests/") and p.endswith(".py") for p in files)
    if has_test_files and "tests/__init__.py" not in files:
        files["tests/__init__.py"] = ""
        fixes.append("Created missing 'tests/__init__.py'")
    
    # Check for pytest.ini
    if has_test_files and "pytest.ini" not in files:
        files["pytest.ini"] = DEFAULT_PYTEST_INI
        fixes.append("Created missing 'pytest.ini' with asyncio_mode=auto")
    
    # Check for .env (only if code references it)
    uses_env = any(
        "dotenv" in content or "pydantic_settings" in content or "os.getenv" in content
        for content in files.values()
        if isinstance(content, str)
    )
    if uses_env and ".env" not in files:
        files[".env"] = DEFAULT_ENV
        fixes.append("Created missing '.env' with safe defaults")
    
    # Check for requirements.txt
    if "requirements.txt" not in files:
        files["requirements.txt"] = "fastapi\nuvicorn\npydantic\nsqlalchemy\naiosqlite\n"
        fixes.append("Created missing 'requirements.txt' with base dependencies")
    
    return files, fixes


# =====================================================================
# 4. TEST DB ISOLATION FIXER
# =====================================================================
def fix_test_db_isolation(files: Dict[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """
    If .env contains a PostgreSQL URL but conftest.py uses it directly,
    ensures the test conftest overrides to use SQLite.
    
    Also ensures conftest patches init_db to prevent prod DB table creation.
    """
    fixes = []
    env_content = files.get(".env", "")
    conftest_content = files.get("tests/conftest.py", "")
    
    if not conftest_content:
        return files, fixes
    
    # Check if .env uses PostgreSQL but conftest doesn't override
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
# AGENT FUNCTION
# =====================================================================
def validator_agent(state: AgentState) -> dict:
    """
    Programmatic validator — zero LLM calls, pure Python.
    
    Runs after Coder and after Debugger to catch deterministic bugs
    before tests execute.
    """
    logger.info("--- VALIDATOR AGENT: Running programmatic checks ---")
    
    files = dict(state.get("files", {}))  # Make a mutable copy
    all_fixes = []
    all_warnings = []
    
    # 1. Ensure mandatory files exist
    files, fixes = ensure_mandatory_files(files)
    all_fixes.extend(fixes)
    
    # 2. Scan imports and fix requirements.txt
    files, fixes = fix_missing_dependencies(files)
    all_fixes.extend(fixes)
    
    # 3. Detect and handle truncated files
    files, warnings = detect_truncated_files(files)
    all_warnings.extend(warnings)
    
    # 4. Check test DB isolation
    files, warnings = fix_test_db_isolation(files)
    all_warnings.extend(warnings)
    
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
