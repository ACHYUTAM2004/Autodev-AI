from typing import Dict, Any, List
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager
from app.agents.utils import extract_text_from_response


REVIEWER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior staff engineer reviewing generated backend code.

Evaluate the following:
- Architecture correctness
- Security issues
- Missing features
- API correctness
- Production readiness

You MUST return JSON ONLY in this exact format:

{
  "verdict": "approve | reject",
  "severity": "none | minor | major | critical",
  "issues": [
    {
      "file": "filename",
      "type": "architecture | security | correctness | style | performance",
      "message": "what is wrong",
      "suggestion": "optional fix suggestion"
    }
  ],
  "summary": "overall assessment"
}

Code files:
{files}
""")


def reviewer_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]

    # 🧭 Progress update
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
        temperature=0
    )

    files = state.get("files", {})

    response = llm.invoke(
        REVIEWER_PROMPT.format_messages(files=files)
    )

    review_text = extract_text_from_response(response,expect_json=True)

    try:
        review = json.loads(review_text)
    except Exception:
        review = {
            "verdict": "reject",
            "severity": "critical",
            "issues": [
                {
                    "file": "unknown",
                    "type": "correctness",
                    "message": "Reviewer returned invalid JSON",
                    "suggestion": "Fix reviewer output format"
                }
            ],
            "summary": "Reviewer failed to produce valid output"
        }

    state["review"] = review

    # 📣 Log verdict
    JobLogger.log(
        job_id=job_id,
        agent="reviewer",
        level="ERROR" if review["verdict"] == "reject" else "INFO",
        message=f"Review verdict: {review['verdict']} – {review['summary']}",
    )
    
    return state
