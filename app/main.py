import os
import shutil
import json   
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.schemas import BuildRequest
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.graph.flow import app as graph_app 

api = FastAPI(
    title="AutoDev AI API",
    description="Autonomous Backend Generator Agent",
    version="1.0.0"
)

# --- ADD THIS BLOCK ---
api.add_middleware(
    CORSMiddleware,
    # Allow Frontend (3000) AND Reflex Backend (8000)
    allow_origins=["http://localhost:3000", "http://localhost:8000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@api.post("/build")
async def build_project(request: BuildRequest):
    print(f"Received build request for: {request.project_name}")

    initial_state = {
        "user_input": request.model_dump(),
        "plan": [],
        "tech_decisions": {},
        "files": {},
        "test_results": {},
        "status": "started",
        "debug_iterations": 0
    }

    async def event_generator():
        """Yields logs and the final result as a stream."""
        
        # --- FIX 1: Initialize a persistent state container ---
        current_state = initial_state.copy()
        
        # 1. Stream updates from LangGraph
        async for event in graph_app.astream(initial_state):
            for node_name, state_update in event.items():
                
                # --- FIX 2: Merge the new data into current_state ---
                # This ensures we don't lose 'files' when the 'tester' runs
                current_state.update(state_update)
                
                # Yield a log message for the UI
                log_msg = f"🤖 {node_name.upper()} Agent finished task."
                yield json.dumps({"type": "log", "content": log_msg}) + "\n"
                
                # Optional: Yield more specific logs
                if node_name == "planner":
                     yield json.dumps({"type": "log", "content": f"📋 Plan generated with {len(state_update.get('plan', []))} steps."}) + "\n"
                elif node_name == "tester":
                    # Show test results in real-time
                    results = state_update.get("test_results", {})
                    status = "Passed" if results.get("tests_passed") else "Failed"
                    yield json.dumps({"type": "log", "content": f"🧪 Tests {status}"}) + "\n"

        # 2. Save files (Once graph is done)
        yield json.dumps({"type": "log", "content": "💾 Saving project to disk..."}) + "\n"
        
        # --- FIX 3: Get files from the accumulated 'current_state' ---
        files = current_state.get("files", {})
        
        if not files:
            yield json.dumps({"type": "log", "content": "⚠️ Warning: No files found in final state."}) + "\n"
        
        # Save to disk
        project_path = save_project_to_disk(request.project_name, files)

        # 3. Create Summary & Download Link
        summary = {
            "project_name": request.project_name,
            "tech_stack": current_state.get("tech_decisions", {}),
            "test_results": current_state.get("test_results", {}),
            # This URL matches the download endpoint we added earlier
            "download_url": f"http://localhost:8001/download/{request.project_name}" 
        }
        
        # Save Summary JSON inside the project folder
        summary_path = os.path.join(project_path, "autodev_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Yield the final result object to the Frontend
        yield json.dumps({"type": "result", "data": summary}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
