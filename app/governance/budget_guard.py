from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager


class BudgetGuard:
    @staticmethod
    def check_and_consume(
        *,
        job_id: str,
        state: dict,
        tokens_used: int,
        cost_usd: float,
        agent: str,
    ) -> None:

        state["token_usage"] = state.get("token_usage", 0) + tokens_used
        state["cost_usd"] = state.get("cost_usd", 0.0) + cost_usd

        if state["token_usage"] > state.get("max_tokens", 0):
            BudgetGuard._violation(
                job_id,
                agent,
                f"Token budget exceeded ({state['token_usage']})",
            )

        if state["cost_usd"] > state.get("max_cost_usd", 0):
            BudgetGuard._violation(
                job_id,
                agent,
                f"Cost budget exceeded (${state['cost_usd']:.2f})",
            )

    @staticmethod
    def _violation(job_id: str, agent: str, reason: str) -> None:
        JobLogger.log(
            job_id=job_id,
            agent="governance",
            level="ERROR",
            message=f"Budget violation by {agent}: {reason}",
        )

        JobManager.update_job_status(job_id, "budget_exceeded")
        raise RuntimeError("Job terminated due to budget violation")
