from datetime import datetime
import uuid

from app.memory.storage import append_memory


def record_memory(agent: str, type_: str, payload: dict, score: float = 1.0):
    memory = {
        "id": str(uuid.uuid4()),
        "agent": agent,
        "type": type_,
        "payload": payload,

        "score": score,
        "uses": 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_used_at": None,
    }

    append_memory(agent, memory)
