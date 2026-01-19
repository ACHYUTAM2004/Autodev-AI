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
        "test_results": {},
        "errors": [],
        "review_feedback": [],
        "status": "in_progress",
    }

    result = run_autodev_graph(initial_state)

    return {
        "message": "Build process finished",
        "status": result["status"],
    }
