from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, List, Optional


class JobState(BaseModel):
    job_id: str
    status: str
    created_at: datetime

    user_input: Dict[str, Any]

    plan: List[str] = []
    tech_decisions: Dict[str, Any] = {}
    files: Dict[str, str] = {}
    errors: List[str] = []

    # Phase 5C additions
    current_agent: Optional[str] = None
    current_step: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)

    # Phase 6A
    review: Optional[Dict[str, Any]] = None

    # Phase 6B-1
    tests: Optional[Dict[str, Any]] = None
    