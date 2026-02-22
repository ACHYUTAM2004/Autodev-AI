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
        -   Include a `"test"` script in `package.json` (e.g., `"test": "jest --forceExit --detectOpenHandles"`).
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
        -   **YOU MUST generate a `jest.config.js`** or include jest config in `package.json`.
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
# TESTER PROFILES
# =====================================================================
_PYTHON_TESTER_RULES = """
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
"""

_NODE_TESTER_RULES = """
    **Goal:** 1. Read the provided source code.
    2. Write thorough, deterministic unit tests using Jest + Supertest.
    3. Specify the testing framework (always 'jest' for Node.js).
    
    **Test Quality Rules (CRITICAL):**
    
    1.  **Deterministic Assertions:** NEVER use weak assertions like:
        - `expect(response).toBeDefined()` ← USELESS
        - `expect(response.status).not.toBe(500)` ← TOO WEAK
        
        ALWAYS use EXACT assertions:
        - `expect(response.status).toBe(201)`
        - `expect(response.body.name).toBe("test_item")`
        - `expect(response.body).toHaveLength(1)`
        - `expect(response.body).toHaveProperty("_id")`
    
    2.  **CRUD Coverage:** For every endpoint, test:
        - **Create (POST):** Correct status code (201), response body contains created data
        - **Read (GET):** Returns 200 with correct data, returns 404 for non-existent ID
        - **Update (PUT/PATCH):** Returns updated data, returns 404 for missing
        - **Delete (DELETE):** Returns 200/204, subsequent GET returns 404
        - **Validation:** Invalid input returns 400 with error message
    
    3.  **Edge Cases (MANDATORY):**
        - Empty string inputs where strings are required
        - Non-existent IDs (e.g., invalid MongoDB ObjectId) should return 404 or 400
        - Missing required fields should return 400
        - Duplicate entries if uniqueness is implied
    
    4.  **Test DB Setup (CRITICAL):**
        YOU MUST set up test database isolation:
        - Use `mongodb-memory-server` for an in-memory MongoDB instance
        - Connect to the in-memory DB in `beforeAll`
        - Clear collections in `beforeEach` or `afterEach`
        - Disconnect and stop the server in `afterAll`
        - Import the Express `app` (NOT the server) for use with `supertest`
        
    5.  **Test Isolation:** Each test should be independent. Do not rely on test execution order.
    
    6.  **Package.json test script:** The `package.json` MUST have:
        `"test": "jest --forceExit --detectOpenHandles"`
    
    **Output Format:**
    Do NOT return JSON. Return the test files wrapped in XML-style tags:
    
    <file path="__tests__/todo.test.js">
    const request = require('supertest');
    const app = require('../app');
    ...
    </file>
    
    <framework>jest</framework>
    
    **Important:** - The 'path' must be relative.
    - For Node.js, always use 'jest' as the framework.
    - Do NOT include installation commands.
    - Make sure `supertest` and `mongodb-memory-server` are in devDependencies in package.json.
"""

# =====================================================================
# DEBUGGER PROFILES
# =====================================================================
_PYTHON_DEBUGGER_TAXONOMY = """
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
"""

_NODE_DEBUGGER_TAXONOMY = """
    **EXPANDED ERROR TAXONOMY (MEMORIZE THIS):**
    For each error type, apply the EXACT fix pattern:
    
    | Error Pattern | Root Cause | Fix |
    |---|---|---|
    | `Error: Cannot find module 'X'` | Missing from package.json OR wrong require path | Add to package.json dependencies AND verify the require/import path |
    | `TypeError: X is not a function` | Module doesn't export what you expect, or wrong import | Check module.exports / export, fix the import |
    | `TypeError: Cannot read properties of undefined (reading 'X')` | Object is undefined/null at access time | Add null checks, verify async operations complete before access |
    | `TypeError: X is not a constructor` | Trying to `new` something that isn't a class/constructor | Check if using default vs named export correctly |
    | `MongooseError: Operation ... buffering timed out` | Mongoose not connected when query runs | Ensure `mongoose.connect()` completes before tests run (use beforeAll) |
    | `MongoServerError: E11000 duplicate key` | Unique index violation, test data not cleaned | Clear collections in `beforeEach` / use fresh in-memory DB |
    | `ValidationError: X: Path 'Y' is required` | Mongoose required field missing in request body | Fix the test payload to include all required fields |
    | `CastError: Cast to ObjectId failed` | Invalid MongoDB ObjectId format in URL parameter | Add ObjectId validation in route handler, return 400 |
    | `EADDRINUSE: address already in use` | Server already listening on the port | Don't call `app.listen()` in test files — import app, not server |
    | `ECONNREFUSED` | Test trying to connect to a server that isn't running | Use supertest with app directly, don't make HTTP calls to localhost |
    | `expect(received).toBe(expected)` status mismatch | Wrong status code returned by endpoint | Check route handler, status code sent in `res.status().json()` |
    | `ReferenceError: X is not defined` | Variable/function used before declaration or not imported | Add missing require/import statement |
    | `SyntaxError: Unexpected token` | JS syntax error in source file | Fix the syntax (missing brackets, commas, etc.) |
    | `Jest did not exit` / open handles | DB connections or server not closed after tests | Add `afterAll` to disconnect DB and close server, use `--forceExit` |
    | `connect ECONNREFUSED 127.0.0.1:27017` | Tests trying to use real MongoDB instead of in-memory | Use `mongodb-memory-server` in test setup |
    
    **CONSISTENCY VALIDATION (MANDATORY BEFORE OUTPUT):**
    Before outputting files, verify ALL of these:
    - [ ] package.json includes every `require()`'d third-party package
    - [ ] Every `require('./X')` resolves to an actual file
    - [ ] Test files import the Express `app`, not the `server`
    - [ ] mongodb-memory-server is used for test DB isolation
    - [ ] Environment variables in code match those in .env
    - [ ] All routes are mounted with `app.use()` in the main app file
    - [ ] Mongoose models are properly exported and imported
    - [ ] Error handling middleware is present as the last `app.use()`
    - [ ] All async route handlers have try/catch blocks
    - [ ] No open DB connections or server handles after tests
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

        # Test frameworks
        "default_test_framework": "pytest",
        "test_frameworks": ["pytest", "unittest"],

        # Prompt injections
        "coder_rules": _PYTHON_CODER_RULES,
        "tester_rules": _PYTHON_TESTER_RULES,
        "debugger_taxonomy": _PYTHON_DEBUGGER_TAXONOMY,

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

        # Test frameworks
        "default_test_framework": "jest",
        "test_frameworks": ["jest", "mocha"],

        # Prompt injections
        "coder_rules": _NODE_CODER_RULES,
        "tester_rules": _NODE_TESTER_RULES,
        "debugger_taxonomy": _NODE_DEBUGGER_TAXONOMY,

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
