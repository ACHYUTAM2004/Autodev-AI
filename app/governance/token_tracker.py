from app.jobs.storage import read_json, write_json
from app.governance.budgets import (
    AGENT_BUDGETS,
    JOB_MAX_TOKENS,
)

class TokenTracker:

    @staticmethod
    def add_tokens(job_id: str, agent: str, tokens: int):
        data = read_json(job_id, "tokens.json") or {}

        data.setdefault("total", 0)
        data.setdefault("agents", {})
        data["agents"].setdefault(agent, 0)

        data["total"] += tokens
        data["agents"][agent] += tokens

        # 🔒 Enforce agent budget
        if data["agents"][agent] > AGENT_BUDGETS.get(agent, 0):
            raise RuntimeError(
                f"Agent '{agent}' exceeded token budget"
            )

        # 🔒 Enforce job budget
        if data["total"] > JOB_MAX_TOKENS:
            raise RuntimeError("Job exceeded maximum token budget")

        write_json(job_id, "tokens.json", data)
