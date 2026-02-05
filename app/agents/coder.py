from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json
import logging

from app.agents.utils import extract_text_from_response,extract_token_usage, normalize_llm_output
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard
from app.jobs.artifacts import save_files


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

    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")

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
        tokens=extract_token_usage(response)
    )

    raw_output = extract_text_from_response(response)

    try:
        parsed = json.loads(raw_output)
    except Exception:
        logger.error("❌ Coder JSON parsing failed")
        logger.error(raw_output)
        state.setdefault("errors", []).append("Invalid JSON from coder")
        return state

    # 🔒 Normalize shape → dict
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    elif not isinstance(parsed, dict):
        parsed = {}

    # 🔒 Extract files payload
    if "files" in parsed and isinstance(parsed["files"], dict):
        files = parsed["files"]
    else:
        # allow direct file map
        files = parsed

    # 🔒 Enforce Dict[str, str]
    files = {
        path: content
        for path, content in files.items()
        if isinstance(path, str) and isinstance(content, str)
    }

    if not files:
        logger.error("❌ Coder produced no files")
        logger.error(raw_output)
        state.setdefault("errors", []).append("Coder produced no files")
        return state
    
    # 🔒 Ensure files is pure Dict[str, str]
    files = {
        path: content
        for path, content in files.items()
        if isinstance(path, str) and isinstance(content, str)
    }

    # 🔒 Persist + carry forward
    save_files(job_id, files)
    state["files"] = files


    return state
