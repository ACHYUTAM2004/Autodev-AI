import uuid
from datetime import datetime
from typing import Dict, Any

from app.jobs.schemas import JobState
from app.jobs.storage import write_json, read_json


class JobManager:

    @staticmethod
    def create_job(user_input: Dict[str, Any]) -> JobState:
        job_id = str(uuid.uuid4())

        state = JobState(
            job_id=job_id,
            status="running",
            created_at=datetime.utcnow(),
            user_input=user_input,
        )

        JobManager._persist_state(state)
        return state

    @staticmethod
    def update_job(state: JobState) -> None:
        JobManager._persist_state(state)

    @staticmethod
    def load_job(job_id: str) -> Dict[str, Any] | None:
        return {
            "job_id": job_id,
            "status": read_json(job_id, "status.json"),
            "user_input": read_json(job_id, "input.json"),
            "plan": read_json(job_id, "plan.json"),
            "tech_decisions": read_json(job_id, "tech_decisions.json"),
            "files": read_json(job_id, "files.json"),
            "errors": read_json(job_id, "errors.json"),
        }

    @staticmethod
    def _persist_state(state: JobState) -> None:
        write_json(state.job_id, "status.json", state.status)
        write_json(state.job_id, "input.json", state.user_input)
        write_json(state.job_id, "plan.json", state.plan)
        write_json(state.job_id, "tech_decisions.json", state.tech_decisions)
        write_json(state.job_id, "files.json", state.files)
        write_json(state.job_id, "errors.json", state.errors)
