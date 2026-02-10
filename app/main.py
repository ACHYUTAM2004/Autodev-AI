import os
import shutil
import json   
from fastapi import FastAPI, HTTPException
from app.core.schemas import BuildRequest, BuildResponse
from app.core.config import settings
from app.graph.flow import app as graph_app 

api = FastAPI(
    title="AutoDev AI API",
    description="Autonomous Backend Generator Agent",
    version="1.0.0"
)

def save_project_to_disk(project_name: str, files: dict) -> str:
    """Helper to write generated files to disk."""
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    
    os.makedirs(project_path, exist_ok=True)

    for filepath, content in files.items():
        full_path = os.path.join(project_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    return project_path

@api.post("/build", response_model=BuildResponse)
async def build_project(request: BuildRequest):
    print(f"Received build request for: {request.project_name}")

    # INITIALIZE STATE WITH NEW COUNTER
    initial_state = {
        "user_input": request.model_dump(),
        "plan": [],
        "tech_decisions": {},
        "files": {},
        "test_results": {},
        "status": "started",
        "debug_iterations": 0
    }

    try:
        # 1. Run the Graph
        final_state = graph_app.invoke(initial_state)
        
        # 2. Save Code Files
        project_path = save_project_to_disk(
            request.project_name, 
            final_state.get("files", {})
        )

        # 3. Construct Summary
        summary = {
            "project_name": request.project_name,
            "plan": final_state.get("plan", []),
            "tech_stack": final_state.get("tech_decisions", {}),
            "test_results": final_state.get("test_results", {}),
            "files_generated": list(final_state.get("files", {}).keys()),
            "download_path": project_path
        }

        # 4. Save Summary JSON
        summary_path = os.path.join(project_path, "autodev_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        print(f"Saved project summary to: {summary_path}")

        # 5. Return Response
        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))