from datetime import datetime
from app.memory.schemas import MemoryEntry
from app.memory.store import load_memory, save_memory


def record_memory(agent: str, type_: str, payload: dict):
    memory = load_memory(agent)

    entry = MemoryEntry(
        agent=agent,
        type=type_,
        payload=payload,
        timestamp=datetime.utcnow(),
    )

    memory.append(entry.model_dump())
    save_memory(agent, memory)
