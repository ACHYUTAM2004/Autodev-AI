from datetime import datetime, timezone
from typing import Dict, Any

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager


class AgentThrottle:
    AGENT_LIMITS = {
        "planner": {"cooldown": 0, "max_runs": 1},
        "tech_lead": {"cooldown": 0, "max_runs": 1},
        "coder": {"cooldown": 30, "max_runs": 3},
        "reviewer": {"cooldown": 10, "max_runs": 2},
        "tester": {"cooldown": 10, "max_runs": 2},
        "debugger": {"cooldown": 20, "max_runs": 2},
    }

    @staticmethod
    def check(job_id: str, agent: str, state: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)

        stats = state.setdefault("agent_stats", {})
        agent_stat = stats.setdefault(agent, {"runs": 0, "last_run": None})

        limits = AgentThrottle.AGENT_LIMITS.get(agent)
        if not limits:
            return  # unknown agent → allow

        # ⛔ max runs exceeded
        if agent_stat["runs"] >= limits["max_runs"]:
            JobLogger.log(
                job_id,
                agent="governance",
                level="ERROR",
                message=f"{agent} exceeded max runs ({limits['max_runs']})",
            )
            raise RuntimeError(f"Agent {agent} throttled (max runs exceeded)")

        # ⏳ cooldown check
        last = agent_stat["last_run"]
        if last:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            if elapsed < limits["cooldown"]:
                JobLogger.log(
                    job_id,
                    agent="governance",
                    level="ERROR",
                    message=f"{agent} cooldown active ({limits['cooldown']}s)",
                )
                raise RuntimeError(f"Agent {agent} cooldown active")

        # ✅ record execution
        agent_stat["runs"] += 1
        agent_stat["last_run"] = now.isoformat()

        JobManager.update_job_status(job_id, "running")
