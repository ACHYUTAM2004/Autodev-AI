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
        "status": job["status"] or "unknown",
        "user_input": job["user_input"] or {},
        "plan": job["plan"] or [],
        "tech_decisions": job["tech_decisions"] or {},
        "files": job["files"] or {},
        "errors": job["errors"] or [],
    }
