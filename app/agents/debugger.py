import re
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger
from app.core.language_config import detect_language, get_language_profile

# ---------------------------------------------------------------------
# 1. DYNAMIC PROMPT (Language-Agnostic Shell + Injected Taxonomy)
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
    - Do not complain that a file is missing. Just output the `<file path="...">` tag with the new content.
    
    **LANGUAGE-SPECIFIC ERROR TAXONOMY:**
    {error_taxonomy}
    
    **FULL ERROR CASCADE ANALYSIS (MANDATORY):**
    After identifying and fixing the first error:
    1. Mentally re-run ALL tests with your fix applied.
    2. Ask: "Does fixing Error #1 unmask Error #2?" (e.g., fixing an import error lets the
       test run further, but then a fixture error appears).
    3. Ask: "Does my fix INTRODUCE any new errors?" (e.g., fixing a schema might break
       a different test that relied on the old schema).
    4. Continue until you are confident ALL tests will pass.
    
    **FILE DEPENDENCY GRAPH (BUILD THIS INTERNALLY):**
    Before writing fixes, mentally map the dependency graph of all files:
    - Which files import/require from which other files?
    - Which test files depend on which source files?
    - Which config files affect runtime behavior?
    
    Verify EVERY edge in this graph is satisfied by the files you output.
    
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
    1. Error: "..."
    2. Cause: ...
    3. Strategy: ...
    4. Cascade: After fixing this, ...
    </plan>
    
    <file path="path/to/file">
    ... full corrected content ...
    </file>
    
    **Rules:**
    - Return the FULL content of any file you modify or create.
    - Do not use markdown blocks (```python or ```javascript) inside the XML tags.
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

    # Sanitize escaped newlines
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    # 1. Extract and Log the Plan
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
# 3. AGENT FUNCTION (Language-Aware)
# ---------------------------------------------------------------------
def debugger_agent(state: AgentState):
    logger.info(f"--- DEBUGGER AGENT: Fixing {state['user_input'].get('project_name')} ---")
    
    existing_files = state.get("files", {})
    test_results = state.get("test_results", {})
    tech_decisions = state.get("tech_decisions", {})
    
    # Get language profile for error taxonomy
    profile = get_language_profile(tech_decisions)
    language = detect_language(tech_decisions)
    logger.info(f"  Debugging for language: {language}")
    
    # 1. Prepare Context
    skip_ext = profile.get("skip_extensions", ())
    file_context_str = ""
    for path, content in existing_files.items():
        if not path.endswith(skip_ext) and not path.endswith(("package-lock.json",)):
            file_context_str += f"\n--- FILE: {path} ---\n{content}\n"

    # 2. Invoke LLM with language-specific error taxonomy
    llm = get_llm(temperature=0.0) 
    chain = debugger_prompt | llm 
    
    try:
        response = chain.invoke({
            "existing_files": file_context_str[:60000], 
            "test_output": test_results.get("output", "No logs available.")[-20000:],
            "debug_iteration": state.get("debug_iterations", 0) + 1,
            "error_taxonomy": profile["debugger_taxonomy"],
        })
        
        # 3. Parse Output
        fixed_files = parse_debugger_output(response.content)
        
        if not fixed_files:
            logger.warning("⚠️ Debugger returned no files. It might have failed to find a fix.")
        else:
            new_paths = set(fixed_files.keys()) - set(existing_files.keys())
            if new_paths:
                logger.info(f"✨ Debugger CREATED new files: {new_paths}")
        
        # 4. Merge Updates
        new_files = {**existing_files, **fixed_files}
        
        return {
            "files": new_files,
            "debug_iterations": state["debug_iterations"] + 1
        }
        
    except Exception as e:
        logger.error(f"❌ Debugger failed: {e}")
        return {"debug_iterations": state["debug_iterations"] + 1}