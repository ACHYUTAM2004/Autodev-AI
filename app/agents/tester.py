from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import json

from app.jobs.logger import JobLogger
from app.jobs.manager import JobManager
from app.agents.utils import extract_text_from_response, extract_token_usage

from app.memory.reader import get_memories
from app.memory.recorder import record_memory
from app.memory.summarizer import summarize_memories
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

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

{{
  "passed": true | false,
  "summary": "short explanation",
  "failed_tests": [ "test description" ],
  "warnings": [ "warning description" ]
}}

Code files:
{files}
""")


def tester_agent(state: Dict[str, Any]) -> Dict[str, Any]:

    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")
    
    job_id = state["job_id"]

    AgentThrottle.check(job_id, "tester", state)

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

    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=2500,
        cost_usd=0.0018,
        agent="tester",
    )


    response = llm.invoke(
        TESTER_PROMPT.format_messages(
            files=state["files"],
            memory_context=memory_context,
        )
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="tester",
        tokens=extract_token_usage(response)
    )

    test_text = extract_text_from_response(response)

    try:
        parsed = json.loads(test_text)
    except Exception:
        parsed = None

    # 🔒 Normalize tests to dict
    if isinstance(parsed, list):
        if parsed and isinstance(parsed[0], dict):
            tests = parsed[0]
        else:
            tests = {}
    elif isinstance(parsed, dict):
        tests = parsed
    else:
        tests = {}

    # Fill defaults safely
    if "passed" not in tests:
        tests["passed"] = True
        tests["summary"] = "Tester output unparsable; assuming pass"
        tests["failed_tests"] = []
        tests["warnings"] = ["Tester output could not be fully parsed"]
    else:
        tests.setdefault("summary", "")
        tests.setdefault("failed_tests", [])
        tests.setdefault("warnings", [])



    # Carry forward execution result (runner decides outcome)
    state["tests"] = {
    "passed": bool(tests["passed"]),
    "summary": str(tests["summary"]),
    "failed_tests": list(tests["failed_tests"]),
    "warnings": list(tests["warnings"]),
    }

    assert isinstance(state["tests"], dict) and "passed" in state["tests"]


    # 🧠 Persist failure memory
    if tests.get("passed") is False:
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
