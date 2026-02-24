from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.coder import coder_agent
from app.agents.architect import architect_agent
from app.agents.fixer import fixer_agent

def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("architect", architect_agent)
    workflow.add_node("coder", coder_agent)
    workflow.add_node("fixer", fixer_agent)

    # Linear Pipeline: Architect → Coder → Fixer → END
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "coder")
    workflow.add_edge("coder", "fixer")
    workflow.add_edge("fixer", END)

    return workflow.compile()

# Compile the app
app = build_graph()
