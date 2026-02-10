from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.coder import coder_agent
from app.agents.tester import tester_agent
from app.agents.debugger import debugger_agent 
from app.agents.architect import architect_agent


def check_test_results(state: AgentState):
    """
    Conditional logic:
    - If tests passed, go to END.
    - If tests failed, go to DEBUGGER.
    - Safety: Stop after 3 debug attempts.
    """
    results = state.get("test_results", {})
    iterations = state.get("debug_iterations", 0)
    
    if results.get("tests_passed", False):
        return "end"
    
    if iterations >= 3:
        print("--- MAX DEBUG ITERATIONS REACHED ---")
        return "end"
        
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
    
    # NEW FLOW: Coder -> Reviewer -> Tester
    workflow.add_edge("coder", "tester")
    
    # Conditional Edge from Tester
    workflow.add_conditional_edges(
        "tester",
        check_test_results,
        {
            "end": END,
            "debugger": "debugger"
        }
    )
    
    # Loop back from Debugger to Tester
    workflow.add_edge("debugger", "tester")

    return workflow.compile()

app = build_graph()