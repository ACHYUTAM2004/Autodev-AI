import re
from typing import Union, List
from langchain_core.prompts import ChatPromptTemplate
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger
from app.core.language_config import get_language_profile, detect_language

# ---------------------------------------------------------------------
# 1. DYNAMIC PROMPT (Language-Agnostic Shell + Injected Rules)
# ---------------------------------------------------------------------
coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Senior Full-Stack Developer at AutoDev AI.
    
    **Goal:** Write production-ready, clean, and SECURE code based on the Architect's plan.
    Your code MUST pass automated tests on the FIRST attempt with ZERO debugging iterations.
    
    **Input Context:**
    - **Stack:** {tech_stack}
    - **Architecture:** {architecture}
    - **Plan:** {plan}
    
    **LANGUAGE-SPECIFIC RULES (FOLLOW EXACTLY):**
    {language_rules}
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Constraints: {constraints}
    """)
])

# ---------------------------------------------------------------------
# 2. PARSING & SANITIZATION HELPER
# ---------------------------------------------------------------------
def sanitize_content(content: str) -> str:
    """Cleans up common LLM formatting errors."""
    content = content.strip()
    
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
    elif content.startswith("'") and content.endswith("'"):
        content = content[1:-1]
        
    if "\\n" in content and "\n" not in content:
        logger.warning("Detected escaped newlines in single-line output. Fixing...")
        content = content.replace("\\n", "\n")
        
    return content

def parse_xml_output(text: Union[str, List]) -> dict:
    """Extracts file paths and content using Regex."""
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text)

    pattern = r'<file\s+path="([^"]+)">\s*(.*?)\s*</file>'
    matches = re.findall(pattern, text, re.DOTALL)
    
    files = {}
    for path, content in matches:
        files[path] = sanitize_content(content)
        
    return files

# ---------------------------------------------------------------------
# 3. AGENT FUNCTION (Language-Aware)
# ---------------------------------------------------------------------
def coder_agent(state: AgentState):
    user_req = state["user_input"]
    plan = state.get("plan", [])
    tech_decisions = state.get("tech_decisions", {})
    
    logger.info(f"--- CODER AGENT: Writing code for {user_req.get('project_name')} ---")

    # Detect language and get profile
    profile = get_language_profile(tech_decisions)
    language = detect_language(tech_decisions)
    logger.info(f"  Language detected: {language}")

    # Context Variables
    stack_str = f"{tech_decisions.get('language', 'Python')} using {tech_decisions.get('framework', 'FastAPI')}"
    arch_str = f"Database: {tech_decisions.get('database', 'SQLite')}, Auth: {tech_decisions.get('auth', 'None')}"
    plan_str = "\n".join(plan) if isinstance(plan, list) else str(plan)
    
    # Invoke LLM with language-specific rules injected
    llm = get_llm(temperature=0.0) 
    chain = coder_prompt | llm 
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {}),
            "tech_stack": stack_str,
            "architecture": arch_str,
            "plan": plan_str,
            "language_rules": profile["coder_rules"],
        })

        files_dict = parse_xml_output(response.content)
        
        if not files_dict:
            logger.warning("Coder Agent produced no files. Raw output snippet:")
            raw = response.content
            if isinstance(raw, list): raw = "".join(str(x) for x in raw)
            logger.warning(raw[:500])
        
        logger.info(f"Coder generated {len(files_dict)} files.")
        
        # Return files only (Iteration logic handled elsewhere)
        return {
            "files": files_dict
        }
        
    except Exception as e:
        logger.error(f"Error in Coder Agent: {e}")
        return {"errors": [f"Coder Agent failed: {str(e)}"]}