#!/usr/bin/env python3
"""Tiny mock backend for AutoVisualSkill smoke tests.

It implements the external subagent protocol used by `autovisualskill.llm.subagent_client`
and returns schema-shaped responses without calling a real model.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> None:
    request = json.load(sys.stdin)
    mode = request.get("mode")
    schema_name = request.get("schema_name", "")
    messages = request.get("messages", [])
    goal = _extract_goal(messages)
    frame_count = _extract_frame_count(messages)
    flattened_messages = "\n".join(_flatten_text(message.get("content")) for message in messages)
    has_interleaved_blueprint = '"visual_skill_kind":"interleaved"' in flattened_messages.replace(" ", "")
    lowered_goal = goal.lower()
    wants_interleaved = (
        "interleaved" in lowered_goal
        or (frame_count > 0 and "video" in lowered_goal)
    ) or (schema_name == "SkillMarkdown" and has_interleaved_blueprint)

    if mode == "chat":
        print(json.dumps({"content": "Mock subagent response."}, ensure_ascii=False))
        return

    skill_blueprint = (
        _interleaved_skill_blueprint(source_available=frame_count > 0)
        if wants_interleaved
        else _text_skill_blueprint()
    )
    skill_markdown = (
        _interleaved_skill_markdown(source_available=frame_count > 0)
        if wants_interleaved
        else _text_skill_markdown()
    )

    responses = {
        "ContextAssessmentOutput": {
            "needs_web_research": False,
            "missing_context_notes": [],
            "search_queries": [],
        },
        "AnalyzeMaterialOutput": {
            "task_domain": "general",
            "material_summary": f"Mock subagent analyzed the request: {goal}",
        },
        "SkillBlueprint": skill_blueprint,
        "SkillMarkdown": {"markdown": skill_markdown},
        "CropCoordinates": {
            "left": 0,
            "top": 0,
            "right": 10,
            "bottom": 10,
            "explanation": "Mock crop.",
        },
        "DrawingCode": {
            "python_code": (
                "from PIL import Image\n"
                "img = Image.new('RGB', (64, 64), 'white')\n"
                "img.save(output_path)\n"
            ),
            "explanation": "Mock drawing.",
        },
        "ImageSelection": {
            "selected_index": 0,
            "reason": "Mock selection.",
        },
        "VideoFrameSelection": {
            "selected_indices": _mock_video_frame_selection(messages),
            "rationale": "Mock selected evenly spaced 1 FPS candidates while preserving the final frame.",
        },
    }

    response = responses.get(schema_name)
    if response is None:
        response = _response_from_schema(request.get("schema", {}))
    print(json.dumps({"data": response}, ensure_ascii=False))


def _text_skill_blueprint() -> dict[str, Any]:
    return {
        "name": "mock_reproducibility_check_skill",
        "skill_type": "text",
        "visual_skill_kind": "text",
        "prior_kind": "none",
        "bottleneck": "none",
        "description": "A smoke-test text skill generated through the external subagent backend.",
        "declarative_textual_logic": [
            "Identify the claim being checked.",
            "Verify whether the report includes enough metadata to reproduce the result.",
            "Return missing items as actionable checklist entries.",
        ],
        "visual_prior_specs": [],
        "binding_protocol": {
            "image_roles": [],
            "coordinate_system": "",
            "text_to_visual_binding": [],
            "task_binding_rules": [],
            "anti_leakage_rules": [],
        },
        "runtime_protocol": {
            "mode": "single_turn",
            "state_schema": "",
            "update_rule": "Read one report and emit one checklist.",
            "stop_condition": "Stop after the checklist is complete.",
            "renderer_spec": "",
        },
        "parameters": [
            {
                "name": "report_text",
                "type": "string",
                "description": "Experiment report or claim to audit.",
            }
        ],
        "execution_steps": [
            "Read the report carefully.",
            "Extract model, data, prompt, decoding, judge, and random seed metadata.",
            "List missing reproducibility information.",
            "Return a concise checklist.",
        ],
        "usage_constraints": [
            "Do not infer missing metadata.",
            "Distinguish missing evidence from negative evidence.",
        ],
        "output_format": "Markdown checklist with pass/missing labels.",
    }


def _interleaved_skill_blueprint(source_available: bool) -> dict[str, Any]:
    strategy = "source" if source_available else "draw"
    return {
        "name": "mock_interleaved_visual_sequence_skill",
        "skill_type": "visual",
        "visual_skill_kind": "interleaved",
        "prior_kind": "static",
        "bottleneck": "protocol_ambiguity",
        "description": "A smoke-test interleaved visual skill grounded in ordered visual evidence.",
        "declarative_textual_logic": [
            "Read the visual references as ordered evidence for a multi-step skill.",
            "Bind each visible diagram, state, or transformation to the adjacent text step.",
            "State when a needed explanation is not supported by the available visual evidence.",
        ],
        "visual_prior_specs": [
            {
                "name": "interleaved_visual_reference",
                "prior_kind": "static",
                "strategy": strategy,
                "content_description": "A visual reference bound to one step in an interleaved skill.",
                "source_frame_index": 0 if source_available else -1,
                "crop_region_description": "",
                "search_query": "",
                "draw_instructions": "Draw a simple two-panel visual sequence with a before state, an arrow, and an after state.",
                "visual_rationale": "The visual anchors the visible state or transformation for the interleaved step.",
                "visual_encodings": ["Panel order indicates progression.", "Arrow indicates transformation."],
                "text_exclusions": ["Long prose explanation."],
                "forbidden_elements": ["Invented hidden evidence."],
                "max_text_tokens": 12,
                "image_generation_prompt": "",
                "image_generation_model": "",
                "image_generation_size": "1024x1024",
                "renderer_name": "",
                "renderer_description": "",
                "renderer_inputs": [],
                "renderer_outputs": [],
            }
        ],
        "binding_protocol": {
            "image_roles": ["ordered visual references"],
            "coordinate_system": "Source-frame or panel identity and visible regions.",
            "text_to_visual_binding": [
                "Each text step should name the visual reference or visible region it depends on."
            ],
            "task_binding_rules": [
                "Use visual references as evidence for layout, diagrams, states, and transformations."
            ],
            "anti_leakage_rules": [
                "Do not infer unsupported details that are absent from the visual evidence."
            ],
        },
        "runtime_protocol": {
            "mode": "single_turn",
            "state_schema": "Ordered visual references and visible-step notes.",
            "update_rule": "Bind text steps to visual references in order.",
            "stop_condition": "Stop when all visually grounded steps have been covered.",
            "renderer_spec": "No dynamic renderer.",
        },
        "parameters": [
            {
                "name": "visual_references",
                "type": "ordered images",
                "description": "Images, diagrams, frames, or generated panels used as step-bound evidence.",
            }
        ],
        "execution_steps": [
            "Scan the visual references in order.",
            "Identify visible states, diagrams, transformations, or local evidence.",
            "Write interleaved steps that bind each instruction or reasoning step to the relevant visual.",
            "Flag any step whose required evidence is missing.",
        ],
        "usage_constraints": [
            "Do not invent visual evidence that is not present.",
            "Treat visuals as evidence anchors, not as complete hidden context.",
        ],
        "output_format": "Ordered steps with visual references, visible evidence, and limitation notes.",
    }


def _text_skill_markdown() -> str:
    return (
        "# Mock Reproducibility Check Skill\n\n"
        "## Description\n"
        "This artifact was generated by AutoVisualSkill through AUTOVISUALSKILL_LLM_BACKEND=subagent.\n\n"
        "## Declarative Textual Logic\n"
        "1. Identify the claim being checked.\n"
        "2. Verify whether the report includes enough metadata to reproduce the result.\n"
        "3. Return missing items as actionable checklist entries.\n\n"
        "## Parameters\n"
        "- `report_text` (string): Experiment report or claim to audit.\n\n"
        "## Execution Steps\n"
        "1. Read the report carefully.\n"
        "2. Extract model, data, prompt, decoding, judge, and random seed metadata.\n"
        "3. List missing reproducibility information.\n"
        "4. Return a concise checklist.\n\n"
        "## Output Format\n"
        "Markdown checklist with pass/missing labels.\n"
    )


def _interleaved_skill_markdown(source_available: bool) -> str:
    visual_label = "Source visual reference" if source_available else "Generated visual reference"
    return (
        "# Mock Interleaved Visual Sequence Skill\n\n"
        "## Description\n"
        "A mock interleaved visual skill whose steps are grounded in adjacent visual evidence.\n\n"
        "## Declarative Textual Logic\n"
        "1. Treat visual references as ordered evidence.\n"
        "2. Bind visible diagrams, states, or transformations to nearby text steps.\n"
        "3. Flag reasoning that is not supported by available visual evidence.\n\n"
        "## Visual Priors\n"
        f"![{visual_label}](assets/interleaved_visual_reference.png)\n\n"
        "This visual anchors the visible state or transformation for one interleaved step.\n\n"
        "## Multimodal Binding Protocol\n"
        "Bind each instruction or reasoning step to a visual reference or visible region.\n\n"
        "## Runtime Protocol\n"
        "Single-turn; no dynamic renderer is used.\n\n"
        "## Parameters\n"
        "- `visual_references` (ordered images): images, diagrams, frames, or generated panels.\n\n"
        "## Execution Steps\n"
        "1. Scan the visual references in order.\n"
        "2. Identify visible states, diagrams, transformations, or local evidence.\n"
        "3. Write ordered text steps with adjacent visual references.\n"
        "4. Note any missing evidence.\n\n"
        "## Usage Constraints\n"
        "- Do not invent visual evidence that is not present.\n\n"
        "## Output Format\n"
        "Ordered steps with visual references, visible evidence, and limitation notes.\n"
    )


def _extract_goal(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        text = _flatten_text(message.get("content"))
        marker = "User goal:"
        if marker in text:
            return text.split(marker, 1)[1].splitlines()[0].strip()
    return "unknown goal"


def _extract_frame_count(messages: list[dict[str, Any]]) -> int:
    for message in messages:
        text = _flatten_text(message.get("content"))
        marker = "Number of extracted_frames:"
        if marker in text:
            value = text.split(marker, 1)[1].splitlines()[0].strip()
            try:
                return int(value)
            except ValueError:
                return 0
    return 0


def _mock_video_frame_selection(messages: list[dict[str, Any]]) -> list[int]:
    text = "\n".join(_flatten_text(message.get("content")) for message in messages)
    candidate_count = _extract_int_after(text, "Candidate frame count:")
    max_selected = _extract_int_after(text, "Maximum selected frames:")
    if candidate_count <= 0:
        return []
    if max_selected <= 0:
        max_selected = candidate_count
    count = min(candidate_count, max_selected)
    if count == 1:
        return [0]
    return [
        round(i * (candidate_count - 1) / (count - 1))
        for i in range(count)
    ]


def _extract_int_after(text: str, marker: str) -> int:
    if marker not in text:
        return 0
    value = text.split(marker, 1)[1].splitlines()[0].strip()
    try:
        return int(value)
    except ValueError:
        return 0


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        if value.get("type") == "text":
            return str(value.get("text", ""))
        return "\n".join(_flatten_text(v) for v in value.values())
    return str(value)


def _response_from_schema(schema: dict[str, Any]) -> Any:
    properties = schema.get("properties", {})
    required = schema.get("required", properties.keys())
    return {key: _default_for_property(properties.get(key, {})) for key in required}


def _default_for_property(prop: dict[str, Any]) -> Any:
    prop_type = prop.get("type")
    if prop_type == "boolean":
        return False
    if prop_type == "integer":
        return 0
    if prop_type == "number":
        return 0.0
    if prop_type == "array":
        return []
    if prop_type == "object":
        return {}
    return ""


if __name__ == "__main__":
    main()
