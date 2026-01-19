from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict):
    user_input: Dict[str, Any]
    plan: List[str]
    tech_decisions: Dict[str, Any]
    files: Dict[str, str]
    test_results: Dict[str, Any]
    errors: List[str]
    review_feedback: List[str]
    status: str
