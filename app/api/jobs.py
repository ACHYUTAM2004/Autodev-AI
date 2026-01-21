from fastapi import APIRouter, HTTPException
from app.jobs.manager import JobManager

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}")
def get_job(job_id: str):
    job = JobManager.load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
