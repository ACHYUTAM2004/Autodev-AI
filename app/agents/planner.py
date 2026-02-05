from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any

from app.agents.utils import extract_text_from_response, extract_token_usage, normalize_llm_output
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard
from app.jobs.artifacts import save_plan

PLANNER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software engineer acting as a planner.

Given a project description, break it down into a clear,
ordered list of development steps.

Project description:
{description}

Return ONLY a numbered list of steps.
""")


def planner_agent(state: Dict[str, Any]) -> Dict[str, Any]:

    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")

    job_id = state["job_id"]

    AgentThrottle.check(job_id, "planner", state)

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )


    description = state.get("user_input", {}).get("description", "")


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
        tokens=extract_token_usage(response)
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

    # 🔒 Persist immediately (authoritative)
    save_plan(job_id, plan)

    # Carry forward only what next agents need
    state["plan"] = plan
    return state

