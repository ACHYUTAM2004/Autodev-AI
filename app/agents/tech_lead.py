from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.llm import get_llm
from app.graph.state import AgentState

# Define the output parser
parser = JsonOutputParser()

# Tech Lead Prompt - Architecture & Stack Selection
tech_lead_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Technical Lead for AutoDev AI.
    Your goal is to make architectural decisions for a backend software project based on the user's request.
    
    **Your Responsibilities:**
    1. Identify the programming language and framework (e.g., Node/Express, Python/Django, Go/Gin).
    2. Select a database (Default to SQLite if not specified, unless the stack requires something else like MongoDB).
    3. Choose authentication strategy (e.g., JWT, OAuth).
    4. List strictly necessary dependencies (package names).
    
    **Guiding Principles:**
    - If the user did not specify a language, default to Python (FastAPI).
    - If the user did not specify a database, default to SQLite (for relational) or a simple JSON/Memory store (for NoSQL) to keep the generated project self-contained.
    - Keep the architecture simple (MVP) but scalable.
    
    **Output Format:**
    Return a valid JSON object with the following keys:
    {{
        "language": "string",
        "framework": "string",
        "database": "string",
        "auth_method": "string",
        "project_structure": "string (brief description of folder layout)",
        "dependencies": ["list", "of", "package", "names"]
    }}
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Constraints: {constraints}
    Approved Plan: {plan}
    """)
])

def tech_lead_agent(state: AgentState):
    """
    Analyzes the user request and plan to make technical decisions.
    Updates 'tech_decisions' in the state.
    """
    print(f"--- TECH LEAD: Architecting {state['user_input'].get('project_name')} ---")
    
    user_req = state["user_input"]
    plan = state.get("plan", [])
    
    # Tech Lead needs a smarter model to make good architectural choices
    llm = get_llm(temperature=0.1) 
    chain = tech_lead_prompt | llm | parser
    
    try:
        decisions = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {}),
            "plan": plan
        })
        
        # Log the decisions for debugging
        print(f"--> Selected Stack: {decisions.get('language')} / {decisions.get('framework')}")
        
        return {"tech_decisions": decisions}
        
    except Exception as e:
        print(f"Error in Tech Lead Agent: {e}")
        # Fallback default
        return {
            "tech_decisions": {
                "language": "python",
                "framework": "fastapi",
                "database": "sqlite",
                "dependencies": ["fastapi", "uvicorn", "pydantic"]
            }
        }