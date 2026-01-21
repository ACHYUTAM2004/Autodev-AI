from fastapi import APIRouter
from app.graph.flow import run_autodev_graph

router = APIRouter()


@router.post("/build")
def build_project(payload: dict):
    # Initial shared state for the entire agent graph
    initial_state = {
        "user_input": payload,
        "plan": [],
        "tech_decisions": {},
        "files": {},          # ✅ where coder agent will write code
        "errors": [],
        "status": "in_progress"
    }

    final_state = run_autodev_graph(initial_state)

    return {
        "message": "AutoDev pipeline executed successfully",
        "status": final_state.get("status"),

        # Planner output
        "plan": final_state.get("plan"),

        # Tech Lead output
        "tech_decisions": final_state.get("tech_decisions"),

        # Coder output (NEW)
        "files": final_state.get("files"),

        # Optional: surface errors if any agent failed
        "errors": final_state.get("errors")
    }
