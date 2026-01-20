from fastapi import APIRouter
from app.graph.flow import run_autodev_graph

router = APIRouter()


@router.post("/build")
def build_project(payload: dict):
    initial_state = {
        "user_input": payload,
        "plan": [],
        "tech_decisions": {},
        "files": {},
        "errors": [],
        "status": "in_progress"
    }

    result = run_autodev_graph(initial_state)

    return {
        "message": "Planner + Tech Lead executed successfully",
        "plan": result.get("plan"),
        "tech_decisions": result.get("tech_decisions"),
        "status": result.get("status")
    }
