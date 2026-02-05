from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json
import logging

from app.agents.utils import extract_text_from_response, extract_token_usage, normalize_llm_output
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard
from app.jobs.artifacts import save_tech_decisions


logger = logging.getLogger("autodev")


TECH_LEAD_PROMPT = ChatPromptTemplate.from_template("""
You are a senior technical lead.

Given a software development plan and user requirements,
make high-level technical decisions.

Development plan:
{plan}

User requirements:
{requirements}

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.
Do NOT wrap the output in ```.

The JSON must be directly parsable by json.loads().
""")


def tech_lead_agent(state: Dict[str, Any]) -> Dict[str, Any]:

    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")

    job_id = state["job_id"]

    AgentThrottle.check(job_id, "tech_lead", state)

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )

    plan_text = "\n".join(state.get("plan", []))
    requirements = state.get("user_input", {})

    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=2500,
        cost_usd=0.0015,
        agent="tech_lead",
    )

    response = llm.invoke(
        TECH_LEAD_PROMPT.format_messages(
            plan=plan_text,
            requirements=requirements
        )
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="tech_lead",
        tokens=extract_token_usage(response)
    )

    raw_output = extract_text_from_response(response)

    try:
        parsed = json.loads(raw_output)
    except Exception:
        parsed = None

    # 🔒 Normalize to ONE decision object
    if isinstance(parsed, list):
        # take the first valid dict
        tech_decisions = (
            parsed[0]
            if parsed and isinstance(parsed[0], dict)
            else {}
        )
    elif isinstance(parsed, dict):
        tech_decisions = parsed
    else:
        tech_decisions = {}

    # Enforce minimal contract (VERY important)
    tech_decisions.setdefault("architecture", {})
    tech_decisions.setdefault("tech_stack", {})
    tech_decisions.setdefault("decisions", {})
    tech_decisions.setdefault("notes", "")

    # Persist + carry forward
    save_tech_decisions(job_id, tech_decisions)
    state["tech_decisions"] = tech_decisions


    return state
