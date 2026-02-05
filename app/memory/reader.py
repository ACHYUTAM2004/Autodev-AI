from typing import List, Dict
from app.memory.storage_memory import load_memory
from app.memory.scorer import compute_effective_score, MIN_SCORE_THRESHOLD


def get_memories(
    agent: str,
    type_: str | None = None,
    limit: int = 5,
) -> List[Dict]:

    memories = load_memory(agent, type_)

    scored = []
    for m in memories:
        score = compute_effective_score(m)
        if score >= MIN_SCORE_THRESHOLD:
            m["effective_score"] = round(score, 3)
            scored.append(m)

    scored.sort(key=lambda x: x["effective_score"], reverse=True)
    return scored[:limit]
