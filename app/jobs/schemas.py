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

    # Phase 6B
    tests: Optional[Dict[str, Any]] = None

    # Phase 6C-1
    debug: Optional[Dict[str,Any]] = None

    # Phase 6C-2
    patches_applied: int = 0

    # Phase 6B-3
    retry_count: int = 0
    max_retries: int = 2

    # Phase 6C-3
    patches: List[Dict[str,Any]] = []



    