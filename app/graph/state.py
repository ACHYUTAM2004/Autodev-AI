from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    user_input: Dict[str, Any]
    plan: List[str]
    tech_decisions: Dict[str, str]
    files: Dict[str, str]
    fixes_applied: List[str]  # Log of fixes applied by the Fixer agent