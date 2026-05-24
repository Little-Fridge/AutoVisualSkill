from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.llm.client import call_llm_structured
from autovisualskill.models.llm_responses import ContextAssessmentOutput
from autovisualskill.prompts.templates import ASSESS_CONTEXT_SYSTEM
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records, issue_record, provenance_record


def run(state: GraphState) -> dict:
    config = state.get("run_config", {})
    if not config.get("enable_web_research", True):
        return {
            "needs_web_research": False,
            "missing_context_notes": [],
            "search_queries": [],
            "provenance": append_records(
                state,
                "provenance",
                [provenance_record("assess_context", "web_research_disabled")],
            ),
        }

    text_blob = "\n---\n".join(state["extracted_texts"])[: config.get("max_text_chars", 8000)]
    artifact_summary = "\n".join(
        f"- {item.get('modality', 'unknown')}: {item.get('source', '')}"
        for item in state.get("input_artifacts", [])
    )
    user_text = (
        f"User goal:\n{state['user_goal']}\n\n"
        f"Modalities: {state['modalities']}\n"
        f"Input artifacts:\n{artifact_summary or '(none)'}\n\n"
        f"Extracted text excerpt:\n{text_blob or '(none)'}"
    )

    messages = [
        SystemMessage(content=ASSESS_CONTEXT_SYSTEM),
        HumanMessage(content=user_text),
    ]

    try:
        result: ContextAssessmentOutput = call_llm_structured(messages, ContextAssessmentOutput)
    except Exception as exc:
        return {
            "needs_web_research": False,
            "missing_context_notes": [f"Context assessment failed: {exc}"],
            "search_queries": [],
            "warnings": append_records(
                state,
                "warnings",
                [issue_record("assess_context", "Context assessment failed", error=str(exc))],
            ),
        }

    return {
        "needs_web_research": result.needs_web_research,
        "missing_context_notes": result.missing_context_notes,
        "search_queries": result.search_queries,
        "provenance": append_records(
            state,
            "provenance",
            [
                provenance_record(
                    "assess_context",
                    "assessed_context",
                    needs_web_research=result.needs_web_research,
                    search_queries=result.search_queries,
                )
            ],
        ),
    }
