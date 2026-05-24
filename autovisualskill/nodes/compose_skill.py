import os

from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.llm.client import call_llm_structured
from autovisualskill.models.llm_responses import SkillMarkdown
from autovisualskill.models.skill import SkillBlueprint
from autovisualskill.prompts.templates import COMPOSE_SKILL_SYSTEM
from autovisualskill.state import GraphState


def run(state: GraphState) -> dict:
    blueprint = SkillBlueprint.model_validate_json(state["skill_blueprint"])

    if state["visual_prior_paths"]:
        lines = []
        for path, desc in zip(state["visual_prior_paths"], state["visual_prior_descriptions"]):
            filename = path.split(os.sep)[-1] if os.sep in path else path.split("/")[-1]
            lines.append(f"- {filename}: {desc}")
        visual_info = "Static visual prior assets generated:\n" + "\n".join(lines)
    else:
        visual_info = "(No static visual prior assets generated.)"

    dynamic_specs = [
        spec.model_dump()
        for spec in blueprint.visual_prior_specs
        if spec.prior_kind == "dynamic" or spec.strategy == "renderer"
    ]
    if dynamic_specs:
        visual_info += "\n\nDynamic visual prior specs:\n" + str(dynamic_specs)

    user_text = (
        f"User goal: {state['user_goal']}\n"
        f"Material summary: {state['material_summary']}\n\n"
        f"Web research context:\n{state.get('web_context', '')}\n\n"
        f"Web sources:\n{state.get('web_sources', [])}\n\n"
        f"SkillBlueprint:\n{state['skill_blueprint']}\n\n"
        f"{visual_info}"
    )

    messages = [
        SystemMessage(content=COMPOSE_SKILL_SYSTEM),
        HumanMessage(content=user_text),
    ]

    result: SkillMarkdown = call_llm_structured(messages, SkillMarkdown)

    return {"skill_md_content": result.markdown}
