import traceback
from typing import Dict, Any

from app.graph.flow import run_autodev_graph
from app.jobs.manager import JobManager
from app.jobs.schemas import JobState


def run_job(job_id: str, initial_state: Dict[str, Any]) -> None:
    """
    Background execution entrypoint.
    """

    try:
        # Mark job as running
        JobManager.update_job_status(job_id, "running")

        # Run LangGraph
        final_state_dict = run_autodev_graph(initial_state)

        # Convert back to JobState
        final_state = JobState(**final_state_dict)
        final_state.status = "completed"

        # Persist final state
        JobManager.update_job(final_state)

    except Exception as exc:
        failed_state = JobState(**initial_state)
        failed_state.status = "failed"
        failed_state.errors.append(str(exc))
        failed_state.errors.append(traceback.format_exc())

        JobManager.update_job(failed_state)
