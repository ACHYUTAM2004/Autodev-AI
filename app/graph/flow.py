from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.planner import planner_agent


def run_autodev_graph(initial_state: AgentState) -> AgentState:
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", END)

    runnable = graph.compile()

    final_state = runnable.invoke(initial_state)
    return final_state
