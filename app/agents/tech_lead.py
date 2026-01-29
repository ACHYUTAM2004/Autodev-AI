from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json
import logging

from app.agents.utils import extract_text_from_response
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

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
        tokens=response.usage.total_tokens
    )

    raw_output = extract_text_from_response(response)

    try:
        parsed = json.loads(raw_output)
        state["tech_decisions"] = parsed
        state["status"] = "completed"   # ✅ IMPORTANT
    except json.JSONDecodeError:
        logger.error("❌ Tech Lead JSON parsing failed")
        logger.error(raw_output)

        state["tech_decisions"] = {
            "error": "Failed to parse tech lead output",
            "raw_output": raw_output
        }
        state["status"] = "failed"

    return state
