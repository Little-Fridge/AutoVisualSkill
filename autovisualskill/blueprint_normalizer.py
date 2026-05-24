from __future__ import annotations

from typing import Any, Mapping

from autovisualskill.models.skill import SkillBlueprint, VisualPriorSpec
from autovisualskill.utils import issue_record


def normalize_skill_blueprint(
    blueprint: SkillBlueprint,
    state: Mapping[str, Any],
) -> tuple[SkillBlueprint, list[dict[str, Any]]]:
    """Make LLM-authored blueprint routing and prior specs internally consistent.

    The design prompt asks the model to choose skill_type, visual_skill_kind,
    prior_kind, and visual prior strategies. This pass keeps the graph from
    executing impossible combinations, such as a dynamic prior with a static
    drawn asset or a source/crop prior that points at a missing frame.
    """

    warnings: list[dict[str, Any]] = []
    frame_count = len(state.get("extracted_frames", []) or [])

    def warn(message: str, **details: Any) -> None:
        warnings.append(issue_record("design_skill", message, **details))

    if blueprint.skill_type == "text" or blueprint.visual_skill_kind == "text":
        if (
            blueprint.skill_type != "text"
            or blueprint.visual_skill_kind != "text"
            or blueprint.prior_kind != "none"
            or blueprint.visual_prior_specs
        ):
            warn(
                "Normalized text skill to skip visual prior generation",
                original_skill_type=blueprint.skill_type,
                original_visual_skill_kind=blueprint.visual_skill_kind,
                original_prior_kind=blueprint.prior_kind,
                dropped_visual_prior_count=len(blueprint.visual_prior_specs),
            )
        return (
            blueprint.model_copy(
                update={
                    "skill_type": "text",
                    "visual_skill_kind": "text",
                    "prior_kind": "none",
                    "bottleneck": "none",
                    "visual_prior_specs": [],
                },
                deep=True,
            ),
            warnings,
        )

    specs = list(blueprint.visual_prior_specs)
    dynamic_required = (
        blueprint.visual_skill_kind == "dynamic"
        or blueprint.prior_kind == "dynamic"
        or blueprint.bottleneck == "perceptual_tracking"
        or any(spec.prior_kind == "dynamic" or spec.strategy == "renderer" for spec in specs)
    )

    if dynamic_required:
        if not specs:
            specs = [_default_dynamic_spec(blueprint)]
            warn("Added missing dynamic renderer spec")

        normalized_specs: list[VisualPriorSpec] = []
        for spec in specs:
            updates: dict[str, Any] = {}
            if spec.prior_kind != "dynamic":
                updates["prior_kind"] = "dynamic"
            if spec.strategy != "renderer":
                updates["strategy"] = "renderer"
            if not spec.renderer_name:
                updates["renderer_name"] = f"{spec.name}_renderer"
            if not spec.renderer_description:
                updates["renderer_description"] = spec.content_description
            if not spec.renderer_inputs:
                updates["renderer_inputs"] = [
                    "base task image",
                    "runtime visual state",
                    "coordinate mode",
                    "visual style configuration",
                ]
            if not spec.renderer_outputs:
                updates["renderer_outputs"] = [
                    "overlay image with rendered runtime state",
                    "optional machine-readable render manifest",
                ]
            if updates:
                warn(
                    "Normalized dynamic visual prior spec to renderer",
                    prior_name=spec.name,
                    updates=sorted(updates),
                )
                spec = spec.model_copy(update=updates, deep=True)
            normalized_specs.append(spec)

        if (
            blueprint.skill_type != "visual"
            or blueprint.visual_skill_kind != "dynamic"
            or blueprint.prior_kind != "dynamic"
        ):
            warn(
                "Normalized blueprint to dynamic visual skill",
                original_skill_type=blueprint.skill_type,
                original_visual_skill_kind=blueprint.visual_skill_kind,
                original_prior_kind=blueprint.prior_kind,
            )
        return (
            blueprint.model_copy(
                update={
                    "skill_type": "visual",
                    "visual_skill_kind": "dynamic",
                    "prior_kind": "dynamic",
                    "visual_prior_specs": normalized_specs,
                },
                deep=True,
            ),
            warnings,
        )

    normalized_specs = _normalize_static_specs(specs, frame_count, warn)
    if not normalized_specs and blueprint.skill_type == "visual":
        fallback = _default_static_spec(blueprint, frame_count)
        normalized_specs = [fallback]
        warn(
            "Added missing static visual prior spec",
            prior_name=fallback.name,
            strategy=fallback.strategy,
        )

    if normalized_specs:
        visual_skill_kind = blueprint.visual_skill_kind
        if visual_skill_kind not in {"static", "interleaved"}:
            visual_skill_kind = "static"
        if blueprint.skill_type != "visual" or blueprint.prior_kind != "static":
            warn(
                "Normalized blueprint to static visual skill",
                original_skill_type=blueprint.skill_type,
                original_prior_kind=blueprint.prior_kind,
            )
        return (
            blueprint.model_copy(
                update={
                    "skill_type": "visual",
                    "visual_skill_kind": visual_skill_kind,
                    "prior_kind": "static",
                    "visual_prior_specs": normalized_specs,
                },
                deep=True,
            ),
            warnings,
        )

    warn("Normalized empty visual blueprint to text skill")
    return (
        blueprint.model_copy(
            update={
                "skill_type": "text",
                "visual_skill_kind": "text",
                "prior_kind": "none",
                "bottleneck": "none",
                "visual_prior_specs": [],
            },
            deep=True,
        ),
        warnings,
    )


