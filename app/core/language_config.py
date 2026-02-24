"""
Language Configuration Registry — Centralized language-specific behavior.

Each agent queries this module to get language-appropriate prompts, rules,
file extensions, and validation checks instead of hardcoding Python assumptions.

To add a new language, simply add a new entry to LANGUAGE_PROFILES.
"""

# =====================================================================
# PYTHON PROFILE
# =====================================================================
_PYTHON_CODER_RULES = """
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
        -   Do NOT use escaped newlines (\\\\n) inside the code string. Write actual newlines.
     
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
        - Correct HTTP status codes (201 for creation, 200 for retrieval, 404 for missing, 422 for validation)
        - Validation errors return 422 with detail array
        - Edge cases (empty input, invalid ID, duplicate entries)
        - Async execution correctness
        - Database persistence (create then read back)
        - All CRUD operations end-to-end

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

    11. **Import Completeness:**
        For every `import X` or `from X import Y` in your code, ensure the corresponding
        package is in `requirements.txt`. The system will auto-check this, but getting it 
        right the first time avoids re-runs.
    
    12. **Output ALL files completely:**
        Never truncate a file mid-function. If a file is long, still output it in full.
        Truncated files cause SyntaxErrors that waste a debug iteration.
    
    13. **MENTAL TEST SIMULATION (FINAL GATE):**
        After generating all files, simulate running `pytest` in your head:
        1. Will `conftest.py` set up the DB and client correctly?
        2. Will each import in each test file resolve?
        3. Will each API call return the expected status code?
        4. Will DB operations persist and be queryable?
        5. Are there any race conditions in async code?
        
        If ANY answer is "no" or "maybe", FIX the code before outputting.
    
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
"""

_NODE_CODER_RULES = """
    1.  **Dependency Safety:**
        -   You MUST generate a `package.json` with ALL dependencies and their versions.
        -   Use exact versions (not ranges) for core dependencies.
        -   Include a `"test"` script in `package.json`: `"test": "npx jest --forceExit --detectOpenHandles"`.
        -   **NEVER use bare `jest` in the test script** — always use `npx jest` to avoid 'jest: not found' errors.
        -   Include a `"start"` script (e.g., `"start": "node server.js"`).
        -   Common dependencies for Express + MongoDB:
            `express`, `mongoose`, `dotenv`, `cors`, `helmet`
        -   Dev dependencies:
            `jest`, `supertest`, `mongodb-memory-server` (for test isolation)
        
    2.  **Configuration & Security:**
        -   NEVER hardcode secrets. Use `process.env.VARIABLE_NAME`.
        -   **YOU MUST generate a `.env` file** with default development values.
        -   Use `dotenv` package and `require('dotenv').config()` at the top of the entry file.
        
    3.  **Project Structure:**
        -   Entry point: `server.js` or `index.js` (start the server) and `app.js` (export the Express app without listening — for testing).
        -   Separate the app creation from the server listen so tests can import the app without starting a server.
        -   Routes in `routes/` directory.
        -   Models in `models/` directory (Mongoose schemas).
        -   Middleware in `middleware/` directory if needed.
        
    4.  **Testing Readiness:**
        -   **YOU MUST generate a `jest.config.js`** for Jest configuration.
        -   **DO NOT put a `jest` key in `package.json` if you also create `jest.config.js`** — this causes a fatal 'Multiple configurations found' error.
        -   Tests go in `__tests__/` or `tests/` directory, or use `.test.js` suffix.
        -   Use `supertest` for HTTP endpoint testing.
        -   Use `mongodb-memory-server` for test DB isolation (in-memory MongoDB).
        -   **Each test file must set up and tear down its own DB connection.**
        
    5.  **MongoDB/Mongoose Best Practices:**
        -   Define schemas with proper validation (required fields, types, defaults).
        -   Use `mongoose.connect()` with proper connection options.
        -   Handle connection errors gracefully.
        -   Close connections properly in server shutdown and test teardown.
        
    6.  **Pre-Flight Quality Checklist (MANDATORY INTERNAL THINKING):**
        Before outputting any files, you MUST internally verify:
        
        - All `require()` / `import` statements match packages in package.json.
        - No missing module files (every require('./X') has a corresponding file).
        - Express routes are properly mounted with `app.use()`.
        - Mongoose models are exported and imported correctly.
        - Error handling middleware is present.
        - Async route handlers use try/catch or express-async-errors.
        
        Think step-by-step internally, but DO NOT output the reasoning.
        Only output final corrected files.
    
    7.  **Test Anticipation Mode:**
        Write code as if strict Jest tests already exist.
        Assume tests will check:
        - Correct HTTP status codes (201 for creation, 200 for retrieval, 404 for missing, 400 for validation)
        - Validation errors return 400 with error message
        - Edge cases (empty input, invalid ID, duplicate entries)
        - Database persistence (create then read back)
        - All CRUD operations end-to-end
    
    8.  **Minimal Surface Area Principle:**
        - Do not generate unnecessary files.
        - Do not introduce extra dependencies.
        - Keep implementation simple and deterministic.

    9.  **Zero-Assumption Rule:**
        If something is not specified in the plan, implement the safest minimal version.
    
    10. **Output ALL files completely:**
        Never truncate a file mid-function. If a file is long, still output it in full.
        Truncated files cause SyntaxErrors that waste a debug iteration.
    
    11. **MENTAL TEST SIMULATION (FINAL GATE):**
        After generating all files, simulate running `npm test` in your head:
        1. Will the test DB setup (mongodb-memory-server) work?
        2. Will each require/import in each test file resolve?
        3. Will each API call return the expected status code?
        4. Will DB operations persist and be queryable?
        5. Will the test teardown close DB connections properly?
        
        If ANY answer is "no" or "maybe", FIX the code before outputting.

    **Output Format:**
    Return the file content wrapped in XML tags exactly like this:
    
    <file path="app.js">
    const express = require('express');
    ...
    </file>
    
    <file path="server.js">
    require('dotenv').config();
    const app = require('./app');
    ...
    </file>
    
    <file path="package.json">
    {
      "name": "my-api",
      "scripts": { "test": "jest", "start": "node server.js" },
      "dependencies": { ... },
      "devDependencies": { ... }
    }
    </file>
"""

