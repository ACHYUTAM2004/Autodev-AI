from datetime import datetime, timezone
from typing import List, Dict

from app.jobs.storage import read_json, write_json


class JobLogger:
    @staticmethod
    def log(
        job_id: str,
        *,
        message: str,
        agent: str = "system",
        level: str = "INFO",
    ) -> None:
        logs: List[Dict] = read_json(job_id, "logs.json") or []

        logs.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "agent": agent,
                "message": message,
            }
        )

        write_json(job_id, "logs.json", logs)
