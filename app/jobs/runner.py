import traceback
from typing import Dict, Any

from app.graph.flow import run_autodev_graph
from app.jobs.manager import JobManager
from app.jobs.logger import JobLogger
from app.jobs.storage import write_json


def run_job(job_id: str, initial_state: Dict[str, Any]) -> None:
    try:
        JobManager.update_job_status(job_id, "running")

        JobLogger.log(
            job_id,
            agent="system",
            message="Job execution started",
        )

        JobManager.update_progress(
            job_id,
            progress=5,
            current_agent="system",
            current_step="Initializing pipeline",
        )

        final_state = run_autodev_graph(initial_state)

        JobLogger.log(
            job_id,
            agent="system",
            message="Job execution completed successfully",
        )

        JobManager.update_progress(
            job_id,
            progress=100,
            current_agent="system",
            current_step="Completed",
        )

        write_json(job_id, "final_state.json", final_state)
        JobManager.update_job_status(job_id, "completed")

    except Exception as exc:
        JobLogger.log(
            job_id,
            agent="system",
            level="ERROR",
            message=str(exc),
        )

        write_json(
            job_id,
            "error.json",
            {
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )

        JobManager.update_job_status(job_id, "failed")
