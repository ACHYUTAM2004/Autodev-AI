import json
from pathlib import Path
from typing import Any

BASE_DIR = Path("data/jobs")


def ensure_job_dir(job_id: str) -> Path:
    job_dir = BASE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def write_json(job_id: str, filename: str, data: Any) -> None:
    job_dir = ensure_job_dir(job_id)
    file_path = job_dir / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def read_json(job_id: str, filename: str) -> Any:
    file_path = BASE_DIR / job_id / filename
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
