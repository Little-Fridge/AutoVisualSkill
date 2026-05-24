from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.blueprint_normalizer import normalize_skill_blueprint
from autovisualskill.llm.client import call_llm_structured, image_to_base64
from autovisualskill.models.skill import SkillBlueprint
from autovisualskill.prompts.templates import DESIGN_SKILL_SYSTEM
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records

def run(state: GraphState) -> dict:
    config = state.get("run_config", {})
    max_images = int(config.get("max_images_to_llm", 4))
    content_blocks: list[dict | str] = []

    info_text = (
        f"User goal: {state['user_goal']}\n"
        f"Task domain: {state['task_domain']}\n"
        f"Material summary: {state['material_summary']}\n"
        f"Modalities: {state['modalities']}\n"
        f"Number of extracted_frames: {len(state['extracted_frames'])}\n"
        f"Missing context notes: {state.get('missing_context_notes', [])}\n"
        f"Web research context:\n{state.get('web_context', '')}\n"
    )
    content_blocks.append({"type": "text", "text": info_text})

    for frame_path in state["extracted_frames"][:max_images]:
        b64 = image_to_base64(frame_path)
        content_blocks.append({"type": "image_url", "image_url": {"url": b64}})

    messages = [
        SystemMessage(content=DESIGN_SKILL_SYSTEM),
        HumanMessage(content=content_blocks),
    ]

    blueprint: SkillBlueprint = call_llm_structured(messages, SkillBlueprint)
    blueprint, normalization_warnings = normalize_skill_blueprint(blueprint, state)

    return {
        "skill_type": blueprint.skill_type,
        "visual_skill_kind": blueprint.visual_skill_kind,
        "skill_blueprint": blueprint.model_dump_json(),
        "warnings": append_records(state, "warnings", normalization_warnings),
    }
