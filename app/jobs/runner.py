import traceback
from typing import Dict, Any

from app.graph.flow import run_autodev_graph
from app.jobs.manager import JobManager
from app.jobs.logger import JobLogger
from app.jobs.storage import write_json
from app.jobs.schemas import JobState


def run_job(job_id: str, initial_state: Dict[str, Any]) -> None:
    """
    Background job runner.
    Executes LangGraph with dict state and persists results safely.
    """
    try:
        # ----------------------------
        # Job started
        # ----------------------------
        JobManager.update_job_status(job_id, "running")

        JobLogger.log(
            job_id=job_id,
            agent="system",
            message="Job execution started",
        )

        JobManager.update_progress(
            job_id,
            progress=5,
            current_agent="system",
            current_step="Initializing pipeline",
        )

        # ----------------------------
        # 🔥 CRITICAL FIX:
        # LangGraph must ALWAYS receive dict state
        # ----------------------------
        graph_input: Dict[str, Any] = (
            initial_state.model_dump()
            if isinstance(initial_state, JobState)
            else initial_state
        )

        # ----------------------------
        # Run AutoDev graph
        # ----------------------------
        final_state_dict = run_autodev_graph(graph_input)

        # ----------------------------
        # Convert dict → JobState (for persistence)
        # ----------------------------
        final_state = JobState(**final_state_dict)
        final_state.status = "completed"

        JobLogger.log(
            job_id=job_id,
            agent="system",
            message="Job execution completed successfully",
        )

        JobManager.update_progress(
            job_id,
            progress=100,
            current_agent="system",
            current_step="Completed",
        )

        # ----------------------------
        # Persist results
        # ----------------------------
        JobManager.update_job(final_state)
        write_json(job_id, "final_state.json", final_state_dict)

    except Exception as exc:
        # ----------------------------
        # Failure handling
        # ----------------------------
        JobLogger.log(
            job_id=job_id,
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
