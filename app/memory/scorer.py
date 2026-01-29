from datetime import datetime
from math import exp, log
from typing import Dict


HALF_LIFE_DAYS = 7
MIN_SCORE_THRESHOLD = 0.15


def compute_effective_score(memory: Dict) -> float:
    base_score = memory.get("score", 1.0)

    created_at = datetime.fromisoformat(memory["created_at"])
    days_old = (datetime.utcnow() - created_at).days

    # Time decay
    time_decay = exp(-days_old / HALF_LIFE_DAYS)

    # Usage reinforcement
    uses = memory.get("uses", 0)
    usage_boost = 1 + log(1 + uses)

    return base_score * time_decay * usage_boost
