from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.coder import coder_agent
from app.agents.tester import tester_agent
from app.agents.debugger import debugger_agent 
from app.agents.architect import architect_agent

def check_test_results(state: AgentState):
    """
    Router Logic:
    1. Tests Passed? -> END (Success)
    2. Too many tries? -> END (Give up)
    3. Failure? -> DEBUGGER (Expert Fix)
    """
    results = state.get("test_results", {})
    iterations = state.get("debug_iterations", 0)
    
    # 1. Success Check
    if results.get("tests_passed", False):
        print("✅ Tests Passed! Finishing execution.")
        return "end"
    
    # 2. Safety Limit Check
    if iterations >= 2:
        print("🛑 MAX DEBUG ITERATIONS REACHED. Stopping.")
        return "end"

    # 3. Expert Debugger Check (Direct Route)
    print(f"🚑 Test failure detected (Iter {iterations}). Routing to DEBUGGER.")
    return "debugger"

def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("architect", architect_agent)
    workflow.add_node("coder", coder_agent)
    workflow.add_node("tester", tester_agent)
    workflow.add_node("debugger", debugger_agent)

    # Define Edges
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "coder")
    
    # Standard Flow: Coder -> Tester
    workflow.add_edge("coder", "tester")
    
    # Debugger Flow: Debugger -> Tester (Always verify fixes)
    workflow.add_edge("debugger", "tester")

    # Conditional Logic (The Router)
    workflow.add_conditional_edges(
        "tester",
        check_test_results,
        {
            "end": END,
            "debugger": "debugger" # Removed "coder" path, pure debugging now
        }
    )

    return workflow.compile()

# Compile the app
app = build_graph()