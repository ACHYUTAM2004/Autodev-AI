from fastapi import APIRouter, HTTPException
from app.jobs.manager import JobManager

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}")
def get_job(job_id: str):
    job = JobManager.load_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
    "job_id": job["job_id"],
    "status": job["status"],

    "progress": job["progress"],
    "current_agent": job["current_agent"],
    "current_step": job["current_step"],

    "logs": job["logs"],
    "review": job["review"],
    "tests": job["tests"],

    "plan": job["plan"],
    "tech_decisions": job["tech_decisions"],
    "files": job["files"],
    "errors": job["errors"],
}




