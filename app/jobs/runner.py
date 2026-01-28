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
    Executes LangGraph with dict state and enforces quality gates.
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
        # Ensure dict input for LangGraph
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
        # 🔒 REVIEW QUALITY GATE (Phase 6A)
        # ----------------------------
        review = final_state_dict.get("review")
        if review and review.get("verdict") != "approve":
            JobLogger.log(
                job_id=job_id,
                agent="reviewer",
                level="ERROR",
                message="Reviewer rejected the generated code",
            )

            JobManager.update_job_status(job_id, "blocked_review")
            write_json(job_id, "final_state.json", final_state_dict)
            return  # ⛔ STOP PIPELINE

        # ----------------------------
        # 🔒 TESTER QUALITY GATE (Phase 6B)
        # ----------------------------
        tests = final_state_dict.get("tests")
        if tests and not tests.get("passed"):
            JobLogger.log(
                job_id=job_id,
                agent="tester",
                level="ERROR",
                message="Tester quality gate failed",
            )

            JobManager.update_progress(
                job_id,
                progress=100,
                current_agent="tester",
                current_step="Quality gate failed",
            )

            JobManager.update_job_status(job_id, "failed")
            write_json(job_id, "final_state.json", final_state_dict)
            return  # ⛔ STOP PIPELINE

        # ----------------------------
        # ✅ Job success
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