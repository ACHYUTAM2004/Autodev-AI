from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.planner import planner_agent
from app.agents.tech_lead import tech_lead_agent
from app.agents.coder import coder_agent

# Initialize the Graph with our State schema
workflow = StateGraph(AgentState)

# ---------------------------------------------------------------------
# ADD NODES
# ---------------------------------------------------------------------
# Each node represents an agent function we defined earlier
workflow.add_node("planner", planner_agent)
workflow.add_node("tech_lead", tech_lead_agent)
workflow.add_node("coder", coder_agent)

# ---------------------------------------------------------------------
# DEFINE EDGES (The Control Flow)
# ---------------------------------------------------------------------
# 1. Start with the Planner [cite: 130-131]
workflow.set_entry_point("planner")

# 2. Planner -> Tech Lead [cite: 132-133]
workflow.add_edge("planner", "tech_lead")

# 3. Tech Lead -> Coder [cite: 134-135]
workflow.add_edge("tech_lead", "coder")

# 4. Coder -> END (For now. Later this will go to "tester")
workflow.add_edge("coder", END)

# ---------------------------------------------------------------------
# COMPILE
# ---------------------------------------------------------------------
app = workflow.compile()