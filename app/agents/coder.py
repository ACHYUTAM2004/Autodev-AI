from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.llm import get_llm
from app.graph.state import AgentState

# Define the output parser to ensure we get structured file data
parser = JsonOutputParser()

# ---------------------------------------------------------------------
# CODER PROMPT (Polyglot)
# ---------------------------------------------------------------------
coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are the Coder Agent for AutoDev AI.
    Your job is to generate production-ready code files based on a Technical Design.

    **Input Context:**
    - **Language/Framework:** {tech_stack} (Strict adherence required)
    - **Architecture:** {architecture}
    - **Plan:** Follow these steps strictly: {plan}

    **Guidelines:**
    1. **Complete Implementation:** Generate fully functional code, not pseudocode.
    2. **Project Structure:** Return the file paths exactly as they should appear in the project root (e.g., "app/main.py", "src/User.java").
    3. **Dependencies:** Ensure you include a dependency management file (e.g., `requirements.txt` for Python, `package.json` for Node, `go.mod` for Go).
    4. **Standard Practices:** Use best practices for the chosen stack (e.g., modular routing for Express, Pydantic models for FastAPI).

    **Output Format:**
    Return a STRICT JSON object containing a list of files.
    
    Example Output:
    {{
        "files": [
            {{
                "path": "requirements.txt",
                "content": "fastapi\\nuvicorn\\n"
            }},
            {{
                "path": "main.py",
                "content": "from fastapi import FastAPI\\napp = FastAPI()\\n..."
            }}
        ]
    }}
    """),
    ("user", """
    Project Name: {project_name}
    Description: {description}
    User Constraints: {constraints}
    """)
])

# ---------------------------------------------------------------------
# AGENT FUNCTION
# ---------------------------------------------------------------------
def coder_agent(state: AgentState):
    """
    Generates the actual code files.
    Reads: Plan, Tech Decisions
    Writes: Files (to state)
    """
    print(f"--- CODER AGENT: Writing code for {state['user_input'].get('project_name')} ---")
    
    # 1. Retrieve Context
    user_req = state["user_input"]
    plan = state.get("plan", [])
    tech_decisions = state.get("tech_decisions", {})
    
    # Format tech stack string for the prompt
    stack_str = f"{tech_decisions.get('language', 'Python')} using {tech_decisions.get('framework', 'FastAPI')}"
    arch_str = f"Database: {tech_decisions.get('database', 'SQLite')}, Auth: {tech_decisions.get('auth', 'None')}"
    
    # 2. Invoke LLM
    # We use temperature=0.0 for deterministic code generation (as per design goal) 
    llm = get_llm(temperature=0.0)
    chain = coder_prompt | llm | parser
    
    try:
        response = chain.invoke({
            "project_name": user_req.get("project_name"),
            "description": user_req.get("description"),
            "constraints": user_req.get("constraints", {}),
            "tech_stack": stack_str,
            "architecture": arch_str,
            "plan": "\n".join(plan)
        })
        
        # 3. Update State
        # Convert list of file dicts to the state's dictionary format {path: content}
        generated_files = {}
        if "files" in response and isinstance(response["files"], list):
            for file_obj in response["files"]:
                path = file_obj.get("path")
                content = file_obj.get("content")
                if path and content:
                    generated_files[path] = content
        
        print(f"--> Generated {len(generated_files)} files.")
        
        return {"files": generated_files}
        
    except Exception as e:
        print(f"Error in Coder Agent: {e}")
        return {"errors": [f"Coder Agent failed: {str(e)}"]}