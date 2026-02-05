from pathlib import Path
from typing import List, Dict, Optional, Any
import json

from app.memory.schemas_memory import MemoryEntry

MEMORY_DIR = Path("memory_store")
MEMORY_DIR.mkdir(exist_ok=True)


def _memory_file(agent: str) -> Path:
    return MEMORY_DIR / f"{agent}.json"


def load_memory(agent: str, type_: Optional[str] = None) -> List[dict]:
    """
    Load memory entries for an agent.
    Optional type_ filters entries by memory type.
    """

    file = _memory_file(agent)
    if not file.exists():
        return []

    data = json.loads(file.read_text())

    if type_ is None:
        return data

    # 🔍 Filter by memory type
    return [m for m in data if m.get("type") == type_]



def save_memory(agent: str, data: List[dict]) -> None:
    file = _memory_file(agent)
    file.write_text(json.dumps(data, indent=2))


def append_memory(agent: str, entry: Any) -> None:
    memories = load_memory(agent)

    if hasattr(entry, "model_dump"):
        memories.append(entry.model_dump())
    elif isinstance(entry, dict):
        memories.append(entry)
    else:
        memories.append({"value": str(entry)})

    save_memory(agent, memories)


# ✅ NEW: memory usage tracking
def update_memory_usage(agent: str) -> Dict[str, int]:
    """
    Returns basic memory usage statistics for an agent.
    Used by summarizer / governance layers.
    """
    memories = load_memory(agent)

    total_entries = len(memories)
    total_chars = sum(len(json.dumps(m)) for m in memories)

    usage = {
        "entries": total_entries,
        "characters": total_chars,
    }

    # Persist usage snapshot (optional but useful)
    usage_file = MEMORY_DIR / f"{agent}_usage.json"
    usage_file.write_text(json.dumps(usage, indent=2))

    return usage
