from langgraph.graph import StateGraph, START, END
from agent.state import MAX_LOOPS, RCAState
from agent.nodes.triage import triage
from agent.nodes.logs_agent import logs_agent
from agent.nodes.metrics_agent import metrics_agent
from agent.nodes.deploy_agent import deploy_agent, diff_agent
from agent.nodes.correlator import correlator
from agent.nodes.critic import critic
from agent.nodes.reporter import reporter


def route_after_critic(state: RCAState) -> str:
    if state["critique"].startswith("weak") and state["loop_count"] < MAX_LOOPS:   # KEY: loop back only if weak AND under the limit
        return "correlator"
    return "reporter"


def build_graph():
    builder = StateGraph(RCAState)
    for name, fn in [("triage", triage), ("logs_agent", logs_agent), ("metrics_agent", metrics_agent),
                     ("deploy_agent", deploy_agent), ("diff_agent", diff_agent), ("correlator", correlator),
                     ("critic", critic), ("reporter", reporter)]:
        builder.add_node(name, fn)
    builder.add_edge(START, "triage")
    for agent in ("logs_agent", "metrics_agent", "deploy_agent"):   # KEY: fan-out, these 3 run in parallel
        builder.add_edge("triage", agent)
    builder.add_edge("deploy_agent", "diff_agent")   # diff needs the tags deploy_agent found
    builder.add_edge(["logs_agent", "metrics_agent", "diff_agent"], "correlator")   # KEY: join, correlator waits for all three
    builder.add_edge("correlator", "critic")
    builder.add_conditional_edges("critic", route_after_critic, ["correlator", "reporter"])
    builder.add_edge("reporter", END)
    return builder.compile()


if __name__ == "__main__":
    print(build_graph().get_graph().draw_mermaid())   # paste into a ```mermaid block to see the graph
