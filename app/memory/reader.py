from typing import List, Dict
from app.memory.storage import load_memories
from app.memory.scorer import compute_effective_score, MIN_SCORE_THRESHOLD


def get_memories(
    agent: str,
    type_: str | None = None,
    limit: int = 5,
) -> List[Dict]:

    memories = load_memories(agent, type_)

    scored = []
    for m in memories:
        score = compute_effective_score(m)
        if score >= MIN_SCORE_THRESHOLD:
            m["effective_score"] = round(score, 3)
            scored.append(m)

    scored.sort(key=lambda x: x["effective_score"], reverse=True)
    return scored[:limit]
