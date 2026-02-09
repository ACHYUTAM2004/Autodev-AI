from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    user_input: Dict[str, Any]
    plan: List[str]
    tech_decisions: Dict[str, str]
    files: Dict[str, str]
    test_results: Dict[str, Any]
    debug_iterations: int # <--- Add this field
    review_report: str
    errors: List[str]