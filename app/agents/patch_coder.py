from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any
import json

from app.agents.utils import extract_text_from_response
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
    debug = state.get("debug")
    if not debug or not debug.get("fix_plan"):
        return state  # nothing to patch

    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )


    BudgetGuard.check_and_consume(
        job_id=state["job_id"],
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

    content = extract_text_from_response(response)

    try:
        patch_result = json.loads(content)
    except Exception:
        state.setdefault("errors", []).append(
            "Patch coder failed to return valid JSON"
        )
        return state

    patched_files = patch_result.get("files", {})
    if not patched_files:
        return state

    # Apply patches
    for path, new_content in patched_files.items():
        state["files"][path] = new_content

    state["patches_applied"] = state.get("patches_applied", 0) + 1
    return state
