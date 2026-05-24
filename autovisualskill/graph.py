from langgraph.graph import END, START, StateGraph

from autovisualskill.nodes import (
    analyze_material,
    assess_context,
    compose_skill,
    design_skill,
    generate_visual,
    package_artifact,
    parse_input,
    research_context,
)
from autovisualskill.state import GraphState


def route_by_skill_type(state: GraphState) -> str:
    return state["skill_type"]


def route_by_context_need(state: GraphState) -> str:
    config = state.get("run_config", {})
    if config.get("enable_web_research", True) and state.get("needs_web_research"):
        return "research"
    return "skip"


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("parse_input", parse_input.run)
    builder.add_node("assess_context", assess_context.run)
    builder.add_node("research_context", research_context.run)
    builder.add_node("analyze_material", analyze_material.run)
    builder.add_node("design_skill", design_skill.run)
    builder.add_node("generate_visual", generate_visual.run)
    builder.add_node("compose_skill", compose_skill.run)
    builder.add_node("package_artifact", package_artifact.run)

    builder.add_edge(START, "parse_input")
    builder.add_edge("parse_input", "assess_context")
    builder.add_conditional_edges(
        "assess_context",
        route_by_context_need,
        {"research": "research_context", "skip": "analyze_material"},
    )
    builder.add_edge("research_context", "analyze_material")
    builder.add_edge("analyze_material", "design_skill")

    builder.add_conditional_edges(
        "design_skill",
        route_by_skill_type,
        {"visual": "generate_visual", "text": "compose_skill"},
    )
    builder.add_edge("generate_visual", "compose_skill")
    builder.add_edge("compose_skill", "package_artifact")
    builder.add_edge("package_artifact", END)

    return builder.compile()


app = build_graph()
