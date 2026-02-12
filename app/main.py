import os
import shutil
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from app.core.schemas import BuildRequest
from app.core.config import settings
from app.graph.flow import app as graph_app 

api = FastAPI(
    title="AutoDev AI API",
    description="Autonomous Backend Generator Agent",
    version="1.0.0"
)

# --- 1. CORS CONFIGURATION (Render & Localhost Support) ---
api.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # Local Frontend
        "http://localhost:8000",        # Reflex Default
        "https://autodev-ai.onrender.com", # Production URL
        "*"                             # Allow All (Simple fallback)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. HELPER FUNCTIONS ---
def save_project_to_disk(project_name: str, files: dict) -> str:
    """Helper to write generated files to disk."""
    # Ensure base directory exists
    os.makedirs(settings.GENERATION_DIR, exist_ok=True)
    
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    os.makedirs(project_path, exist_ok=True)

    for filepath, content in files.items():
        full_path = os.path.join(project_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
            
    return project_path

# --- 3. DOWNLOAD ENDPOINT (Zip & Serve) ---
@api.get("/download/{project_name}")
async def download_project(project_name: str):
    """
    Zips the generated project and returns it as a downloadable file.
    """
    project_path = os.path.join(settings.GENERATION_DIR, project_name)
    zip_base_name = os.path.join(settings.GENERATION_DIR, project_name)

    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project not found")

    # Create ZIP file (shutil adds .zip extension automatically)
    shutil.make_archive(zip_base_name, 'zip', project_path)
    
    final_zip_path = f"{zip_base_name}.zip"
    
    return FileResponse(
        final_zip_path, 
        media_type='application/zip', 
        filename=f"{project_name}.zip"
    )

# --- 4. BUILD ENDPOINT (Streaming + State Merging) ---
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
        
        # Initialize a persistent state container to avoid overwriting
        current_state = initial_state.copy()
        
        # 1. Stream updates from LangGraph
        async for event in graph_app.astream(initial_state):
            for node_name, state_update in event.items():
                
                # Merge new data (files, plans, test results) into current_state
                current_state.update(state_update)
                
                # Yield a log message for the UI
                log_msg = f"🤖 {node_name.upper()} Agent finished task."
                yield json.dumps({"type": "log", "content": log_msg}) + "\n"
                
                # Yield specific logs
                if node_name == "planner":
                     yield json.dumps({"type": "log", "content": f"📋 Plan generated with {len(state_update.get('plan', []))} steps."}) + "\n"
                elif node_name == "tester":
                    results = state_update.get("test_results", {})
                    status = "Passed" if results.get("tests_passed") else "Failed"
                    yield json.dumps({"type": "log", "content": f"🧪 Tests {status}"}) + "\n"

        # 2. Save & Zip Logic
        yield json.dumps({"type": "log", "content": "💾 Saving and Zipping project..."}) + "\n"
        
        # Get accumulated files
        files = current_state.get("files", {})
        
        if not files:
            yield json.dumps({"type": "log", "content": "⚠️ Warning: No files found in final state."}) + "\n"
        
        # Save to disk
        project_path = save_project_to_disk(request.project_name, files)

        # 3. Create Summary & Download Link
        # The frontend will parse this and fix the domain if needed
        download_url = f"/autodev/download/{request.project_name}"

        summary = {
            "project_name": request.project_name,
            "tech_stack": current_state.get("tech_decisions", {}),
            "test_results": current_state.get("test_results", {}),
            "download_url": download_url 
        }
        
        # Save Summary JSON inside the project folder
        summary_path = os.path.join(project_path, "autodev_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Send final result to UI
        yield json.dumps({"type": "result", "data": summary}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")v