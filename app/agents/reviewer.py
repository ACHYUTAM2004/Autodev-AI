from typing import Dict, Any, List
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager
from app.agents.utils import extract_text_from_response, extract_token_usage, normalize_llm_output

from app.memory.reader import get_memories
from app.memory.recorder import record_memory
from app.memory.summarizer import summarize_memories
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

REVIEWER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior staff engineer reviewing generated backend code.

Past review experience:
{memory_context}

Evaluate the following:
- Architecture correctness
- Security issues
- Missing features
- API correctness
- Production readiness

You MUST return JSON ONLY in this exact format:

{{
  "verdict": "approve | reject",
  "severity": "none | minor | major | critical",
  "issues": [
    {{
      "file": "filename",
      "type": "architecture | security | correctness | style | performance",
      "message": "what is wrong",
      "suggestion": "optional fix suggestion"
    }}
  ],
  "summary": "overall assessment"
}}

Code files:
{files}
""")


def reviewer_agent(state: Dict[str,Any]) -> Dict[str,Any]:

    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")
    
    job_id = state["job_id"]
    review=None

    AgentThrottle.check(job_id, "reviewer", state)

    # 🧠 Load reviewer memory
    past_rejections = get_memories("reviewer", type_="review_rejection")
    memory_context = summarize_memories(past_rejections)

    JobManager.update_progress(
        job_id,
        progress=85,
        current_agent="reviewer",
        current_step="Reviewing generated code",
    )

    JobLogger.log(
        job_id=job_id,
        agent="reviewer",
        message="Reviewer started code review",
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0,
    )

    files = state["files"]

    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=3000,
        cost_usd=0.002,
        agent="reviewer",
    )


    response = llm.invoke(
        REVIEWER_PROMPT.format_messages(
            files=files,
            memory_context=memory_context,
        )
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="reviewer",
        tokens=extract_token_usage(response)
    )

    review_text = extract_text_from_response(response)

    try:
        parsed = json.loads(review_text)
    except Exception:
        parsed = None

    # 🔒 Normalize shape → dict
    if isinstance(parsed, list):
        review = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    elif isinstance(parsed, dict):
        review = parsed
    else:
        review = {}

    # 🔒 Enforce reviewer contract
    review.setdefault("verdict", "reject")
    review.setdefault("severity", "critical")
    review.setdefault("issues", [])
    review.setdefault("summary", "Reviewer returned malformed output")

    # Ensure issues is a list
    if not isinstance(review["issues"], list):
        review["issues"] = []


    # Carry forward execution-only result
    state["review"] = {
    "verdict": str(review["verdict"]),
    "severity": str(review["severity"]),
    "issues": list(review["issues"]),
    "summary": str(review["summary"]),
    }

    assert isinstance(state["review"], dict) and "verdict" in state["review"]


    # 🧠 Persist rejection memory
    if review.get("verdict") == "reject":
        record_memory(
            agent="reviewer",
            type_="review_rejection",
            payload={
                "severity": review.get("severity"),
                "summary": review.get("summary"),
            },
        )

    JobLogger.log(
        job_id=job_id,
        agent="reviewer",
        level="ERROR" if review.get("verdict") == "reject" else "INFO",
        message=f"Review verdict: {review.get('verdict')} – {review.get('summary')}",
    )

    return state

