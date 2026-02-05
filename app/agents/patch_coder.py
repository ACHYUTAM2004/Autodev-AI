from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json

from app.agents.utils import extract_text_from_response, extract_token_usage
from app.governance.token_tracker import TokenTracker
from app.governance.agent_throttle import AgentThrottle
from app.governance.budget_guard import BudgetGuard

PATCH_CODER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software engineer applying targeted fixes.

You are given:
1. Existing source files
2. A debugger fix plan

Rules:
- Modify ONLY the files listed in the fix plan
- Apply ONLY the requested changes
- Do NOT refactor unrelated code
- Return ONLY valid JSON
- Output format:
  {
    "files": {
      "path/to/file.py": "updated content"
    }
  }

Fix plan:
{fix_plan}

Current files:
{files}
""")

def patch_coder_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    
    if not isinstance(state, dict):
        raise TypeError(f"Agent received non-dict state: {type(state)}")

    job_id = state["job_id"]

    AgentThrottle.check(job_id, "patch_coder", state)

    debug = state.get("debug")
    if not debug or not debug.get("fix_plan"):
        return state  # nothing to patch

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )

    BudgetGuard.check_and_consume(
        job_id=job_id,
        state=state,
        tokens_used=3500,
        cost_usd=0.0025,
        agent="patch_coder",
    )

    response = llm.invoke(
        PATCH_CODER_PROMPT.format_messages(
            fix_plan=json.dumps(debug["fix_plan"], indent=2),
            files=state.get("files", {}),
        )
    )

    TokenTracker.add_tokens(
        job_id=job_id,
        agent="patch_coder",
        tokens=extract_token_usage(response),
    )

    content = extract_text_from_response(response)

    try:
        parsed = json.loads(content)
    except Exception:
        state.setdefault("errors", []).append(
            "Patch coder failed to return valid JSON"
        )
        return state

    # 🔒 Normalize patch_result → dict
    if isinstance(parsed, list):
        patch_result = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    elif isinstance(parsed, dict):
        patch_result = parsed
    else:
        patch_result = {}

    # 🔒 Normalize files payload
    patched_files = patch_result.get("files", {})

    if not isinstance(patched_files, dict):
        patched_files = {}

    # Ensure all values are strings
    patched_files = {
        path: content
        for path, content in patched_files.items()
        if isinstance(path, str) and isinstance(content, str)
    }

    if not patched_files:
        return state


    # 🔒 Return patch intent in runner-compatible format
    state["patches"] = [
        {
            "files": patched_files,
            "confidence": 0.85,  # optimistic but safe default
            "reason": "Applied debugger fix plan"
        }
    ]

    state["patches_applied"] = state.get("patches_applied", 0) + 1

    state["last_patch_reason"] = debug.get("reason", "Unknown")

    return state
