from typing import Any, Literal, TypedDict


class GraphState(TypedDict):
    # Run configuration.
    run_id: str
    run_config: dict[str, Any]
    temp_dir: str

    # User raw input.
    user_goal: str
    input_files: list[str]

    # Node 1: parse_input outputs.
    modalities: list[Literal["text", "image", "video"]]
    input_artifacts: list[dict[str, Any]]
    extracted_texts: list[str]
    extracted_frames: list[str]

    # Node 2: context assessment / web research outputs.
    needs_web_research: bool
    missing_context_notes: list[str]
    search_queries: list[str]
    web_context: str
    web_sources: list[dict[str, Any]]

    # Node 3: analyze_material outputs.
    task_domain: str
    material_summary: str

    # Node 4: design_skill outputs.
    skill_type: Literal["text", "visual"]
    visual_skill_kind: Literal["text", "static", "dynamic", "interleaved"]
    skill_blueprint: str

    # Node 5: generate_visual outputs.
    visual_prior_paths: list[str]
    visual_prior_descriptions: list[str]

    # Node 6: compose_skill outputs.
    skill_md_content: str

    # Node 7: package_artifact outputs.
    output_dir: str

    # Cross-cutting diagnostics.
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
