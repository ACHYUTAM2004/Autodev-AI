from fastapi import APIRouter
from app.graph.flow import run_autodev_graph
from app.jobs.manager import JobManager

router = APIRouter()


@router.post("/build")
def build_project(payload: dict):
    # 1. Create job
    job_state = JobManager.create_job(payload)

    try:
        # 2. Run pipeline
        final_state = run_autodev_graph(job_state)
        final_state.status = "completed"

    except Exception as e:
        final_state = job_state
        final_state.status = "failed"
        final_state.errors.append(str(e))

    # 3. Persist final state
    JobManager.update_job(final_state)

    return {
        "job_id": final_state.job_id,
        "status": final_state.status
    }
