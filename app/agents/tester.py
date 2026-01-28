from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import json

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager
from app.agents.utils import extract_text_from_response

from app.memory.reader import get_memories
from app.memory.recorder import record_memory
from app.memory.summarizer import summarize_memories


TESTER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior QA engineer.

Known failure patterns:
{memory_context}

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

Code files:
{files}
""")


def tester_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    job_id = state["job_id"]

    # 🧠 Load tester memory
    past_failures = get_memories("tester", type_="test_failure")
    memory_context = summarize_memories(past_failures)

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
            files=state.get("files", {}),
            memory_context=memory_context,
        )
    )

    test_text = extract_text_from_response(response, expect_json=True)

    try:
        tests = json.loads(test_text)
    except Exception:
        tests = {
            "passed": False,
            "summary": "Tester returned invalid JSON",
            "failed_tests": ["Invalid tester output"],
            "warnings": [],
        }

    state["tests"] = tests

    # 🧠 Persist failure memory
    if not tests.get("passed", True):
        record_memory(
            agent="tester",
            type_="test_failure",
            payload={
                "summary": tests.get("summary"),
                "failed_tests": tests.get("failed_tests", []),
            },
        )

        JobLogger.log(
            job_id=job_id,
            agent="tester",
            level="ERROR",
            message="Quality gate failed",
        )

    return state
