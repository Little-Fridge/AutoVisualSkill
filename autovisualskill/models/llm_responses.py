from typing import Literal

from pydantic import BaseModel


class CropCoordinates(BaseModel):
    """Pixel crop coordinates returned by the LLM."""

    left: int
    top: int
    right: int
    bottom: int
    explanation: str


class DrawingCode(BaseModel):
    """Pillow drawing code returned by the LLM."""

    python_code: str
    explanation: str


class OverlayMark(BaseModel):
    """One source-grounded overlay mark returned by the LLM."""

    kind: Literal["box", "arrow", "line", "circle", "cross", "mask", "dot"]
    color: Literal["green", "blue", "red", "amber", "purple", "gray"] = "green"
    bbox: list[float] = []
    points: list[list[float]] = []
    label: str = ""
    rationale: str = ""


class OverlayPlan(BaseModel):
    """Sparse source-image overlay plan returned by the LLM."""

    marks: list[OverlayMark]
    explanation: str


class ImageSelection(BaseModel):
    """Best-image selection returned by the LLM."""

    selected_index: int
    reason: str


class VideoFrameSelection(BaseModel):
    """Video candidate-frame selection returned by the LLM."""

    selected_indices: list[int]
    rationale: str


class AnalyzeMaterialOutput(BaseModel):
    """Structured output for the analyze_material node."""

    task_domain: str
    material_summary: str


class ContextAssessmentOutput(BaseModel):
    """Structured output for deciding whether web context is needed."""

    needs_web_research: bool
    missing_context_notes: list[str]
    search_queries: list[str]


class SkillMarkdown(BaseModel):
    """Structured output for the compose_skill node."""

    markdown: str
