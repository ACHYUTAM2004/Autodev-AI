import os
import shutil
from fastapi import FastAPI, HTTPException, BackgroundTasks
from app.core.schemas import BuildRequest, BuildResponse
from app.core.config import settings
from app.graph.flow import app as graph_app # Import our LangGraph

# Initialize FastAPI
api = FastAPI(
    title="AutoDev AI API",
    description="Autonomous Backend Generator Agent",
    version="1.0.0"
)

def save_project_to_disk(project_name: str, files: dict) -> str:
    """
    Helper to write generated files to the 'generated_projects' directory.
    """
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    
    # Clean up existing if needed
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
    os.makedirs(project_path, exist_ok=True)

    for filepath, content in files.items():
        # Construct full path
        full_path = os.path.join(project_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    return project_path

@api.post("/build", response_model=BuildResponse)
async def build_project(request: BuildRequest):
    """
    Triggers the AutoDev AI agent workflow.
    1. Planner decomposes the task.
    2. Tech Lead selects the stack.
    3. Coder generates the files.
    """
    print(f"Received build request for: {request.project_name}")

    # 1. Initialize State
    initial_state = {
        "user_input": request.model_dump(),
        "plan": [],
        "tech_decisions": {},
        "files": {},
        "status": "started"
    }

    try:
        # 2. Run the Graph (Synchronously for MVP simplicity)
        # In a real production app, this would be a background task (Celery/Arq)
        # because LLMs can take 30-60 seconds to complete.
        final_state = graph_app.invoke(initial_state)
        
        # 3. Save Artifacts
        project_path = save_project_to_disk(
            request.project_name, 
            final_state.get("files", {})
        )

        return {
            "project_name": request.project_name,
            "plan": final_state.get("plan", []),
            "tech_stack": final_state.get("tech_decisions", {}),
            "files_generated": list(final_state.get("files", {}).keys()),
            "download_path": project_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# For debugging locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=8000)