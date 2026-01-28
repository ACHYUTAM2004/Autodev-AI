from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json

from app.agents.utils import extract_text_from_response


DEBUGGER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software debugger.

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
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )

    tests = state.get("tests")
    if not tests or tests.get("passed", True):
        return state  # no debugging needed

    response = llm.invoke(
        DEBUGGER_PROMPT.format_messages(
            test_failures=tests.get("failures", []),
            files=state.get("files", {}),
        )
    )

    content = extract_text_from_response(response)

    try:
        debug_report = json.loads(content)
    except Exception:
        debug_report = {
            "root_cause": "Unknown",
            "analysis": content,
            "fix_plan": [],
            "confidence": 0.0,
        }

    state["debug"] = debug_report
    return state
