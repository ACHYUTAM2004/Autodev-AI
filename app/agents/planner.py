from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.llm import get_llm
from app.graph.state import AgentState

# Define the output parser to ensure we get a clean JSON list
parser = JsonOutputParser()

# Define the Planner Prompt
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Planner Agent for AutoDev AI.
    Your job is to break down a backend software development task into clear, logical steps.

    **Context:**
    - The user may request **ANY** backend technology (e.g., Python/Django, Node/Express, Go/Gin, Java/Spring).
    - If no specific stack is mentioned, assume a standard modern web framework structure (like Python/FastAPI or Node/Express).
    - The goal is to build a functional backend API.

    **Constraints:**
    - Focus on Backend Development (API, DB, Auth).
    - No Frontend generation (unless strictly required for a minimal template).
    - No Cloud deployment steps (AWS/GCP), focus on local development.

    **Output Format:**
    Return a valid JSON object with a single key "plan" containing a list of strings.
    
    Example (for a Node.js request):
    {{
        "plan": [
            "Initialize Node.js project and install dependencies",
            "Setup Express server and middleware",
            "Design MongoDB schema",
            "Implement User authentication routes",
            "Implement Todo CRUD logic",
            "Write unit tests with Jest"
        ]
    }}

    Example (for a generic/Python request):
    {{
        "plan": [
            "Setup virtual environment and project structure",
            "Install FastAPI and Uvicorn",
            "Define SQLite database models",
            "Create API endpoints for Items",
            "Add Input Validation",
            "Run server and verify endpoints"
        ]
    }}
    """),
    ("user", "Project Name: {project_name}\nDescription: {description}\nUser Constraints: {constraints}")
])

def planner_agent(state: AgentState):
    """
    Orchestrates the planning process.
    Reads user_input -> Generates Plan -> Updates State
    """
    print(f"--- PLANNER AGENT: Generating plan for {state['user_input']['project_name']} ---")
    
    # 1. Retrieve Input
    user_req = state["user_input"]
    
    # 2. Invoke LLM
    llm = get_llm(temperature=0.2) # Slightly creative but structured
    chain = planner_prompt | llm | parser
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {})
        })
        
        # 3. Update State
        # The design doc (Page 2) expects a list of steps
        plan = response.get("plan", [])
        
        return {"plan": plan}
        
    except Exception as e:
        print(f"Error in Planner Agent: {e}")
        # Fallback plan if LLM fails (resilience)
        return {"plan": ["Set up project structure", "Write code", "Test"]}