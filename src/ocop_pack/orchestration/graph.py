from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ocop_pack.orchestration.state import PackagingState


def _passthrough(state: PackagingState) -> PackagingState:
    return state


def build_graph() -> Any:
    graph = StateGraph(PackagingState)
    for node in [
        "validate_input",
        "plan_design",
        "generate_artworks",
        "generate_layout_candidates",
        "apply_hard_constraints",
        "rank_deterministically",
        "render_candidate_previews",
        "select_default_candidate",
        "run_draft_qa",
        "await_human_approval",
        "render_final_outputs",
        "run_final_qa",
        "export_bundle",
    ]:
        graph.add_node(node, _passthrough)
    graph.add_edge(START, "validate_input")
    graph.add_edge("validate_input", "plan_design")
    graph.add_edge("plan_design", "generate_artworks")
    graph.add_edge("generate_artworks", "generate_layout_candidates")
    graph.add_edge("generate_layout_candidates", "apply_hard_constraints")
    graph.add_edge("apply_hard_constraints", "rank_deterministically")
    graph.add_edge("rank_deterministically", "render_candidate_previews")
    graph.add_edge("render_candidate_previews", "select_default_candidate")
    graph.add_edge("select_default_candidate", "run_draft_qa")
    graph.add_edge("run_draft_qa", "await_human_approval")
    graph.add_edge("await_human_approval", "render_final_outputs")
    graph.add_edge("render_final_outputs", "run_final_qa")
    graph.add_edge("run_final_qa", "export_bundle")
    graph.add_edge("export_bundle", END)
    return graph.compile()
