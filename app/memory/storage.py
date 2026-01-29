from pathlib import Path
from typing import List
from app.memory.schemas import MemoryEntry
import json

MEMORY_DIR = Path("memory_store")
MEMORY_DIR.mkdir(exist_ok=True)


def _memory_file(agent: str) -> Path:
    return MEMORY_DIR / f"{agent}.json"


def load_memory(agent: str) -> List[dict]:
    file = _memory_file(agent)
    if not file.exists():
        return []
    return json.loads(file.read_text())


def save_memory(agent: str, data: List[dict]) -> None:
    file = _memory_file(agent)
    file.write_text(json.dumps(data, indent=2))
