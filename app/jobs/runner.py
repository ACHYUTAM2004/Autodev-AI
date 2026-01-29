import traceback
from typing import Dict, Any

from app.graph.flow import run_autodev_graph
from app.jobs.manager import JobManager
from app.jobs.logger import JobLogger
from app.jobs.storage import write_json
from app.jobs.schemas import JobState


# ----------------------------
# Phase 6C-3 configuration
# ----------------------------
CONFIDENCE_THRESHOLD = 0.7
MAX_PATCHES_PER_RETRY = 2


def run_job(job_id: str, initial_state: Dict[str, Any]) -> None:
    """
    Background job runner.

    Responsibilities:
    - Run LangGraph pipeline
    - Enforce reviewer + tester quality gates
    - Apply debugger patches with confidence ranking
    - Retry bounded times
    - Persist state safely
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

        # ----------------------------
        # Ensure dict input
        # ----------------------------
        state: Dict[str, Any] = (
            initial_state.model_dump()
            if isinstance(initial_state, JobState)
            else initial_state
        )

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        # ===================================
        # 🔁 RETRY LOOP (Phase 6B-3)
        # ===================================
        while retry_count <= max_retries:

            JobLogger.log(
                job_id=job_id,
                agent="system",
                message=f"Execution attempt {retry_count + 1}",
            )

            JobManager.update_progress(
                job_id,
                progress=10 + retry_count * 20,
                current_agent="system",
                current_step=f"Attempt {retry_count + 1}",
            )

            # -----------------------------------
            # Run AutoDev graph
            # -----------------------------------
            final_state_dict = run_autodev_graph(state)

            # -----------------------------------
            # 🔒 REVIEW QUALITY GATE (6A)
            # -----------------------------------
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
                return

            # -----------------------------------
            # 🔒 TESTER QUALITY GATE (6B)
            # -----------------------------------
            tests = final_state_dict.get("tests")
            if tests and not tests.get("passed"):

                retry_count += 1
                final_state_dict["retry_count"] = retry_count

                JobLogger.log(
                    job_id=job_id,
                    agent="tester",
                    level="ERROR",
                    message=f"Tests failed — retry {retry_count}/{max_retries}",
                )

                # -----------------------------------
                # 🧠 DEBUGGER PATCH PRIORITIZATION (6C-3)
                # -----------------------------------
                debug = final_state_dict.get("debug", {})
                all_patches = debug.get("patches", [])

                ranked_patches = sorted(
                    all_patches,
                    key=lambda p: p.get("confidence", 0),
                    reverse=True,
                )

                selected_patches = [
                    p for p in ranked_patches
                    if p.get("confidence", 0) >= CONFIDENCE_THRESHOLD
                ][:MAX_PATCHES_PER_RETRY]

                final_state_dict["patches"] = selected_patches
                final_state_dict["patches_applied"] = len(selected_patches)

                if not selected_patches or retry_count > max_retries:
                    JobLogger.log(
                        job_id=job_id,
                        agent="debugger",
                        level="ERROR",
                        message="No high-confidence patches available — aborting",
                    )

                    JobManager.update_job_status(job_id, "failed")
                    write_json(job_id, "final_state.json", final_state_dict)
                    return

                JobLogger.log(
                    job_id=job_id,
                    agent="debugger",
                    message=f"Applying {len(selected_patches)} high-confidence patch(es)",
                )

                JobManager.update_job_status(job_id, "needs_retry")

                JobManager.update_progress(
                    job_id,
                    progress=60,
                    current_agent="debugger",
                    current_step="Applying fixes",
                )

                # 🔁 Carry patched state forward
                state = final_state_dict
                continue

            # -----------------------------------
            # ✅ SUCCESS
            # -----------------------------------
            final_state = JobState(**final_state_dict)
            final_state.status = "completed"

            JobManager.update_progress(
                job_id,
                progress=100,
                current_agent="system",
                current_step="Completed",
            )

            JobLogger.log(
                job_id=job_id,
                agent="system",
                message="Job execution completed successfully",
            )

            JobManager.update_job(final_state)
            write_json(job_id, "final_state.json", final_state_dict)
            return
    
    except RuntimeError as exc:
        """
        🚫 Governance / Budget violation
        Triggered by BudgetGuard or other hard safety checks.
        """

        JobLogger.log(
            job_id=job_id,
            agent="governance",
            level="ERROR",
            message=str(exc),
        )

        # Persist structured error
        write_json(
            job_id,
            "error.json",
            {
                "error": str(exc),
                "type": "budget_violation",
                "stage": "governance",
            },
        )

        # Update job progress for UI / WS clients
        JobManager.update_progress(
            job_id,
            progress=100,
            current_agent="governance",
            current_step="Budget exceeded — job terminated",
        )

        # Final job status
        JobManager.update_job_status(job_id, "budget_exceeded")

        return  


    except Exception as exc:
        # -----------------------------------
        # Failure handling
        # -----------------------------------
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
