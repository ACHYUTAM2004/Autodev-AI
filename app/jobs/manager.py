import uuid
from datetime import datetime
from typing import Dict, Any

from app.jobs.schemas import JobState
from app.jobs.storage import write_json, read_json


class JobManager:

    # -------------------------
    # Job lifecycle
    # -------------------------

    @staticmethod
    def create_job(user_input: Dict[str, Any]) -> JobState:
        if isinstance(user_input, dict) and user_input.get("job_id"):
            raise RuntimeError("create_job() called with existing job_id")
        
        job_id = str(uuid.uuid4())

        state = JobState(
            job_id=job_id,
            status="created",
            created_at=datetime.utcnow(),
            user_input=user_input,
        )

        JobManager._persist_state(state)
        return state

    @staticmethod
    def update_job(state: JobState) -> None:
        JobManager._persist_state(state)

    @staticmethod
    def update_job_status(job_id: str, status: str) -> None:
        write_json(job_id, "status.json", status)


    # -------------------------
    # ✅ Phase 5C-1 helpers
    # -------------------------

    @staticmethod
    def update_progress(
        job_id: str,
        *,
        progress: int,
        current_agent: str,
        current_step: str,
    ) -> None:
        payload = {
            "progress": progress,
            "current_agent": current_agent,
            "current_step": current_step,
        }

        write_json(job_id, "progress.json", payload)



    # -------------------------
    # Load job
    # -------------------------

    @staticmethod
    def load_job(job_id: str) -> Dict[str, Any]:
        progress_data = read_json(job_id, "progress.json") or {}

        return {
            "job_id": job_id,
            "status": read_json(job_id, "status.json"),
            "user_input": read_json(job_id, "input.json"),
            "plan": read_json(job_id, "plan.json"),
            "tech_decisions": read_json(job_id, "tech_decisions.json"),
            "files": read_json(job_id, "files.json"),
            "errors": read_json(job_id, "errors.json"),

            # Phase 5C-1
            "progress": progress_data.get("progress", 0),
            "current_agent": progress_data.get("current_agent"),
            "current_step": progress_data.get("current_step"),

            # ✅ Phase 5C-2
            "logs": read_json(job_id, "logs.json") or [],

            # Phase 6A
            "review": read_json(job_id, "review.json"),

            # Phase 6B
            "tests": read_json(job_id, "tests.json"),

            # Phase 6C-1
            "debug": read_json(job_id, "debug.json"),

            # Phase 6C-2
            "patches": read_json(job_id, "patches.json"),

        }


    # -------------------------
    # Persistence
    # -------------------------

    @staticmethod
    def _persist_state(state: JobState) -> None:
        write_json(state.job_id, "status.json", state.status)
        write_json(state.job_id, "input.json", state.user_input)
        write_json(state.job_id, "plan.json", state.plan)
        write_json(state.job_id, "tech_decisions.json", state.tech_decisions)
        write_json(state.job_id, "files.json", state.files)
        write_json(state.job_id, "errors.json", state.errors)
        write_json(state.job_id, "review.json", state.review)
        write_json(state.job_id, "tests.json", state.tests)
        write_json(state.job_id, "debug.json", state.debug)

        write_json(
            state.job_id,
            "progress.json",
            {
                "progress": state.progress,
                "current_agent": state.current_agent,
                "current_step": state.current_step,
            },
        )

        write_json(state.job_id, "patches.json", {
    "count": state.patches_applied
})

