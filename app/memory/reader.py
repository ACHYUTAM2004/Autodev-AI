from typing import List, Dict
from app.memory.store import load_memory


def get_memories(agent: str, type_: str | None = None) -> List[Dict]:
    memories = load_memory(agent)
    if type_:
        return [m for m in memories if m["type"] == type_]
    return memories
