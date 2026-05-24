from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.llm.client import call_llm_structured, image_to_base64
from autovisualskill.models.llm_responses import AnalyzeMaterialOutput
from autovisualskill.prompts.templates import ANALYZE_MATERIAL_SYSTEM
from autovisualskill.state import GraphState

def run(state: GraphState) -> dict:
    config = state.get("run_config", {})
    max_images = int(config.get("max_images_to_llm", 4))
    max_text_chars = int(config.get("max_text_chars", 8000))
    content_blocks: list[dict | str] = []

    text_blob = "\n---\n".join(state["extracted_texts"])[:max_text_chars]
    web_context = state.get("web_context", "")
    if text_blob:
        user_text = f"User goal: {state['user_goal']}\n\nExtracted texts:\n{text_blob}"
    else:
        user_text = f"User goal: {state['user_goal']}\n\n(No text materials provided.)"
    if web_context:
        user_text += f"\n\nWeb research context:\n{web_context[:max_text_chars]}"
    content_blocks.append({"type": "text", "text": user_text})

    for frame_path in state["extracted_frames"][:max_images]:
        b64 = image_to_base64(frame_path)
        content_blocks.append({"type": "image_url", "image_url": {"url": b64}})

    messages = [
        SystemMessage(content=ANALYZE_MATERIAL_SYSTEM),
        HumanMessage(content=content_blocks),
    ]

    result: AnalyzeMaterialOutput = call_llm_structured(messages, AnalyzeMaterialOutput)

    return {
        "task_domain": result.task_domain,
        "material_summary": result.material_summary,
    }
