from app.agents.planner import planner_agent
from app.agents.tech_lead import tech_lead_agent
from app.agents.coder import coder_agent

from langgraph.graph import StateGraph
from app.jobs.schemas import JobState
from typing import Dict, Any


def run_autodev_graph(state: Dict[str, Any]) -> Dict[str, Any]:
    graph = StateGraph(dict)

    graph.add_node("planner", planner_agent)
    graph.add_node("tech_lead", tech_lead_agent)
    graph.add_node("coder", coder_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "tech_lead")
    graph.add_edge("tech_lead", "coder")

    runnable = graph.compile()
    return runnable.invoke(state)
