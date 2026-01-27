from datetime import datetime
from app.jobs.storage import append_json


class JobLogger:
    @staticmethod
    def log(
        job_id: str,
        agent: str,
        message: str,
        level: str = "info",
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "level": level,
            "message": message,
        }

        # ✅ ONLY persist log
        append_json(job_id, "logs.json", log_entry)
