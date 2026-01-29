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


CODER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software engineer.

Using the development plan and technical decisions,
generate the full backend project code.

Development plan:
{plan}

Technical decisions:
{tech_decisions}

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

The JSON format MUST be:

{{
  "files": {{
    "app/main.py": "...",
    "app/api/example.py": "...",
    "app/models/example.py": "..."
  }}
}}
""")


def coder_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]

    AgentThrottle.check(job_id, "coder", state)

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )
    

    plan_text = "\n".join(state.get("plan", []))
    tech_decisions = json.dumps(state.get("tech_decisions", {}), indent=2)

    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=6000,
        cost_usd=0.004,
        agent="coder",
    )

    response = llm.invoke(
        CODER_PROMPT.format_messages(
            plan=plan_text,
            tech_decisions=tech_decisions
        )
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="coder",
        tokens=response.usage.total_tokens
    )

    raw_output = extract_text_from_response(response)

    try:
        parsed = json.loads(raw_output)
        files = parsed.get("files", {})

        if not isinstance(files, dict):
            raise ValueError("files must be a dictionary")

        state["files"] = files
        state["status"] = "completed"

    except Exception as e:
        logger.error("❌ Coder agent failed")
        logger.error(raw_output)

        state["errors"].append(str(e))
        state["status"] = "failed"

    return state