# =====================================================================
# LANGUAGE PROFILES (Central Registry)
# =====================================================================
LANGUAGE_PROFILES = {
    "python": {
        # File handling
        "extensions": [".py"],
        "high_priority_ext": (".py",),
        "low_priority_ext": (".txt", ".ini", ".cfg", ".env", ".toml", ".md"),
        "skip_extensions": (".lock", ".png", ".jpg", ".jpeg", ".gif", ".pyc", ".zip", ".tar", ".gz"),
        "package_file": "requirements.txt",

        # Prompt injections
        "coder_rules": _PYTHON_CODER_RULES,

        # Validator config
        "validator_checks": ["mandatory_files", "imports", "truncation", "test_db"],
        "mandatory_files": {
            "pytest.ini": "[pytest]\nasyncio_mode = auto\npython_files = test_*.py\n",
            ".env": "DATABASE_URL=sqlite+aiosqlite:///./dev.db\nSECRET_KEY=dev-secret-key-change-in-production\n",
        },
        "default_package_file_content": "fastapi\nuvicorn\npydantic\nsqlalchemy\naiosqlite\n",

        # Architect fallback
        "fallback_tech": {
            "language": "python",
            "framework": "fastapi",
            "database": "sqlite",
            "orm": "sqlalchemy",
        },
    },

    "node": {
        # File handling
        "extensions": [".js", ".ts", ".mjs", ".cjs"],
        "high_priority_ext": (".js", ".ts", ".mjs", ".cjs"),
        "low_priority_ext": (".json", ".env", ".md", ".yml", ".yaml"),
        "skip_extensions": (".lock", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".map"),
        "package_file": "package.json",

        # Prompt injections
        "coder_rules": _NODE_CODER_RULES,

        # Validator config
        "validator_checks": ["package_json", "truncation_js", "mandatory_files"],
        "mandatory_files": {},
        "default_package_file_content": None,  # LLM must generate valid package.json

        # Architect fallback
        "fallback_tech": {
            "language": "node",
            "framework": "express",
            "database": "mongodb",
            "orm": "mongoose",
        },
    },
}

# Aliases so user can say "javascript", "nodejs", "typescript", etc.
_ALIASES = {
    "javascript": "node",
    "js": "node",
    "node.js": "node",
    "nodejs": "node",
    "node js": "node",
    "typescript": "node",
    "ts": "node",
    "express": "node",
    "express.js": "node",
    "python3": "python",
    "py": "python",
    "flask": "python",
    "fastapi": "python",
    "django": "python",
}


def detect_language(tech_decisions: dict) -> str:
    """
    Detects the canonical language key from tech_decisions.
    Falls back to 'python' if unrecognized.
    """
    raw = tech_decisions.get("language", "python").lower().strip()
    canonical = _ALIASES.get(raw, raw)
    if canonical in LANGUAGE_PROFILES:
        return canonical
    return "python"  # Safe fallback


def get_language_profile(tech_decisions: dict) -> dict:
    """
    Returns the full language profile dict for the detected language.
    """
    lang = detect_language(tech_decisions)
    return LANGUAGE_PROFILES[lang]
