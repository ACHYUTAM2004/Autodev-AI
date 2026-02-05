from app.jobs.storage import write_json


def save_plan(job_id: str, plan: list[str]) -> None:
    write_json(job_id, "plan.json", plan)


def save_tech_decisions(job_id: str, decisions: dict) -> None:
    write_json(job_id, "tech_decisions.json", decisions)


def save_files(job_id: str, files: dict) -> None:
    write_json(job_id, "files.json", files)


def save_errors(job_id: str, errors: list[str]) -> None:
    write_json(job_id, "errors.json", errors)
