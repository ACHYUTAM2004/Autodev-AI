from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any

from app.agents.utils import extract_text_from_response
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

PLANNER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software engineer acting as a planner.

Given a project description, break it down into a clear,
ordered list of development steps.

Project description:
{description}

Return ONLY a numbered list of steps.
""")


def planner_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]

    AgentThrottle.check(job_id, "planner", state)

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )


    description = state.get("user_input", {}).get("description", "")

    from app.governance.budget_guard import BudgetGuard

    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=1500,
        cost_usd=0.001,
        agent="planner",
    )

    response = llm.invoke(
        PLANNER_PROMPT.format_messages(description=description)
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="planner",
        tokens=response.usage.total_tokens
    )

    content = extract_text_from_response(response)

    plan = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        cleaned = line.strip("0123456789. )")
        if cleaned:
            plan.append(cleaned)

    state["plan"] = plan
    return state
