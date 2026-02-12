import os
import re
import subprocess
import sys
from typing import Union, List
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
    2. Write unit tests for it.
    3. Specify the testing framework (e.g., 'pytest', 'unittest').
    
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
    """),
    ("user", """
    Project: {project_name}
    Tech Stack: {tech_stack}
    
    --- SOURCE CODE ---
    {file_context}
    """)
])

# ---------------------------------------------------------------------
# PARSING & SANITIZATION HELPER (FIXED)
# ---------------------------------------------------------------------
def sanitize_content(content: str) -> str:
    content = content.strip()
    
    # 1. Remove wrapping quotes if the LLM added them (JSON style)
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
        
    # 2. Fix literal "\n" to actual newlines
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\n", "\n")
        
    # 3. CRITICAL FIX: Unescape quotes (The error you are seeing)
    # Turns client.post(\'/users\') -> client.post('/users')
    content = content.replace("\\'", "'").replace('\\"', '"')
    
    return content

def parse_tester_output(text: Union[str, list]):
    """Robustly extracts files from LLM output, handling List inputs."""
    
    # --- FIX START: Handle List Input ---
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)
    # --- FIX END ---

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
# EXECUTION HELPERS
# ---------------------------------------------------------------------
def run_command(command: Union[str, List[str]], cwd: str, timeout: int = 300) -> tuple[bool, str]:
    try:
        cmd_str = " ".join(command) if isinstance(command, list) else command
        logger.info(f"--- EXEC: {cmd_str} in {cwd} ---")
        use_shell = isinstance(command, str)
        env = os.environ.copy()
        # Force unbuffered output for Python to capture logs better
        env["PYTHONUNBUFFERED"] = "1" 
        
        result = subprocess.run(
            command, cwd=cwd, shell=use_shell, capture_output=True, text=True, timeout=timeout, env=env
        )
        return result.returncode == 0, result.stdout + "\n" + result.stderr
    except Exception as e:
        logger.error(f"SYSTEM EXECUTION ERROR: {str(e)}")
        return False, str(e)

def setup_and_run_tests(project_name: str, files: dict, framework: str, tech_stack: dict):
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    os.makedirs(project_path, exist_ok=True)
    
    # 1. Write Files (Always write files to capture fixes from Debugger)
    for filepath, content in files.items():
        full_path = os.path.join(project_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 2. Environment Setup
    language = tech_stack.get("language", "python").lower()
    is_windows = sys.platform.startswith("win")
    logs = []
    success = False

    if "python" in language:
        venv_dir = os.path.join(project_path, "venv")
        if is_windows:
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        else:
            python_exe = os.path.join(venv_dir, "bin", "python")
            pip_exe = os.path.join(venv_dir, "bin", "pip")

        # --- OPTIMIZATION START ---
        # A. Create Venv (ONLY if it doesn't exist)
        if not os.path.exists(python_exe):
            logs.append(f"--- Creating Venv (First Run Only) ---")
            ok, out = run_command([sys.executable, "-m", "venv", "venv"], project_path)
            logs.append(out)
            if not ok: return False, "\n".join(logs)

            # Upgrade pip ONLY once (when venv is created)
            logs.append("--- Upgrading Pip (First Run Only) ---")
            run_command([python_exe, "-m", "pip", "install", "--upgrade", "pip"], project_path)
        else:
            logs.append("--- Venv exists, skipping creation ---")

        # B. Install Dependencies (ALWAYS run this to catch new packages)
        logs.append("--- Installing/Updating Dependencies ---")
        # pip install is smart; if requirements haven't changed, this is very fast.
        ok, out = run_command([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], project_path)
        logs.append(out)
        if not ok: return False, "\n".join(logs)

        # C. Install Framework & Tools (Check if installed to save time)
        # We blindly run this because 'pip install' is fast if already satisfied, 
        # but you could optimize further by checking 'pip list'.
        if framework and framework.lower() != "unittest":
            logs.append(f"--- Ensuring {framework} is installed ---")
            run_command([python_exe, "-m", "pip", "install", framework], project_path)
            
            if "fastapi" in tech_stack.get("framework", "").lower():
                 run_command([python_exe, "-m", "pip", "install", "httpx"], project_path)
        # --- OPTIMIZATION END ---

        # D. Run Tests
        logs.append(f"--- Running Tests ({framework}) ---")
        test_cmd = [python_exe, "manage.py", "test"] if "django" in tech_stack.get("framework", "").lower() else [python_exe, "-m", framework]
        
        # Capture the output
        ok, out = run_command(test_cmd, project_path)
        logs.append(out)
        success = ok

    elif "node" in language or "javascript" in language:
        # Node optimization: check for node_modules
        if not os.path.exists(os.path.join(project_path, "node_modules")):
             logs.append("--- Installing Node Dependencies (First Run) ---")
             ok, out = run_command("npm install", project_path)
             if not ok: return False, out
        else:
             # Just run install to catch new packages (npm is usually fast at this)
             logs.append("--- Updating Node Dependencies ---")
             run_command("npm install", project_path)

        logs.append("--- Running Tests ---")
        ok, out = run_command("npm test", project_path)
        logs.append(out)
        success = ok

    # Save logs
    with open(os.path.join(project_path, "test_execution.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(logs))
        
    return success, "\n".join(logs)

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
def tester_agent(state: AgentState):
    logger.info(f"--- TEST AGENT: Verifying {state['user_input'].get('project_name')} ---")
    
    user_req = state["user_input"]
    tech_decisions = state.get("tech_decisions", {})
    existing_files = state.get("files", {})
    tech_stack_str = f"{tech_decisions.get('language')} / {tech_decisions.get('framework')}"

    # Prepare Context
    file_context_str = ""
    for path, content in existing_files.items():
        if not path.endswith((".lock", ".png", ".jpg", ".pyc")):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    llm = get_llm(temperature=0.1)
    chain = tester_prompt | llm 
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "tech_stack": tech_stack_str,
            "file_context": file_context_str[:25000]
        })
        
        # Parse (Now handles lists safely)
        files_dict, framework = parse_tester_output(response.content)
        
        all_files = {**existing_files, **files_dict}
        
        success, output = setup_and_run_tests(user_req.get("project_name"), all_files, framework, tech_decisions)
        
        logger.info(f"Test Execution Result: {'Passed' if success else 'Failed'}")
        
        return {
            "files": all_files,
            "test_results": {
                "tests_passed": success,
                "output": output,
                "command": f"Automated {framework} in venv"
            }
        }
    except Exception as e:
        logger.error(f"Error in Test Agent: {e}")
        return {"test_results": {"tests_passed": False, "output": str(e), "command": "unknown"}}