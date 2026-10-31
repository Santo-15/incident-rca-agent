from langgraph.graph import StateGraph, START, END
from agent.state import RCAState 

MAX_LOOPS = 2

def triage(state: RCAState) -> dict: 
    return {"loop_count": 0} 

def correlator(state: RCAState) -> dict:  
    loop = state["loop_count"] + 1  
    confidence = "low" if loop == 1 else "high"
    return {"hypothesis": {"cause": "postgres_down", "confidence": confidence}, "loop_count": loop}

def critic(state: RCAState) -> dict:   
    ok = state["hypothesis"]["confidence"] != "low"
    return {"critique": "ok" if ok else "weak: confidence low, look again"}

def route_after_critic(state: RCAState) -> str: 
    if state["critique"] != "ok" and state["loop_count"] < MAX_LOOPS:
        return "correlator"
    return "reporter"

def reporter(state: RCAState) -> dict: 
    h = state["hypothesis"]
    return {"report": f"Root cause: {h['cause']} (confidence {h['confidence']}, correlator ran {state['loop_count']}x)"}

def build_graph():
    builder = StateGraph(RCAState)
    builder.add_node("triage", triage)
    builder.add_node("correlator", correlator)
    builder.add_node("critic", critic)
    builder.add_node("reporter", reporter)
    builder.add_edge(START, "triage")
    builder.add_edge("triage", "correlator")
    builder.add_edge("correlator", "critic")
    builder.add_conditional_edges("critic", route_after_critic, ["correlator", "reporter"])
    builder.add_edge("reporter", END)                
    return builder.compile()

if __name__ == "__main__":
    app = build_graph()
    start = {"alerts": ["PostgresDown", "ShopHigh5xxRatio"]}
    for update in app.stream(start, stream_mode="updates"):
        print("node finished ->", update)
