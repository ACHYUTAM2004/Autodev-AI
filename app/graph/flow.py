from langgraph.graph import StateGraph, END
from app.graph.state import AgentState

from app.agents.planner import planner_agent
from app.agents.tech_lead import tech_lead_agent


def run_autodev_graph(initial_state: AgentState) -> AgentState:
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)
    graph.add_node("tech_lead", tech_lead_agent)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "tech_lead")
    graph.add_edge("tech_lead", END)

    runnable = graph.compile()
    return runnable.invoke(initial_state)
