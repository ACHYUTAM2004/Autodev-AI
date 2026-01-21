from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime


class JobState(BaseModel):
    job_id: str
    status: str
    created_at: datetime

    user_input: Dict[str, Any]

    plan: List[str] = []
    tech_decisions: Dict[str, Any] = {}
    files: Dict[str, str] = {}

    errors: List[str] = []
