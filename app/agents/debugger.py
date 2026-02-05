from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json

from app.agents.utils import extract_text_from_response, extract_token_usage, normalize_llm_output

from app.memory.reader import get_memories
from app.memory.recorder import record_memory
from app.memory.summarizer import summarize_memories
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

DEBUGGER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software debugger.

Previously successful fixes:
{memory_context}

You are given:
1. Generated source code
2. Test failure reports

Your task:
- Identify the root cause
- Propose precise fixes
- Do NOT rewrite full files
- Do NOT include markdown
- Return ONLY valid JSON

Test failures:
{test_failures}

Generated files:
{files}
""")


def debugger_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")
    
    job_id = state["job_id"]

    AgentThrottle.check(job_id, "debugger", state)

    tests = state.get("tests")
    if not tests or tests.get("passed", True):
        return state  # no debugging needed

    # 🧠 Load debugger memory
    past_successes = get_memories("debugger", type_="patch_success")
    memory_context = summarize_memories(past_successes)

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0,
    )


    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
        state=state,
        tokens_used=4000,
        cost_usd=0.003,
        agent="debugger",
    )

    
    response = llm.invoke(
        DEBUGGER_PROMPT.format_messages(
            test_failures=tests.get("failed_tests", []),
            files=state["files"],
            memory_context=memory_context,
        )
    )

    TokenTracker.add_tokens(
        job_id=state["job_id"],
        agent="debugger",
        tokens=extract_token_usage(response)
    )


    content = extract_text_from_response(response)

    try:
        parsed = json.loads(content)
    except Exception:
        parsed = None

    # 🔒 Normalize debug_report to dict
    if isinstance(parsed, list):
        # take the most confident item if possible
        if parsed and isinstance(parsed[0], dict):
            debug_report = parsed[0]
        else:
            debug_report = {}
    elif isinstance(parsed, dict):
        debug_report = parsed
    else:
        debug_report = {}

    # Fill safe defaults
    debug_report.setdefault("root_cause", "Unknown")
    debug_report.setdefault("analysis", content)
    debug_report.setdefault("fix_plan", [])
    debug_report.setdefault("confidence", 0.0)


    # Carry forward execution hint (NOT persisted)
    state["debug"] = debug_report

    # 🧠 Persist successful patch memory
    if debug_report.get("confidence", 0) >= 0.7:
        record_memory(
            agent="debugger",
            type_="patch_success",
            payload={
                "root_cause": debug_report.get("root_cause"),
                "confidence": debug_report.get("confidence"),
            },
        )

    return state
