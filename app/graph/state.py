from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    """
    Represents the shared state of the AutoDev AI graph.
    Based on Phase 1 System Design Page 5.
    """
    # Input
    user_input: Dict[str, Any]       # {project_name, description, constraints}
    
    # Planning & Architecture
    plan: List[str]                  # Steps from Planner Agent
    tech_decisions: Dict[str, str]   # {backend: "FastAPI", db: "sqlite", ...}
    
    # Execution
    files: Dict[str, str]            # Virtual filesystem {filename: content}
    
    # Validation
    test_results: Dict[str, Any]     # {tests_passed: bool, errors: List[str]}
    errors: List[str]                # Stack traces or execution errors
    review_feedback: List[str]       # Quality issues from Reviewer
    
    # Workflow Control
    status: str                      # in_progress, tests_failed, completed