def _normalize_static_specs(
    specs: list[VisualPriorSpec],
    frame_count: int,
    warn: Any,
) -> list[VisualPriorSpec]:
    normalized: list[VisualPriorSpec] = []
    for spec in specs:
        updates: dict[str, Any] = {}
        if spec.prior_kind != "static":
            updates["prior_kind"] = "static"

        if spec.strategy in {"source", "crop", "overlay"}:
            if not _valid_frame_index(spec.source_frame_index, frame_count):
                if frame_count > 0:
                    repaired_index = min(max(spec.source_frame_index, 0), frame_count - 1)
                    updates["source_frame_index"] = repaired_index
                    warn(
                        "Repaired source/crop/overlay frame index",
                        prior_name=spec.name,
                        original_source_frame_index=spec.source_frame_index,
                        repaired_source_frame_index=repaired_index,
                        available_frames=frame_count,
                    )
                else:
                    updates.update(
                        {
                            "strategy": "draw",
                            "source_frame_index": -1,
                            "crop_region_description": "",
                            "draw_instructions": spec.draw_instructions
                            or spec.content_description,
                        }
                    )
                    warn(
                        "Converted invalid source/crop/overlay prior to draw strategy",
                        prior_name=spec.name,
                        original_strategy=spec.strategy,
                        original_source_frame_index=spec.source_frame_index,
                        available_frames=frame_count,
                    )
            if spec.strategy == "overlay" and not spec.draw_instructions.strip():
                updates["draw_instructions"] = spec.content_description
                warn("Filled missing overlay instructions", prior_name=spec.name)
        elif spec.strategy == "search" and not spec.search_query.strip():
            updates["search_query"] = spec.content_description
            warn("Filled missing image search query", prior_name=spec.name)
        elif spec.strategy == "draw" and not spec.draw_instructions.strip():
            updates["draw_instructions"] = spec.content_description
            warn("Filled missing draw instructions", prior_name=spec.name)
        elif spec.strategy == "api" and not spec.image_generation_prompt.strip():
            updates["image_generation_prompt"] = spec.content_description
            warn("Filled missing image-generation prompt", prior_name=spec.name)

        if updates:
            spec = spec.model_copy(update=updates, deep=True)
        normalized.append(spec)
    return normalized


def _valid_frame_index(index: int, frame_count: int) -> bool:
    return 0 <= index < frame_count


def _default_dynamic_spec(blueprint: SkillBlueprint) -> VisualPriorSpec:
    return VisualPriorSpec(
        name=f"{blueprint.name}_renderer",
        prior_kind="dynamic",
        strategy="renderer",
        content_description=blueprint.description,
        visual_rationale=(
            "Externalize runtime visual state directly onto the task image so "
            "the next step can inspect visible progress instead of relying on "
            "hidden memory."
        ),
        visual_encodings=[
            "Rendered overlay mark = runtime state from the current task",
            "Compact marker = active frontier or newly updated state",
        ],
        text_exclusions=[
            "Detailed procedure and stop conditions belong in Markdown text",
            "Task answers and fixed coordinates must not be burned into the image",
        ],
        forbidden_elements=[
            "static template routes",
            "long prose instructions",
            "answer-like coordinates",
        ],
        renderer_name=f"{blueprint.name}_renderer",
        renderer_description=blueprint.description,
        renderer_inputs=[
            "base task image",
            "runtime visual state",
            "coordinate mode",
            "visual style configuration",
        ],
        renderer_outputs=[
            "overlay image with rendered runtime state",
            "optional machine-readable render manifest",
        ],
    )


def _default_static_spec(blueprint: SkillBlueprint, frame_count: int) -> VisualPriorSpec:
    if frame_count > 0:
        return VisualPriorSpec(
            name=f"{blueprint.name}_source_reference",
            prior_kind="static",
            strategy="source",
            content_description=blueprint.description,
            source_frame_index=0,
            visual_rationale=(
                "Reuse the provided source frame as the visual reference because "
                "the blueprint did not specify an explicit static prior."
            ),
            visual_encodings=["Source frame = visual grounding for the skill"],
            text_exclusions=["Procedural explanation belongs in Markdown text"],
            forbidden_elements=["new hallucinated diagrams"],
        )
    return VisualPriorSpec(
        name=f"{blueprint.name}_visual_prior",
        prior_kind="static",
        strategy="draw",
        content_description=blueprint.description,
        draw_instructions=blueprint.description,
        visual_rationale=(
            "Provide a minimal abstract visual prior because the blueprint did "
            "not specify one."
        ),
        visual_encodings=["Simple shapes and spatial markers encode the visual convention"],
        text_exclusions=["Detailed procedure belongs in Markdown text"],
        forbidden_elements=["long prose blocks", "answer-like coordinates"],
    )
