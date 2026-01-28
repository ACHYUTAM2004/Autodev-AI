from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager
from app.agents.utils import extract_text_from_response


TESTER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior QA engineer.

Given the generated backend code files, analyze them and verify:
- API correctness
- Authentication enforcement
- Architecture consistency
- Obvious bugs or broken references

Respond STRICTLY in JSON:

{
  "passed": true | false,
  "summary": "short explanation",
  "failed_tests": [ "test description" ],
  "warnings": [ "warning description" ]
}
""")


def tester_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]

    # 🔍 Progress update
    JobManager.update_progress(
        job_id,
        progress=90,
        current_agent="tester",
        current_step="Running automated tests",
    )

    JobLogger.log(
        job_id=job_id,
        agent="tester",
        message="Tester started validation checks",
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0,
    )

    response = llm.invoke(
        TESTER_PROMPT.format_messages(
            files=state.get("files", {})
        )
    )

    test_results = extract_text_from_response(response, expect_json=True)

    state["tests"] = test_results

    JobLogger.log(
    job_id=job_id,
    agent="tester",
    level="ERROR",
    message="Quality gate failed",
    )


    return state
