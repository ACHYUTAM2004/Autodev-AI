from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any


class MemoryEntry(BaseModel):
    agent: str
    type: str
    payload: Dict[str, Any]
    timestamp: datetime
