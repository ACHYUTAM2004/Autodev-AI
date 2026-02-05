from app.agents.planner import planner_agent
from app.agents.tech_lead import tech_lead_agent
from app.agents.coder import coder_agent
from app.agents.reviewer import reviewer_agent
from app.agents.tester import tester_agent
from app.agents.debugger import debugger_agent
from app.agents.patch_coder import patch_coder_agent

from langgraph.graph import StateGraph,END
from app.jobs.schemas import JobState
from typing import Dict, Any


def tester_gate(state: Dict[str, Any]) -> str:
    tests = state.get("tests") or {}
    return "pass" if tests.get("passed") else "fail"

def reviewer_gate(state: Dict[str, Any]) -> str:
    review = state.get("review") or {}
    return "approve" if review.get("verdict") == "approve" else "reject"


def normalize_state(state: Any) -> Dict[str, Any]:
    if isinstance(state, JobState):
        return state.model_dump()
    if isinstance(state, dict):
        return state
    raise TypeError(f"Invalid state type: {type(state)}")


def run_autodev_graph(state: Dict[str, Any]) -> Dict[str, Any]:
    graph = StateGraph(dict)

    graph.add_node("normalize", normalize_state)
    graph.add_node("planner", planner_agent)
    graph.add_node("tech_lead", tech_lead_agent)
    graph.add_node("coder", coder_agent)
    graph.add_node("reviewer", reviewer_agent)
    graph.add_node("tester", tester_agent)
    graph.add_node("debugger", debugger_agent)
    graph.add_node("patch_coder", patch_coder_agent)

    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "planner")
    graph.add_edge("planner", "tech_lead")
    graph.add_edge("tech_lead", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges(
    "reviewer",
    reviewer_gate,
    {
        "approve": "tester",
        "reject": "debugger",
    },
    )
    graph.add_edge("tester", "debugger")
    graph.add_edge("debugger", "patch_coder")

    # 🔥 HARD QUALITY GATE
    graph.add_conditional_edges(
    "tester",
    tester_gate,
    {
        "pass": END,
        "fail": "debugger",
    },
    )


    runnable = graph.compile()
    return runnable.invoke(state)
