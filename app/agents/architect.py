from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.core.llm import get_llm
from app.graph.state import AgentState
from app.core.logger import logger
from app.core.language_config import get_language_profile, LANGUAGE_PROFILES

# ---------------------------------------------------------------------
# 1. DEFINE THE OUTPUT SCHEMA (The "Shape" of data we want)
# ---------------------------------------------------------------------
class TechDecisions(BaseModel):
    language: str = Field(description="The programming language (e.g., python, node)")
    framework: str = Field(description="The web framework (e.g., fastapi, flask, express)")
    database: str = Field(description="The database engine (e.g., sqlite, postgresql)")
    orm: str = Field(description="The ORM library (e.g., sqlalchemy, prisma)")

class ArchitectOutput(BaseModel):
    tech_decisions: TechDecisions
    plan: List[str] = Field(description="A step-by-step implementation guide as a list of strings")

# ---------------------------------------------------------------------
# 2. SETUP THE PARSER
# ---------------------------------------------------------------------
# This parser will automatically generate instructions based on the classes above
parser = JsonOutputParser(pydantic_object=ArchitectOutput)

# ---------------------------------------------------------------------
# 3. DEFINE THE PROMPT
# ---------------------------------------------------------------------
architect_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Chief Software Architect at AutoDev AI.
    
    **Goal:** Analyze the user request and produce a comprehensive technical blueprint.
    
    **Responsibilities:**
    1. **Tech Stack Selection:** Choose the Language, Framework, Database, and ORM.
    2. **Implementation Plan:** Create a step-by-step guide to build the application.
    
    **CRITICAL — RESPECT USER CONSTRAINTS:**
    If the user specifies a tech stack in their constraints (e.g., "Node.js", "Express",
    "MongoDB"), you MUST use what they asked for. DO NOT override their choice.
    - If they say "Node.js" or "Express" or "JavaScript" → set language to "node".
    - If they say "Python" or "FastAPI" or "Flask" → set language to "python".
    - If they say "MongoDB" → set database to "mongodb" and orm to "mongoose".
    - If they say "PostgreSQL" → set database to "postgresql".
    - Only make independent choices for fields the user did NOT specify.
    
    **Language field values:**
    - Use "python" for Python projects.
    - Use "node" for Node.js / JavaScript / TypeScript / Express projects.
    
    **Output Format:**
    You must return a JSON object matching the following instructions:
    {format_instructions}
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Tech Constraints: {constraints}
    """)
])

# ---------------------------------------------------------------------
# 4. THE AGENT FUNCTION
# ---------------------------------------------------------------------
def architect_agent(state: AgentState):
    logger.info(f"--- ARCHITECT AGENT: Planning {state['user_input'].get('project_name')} ---")
    user_req = state["user_input"]
    
    # Use a low temperature for consistent, structured output
    llm = get_llm(temperature=0.1) 
    
    # Chain: Prompt -> LLM -> Parser
    chain = architect_prompt | llm | parser
    
    try:
        # We inject the auto-generated format instructions here
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {}),
            "format_instructions": parser.get_format_instructions()
        })
        
        # The parser guarantees 'response' is a valid Python dictionary
        tech = response.get("tech_decisions", {})
        logger.info(f"  Architect chose: {tech}")
        return {
            "plan": response.get("plan", []),
            "tech_decisions": tech
        }
        
    except Exception as e:
        logger.error(f"Architect failed: {e}")
        # Fallback: detect language from constraints, use its default stack
        constraints = user_req.get("constraints", {})
        lang_hint = constraints.get("backend", "python") if isinstance(constraints, dict) else "python"
        fallback_profile = get_language_profile({"language": lang_hint})
        return {
            "plan": ["1. Initialize project structure", "2. Create main entry file"],
            "tech_decisions": fallback_profile["fallback_tech"]
        }