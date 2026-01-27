from fastapi import APIRouter, BackgroundTasks
from app.jobs.manager import JobManager
from app.jobs.runner import run_job

router = APIRouter(prefix="/build", tags=["Build"])


@router.post("")
def build_project(payload: dict, background_tasks: BackgroundTasks):
    # 1. Create job
    job_state = JobManager.create_job(payload)

    # 2. Run job in background
    background_tasks.add_task(
        run_job,
        job_state.job_id,
        job_state.model_dump()
    )

    return {
        "job_id": job_state.job_id,
        "status": "created",
        "message": "Job submitted successfully",
    }
