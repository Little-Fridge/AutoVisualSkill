import os
import tempfile

from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.llm.client import call_llm_structured, image_to_base64
from autovisualskill.media.image_proc import crop_image, get_image_info
from autovisualskill.media.image_generation import generate_image_via_api
from autovisualskill.media.web_search import download_image, search_images
from autovisualskill.models.llm_responses import CropCoordinates, DrawingCode, ImageSelection, OverlayPlan
from autovisualskill.models.skill import SkillBlueprint, VisualPriorSpec
from autovisualskill.prompts.templates import (
    CROP_COORDINATES_SYSTEM,
    DRAWING_CODE_SYSTEM,
    IMAGE_SELECTION_SYSTEM,
    OVERLAY_PLAN_SYSTEM,
)
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records, issue_record, provenance_record, sanitize_filename


def _visual_prior_path(output_temp: str, name: str) -> str:
    filename = sanitize_filename(name, default="visual_prior", suffix=".png")
    return os.path.join(output_temp, filename)


def _handle_crop(spec: VisualPriorSpec, extracted_frames: list[str], output_temp: str) -> str:
    """crop strategy: ask the LLM for coordinates, then crop with Pillow."""
    source_path = extracted_frames[spec.source_frame_index]
    info = get_image_info(source_path)

    content_blocks = [
        {
            "type": "text",
            "text": (
                f"Image dimensions: {info['width']}x{info['height']}\n"
                f"Please crop the following region: {spec.crop_region_description}"
            ),
        },
        {"type": "image_url", "image_url": {"url": image_to_base64(source_path)}},
    ]
    messages = [
        SystemMessage(content=CROP_COORDINATES_SYSTEM),
        HumanMessage(content=content_blocks),
    ]
    coords: CropCoordinates = call_llm_structured(messages, CropCoordinates)

    left = max(0, min(coords.left, info["width"] - 1))
    top = max(0, min(coords.top, info["height"] - 1))
    right = max(left + 1, min(coords.right, info["width"]))
    bottom = max(top + 1, min(coords.bottom, info["height"]))

    output_path = _visual_prior_path(output_temp, spec.name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    crop_image(source_path, left, top, right, bottom, output_path)
    return os.path.abspath(output_path)


def _handle_source(spec: VisualPriorSpec, extracted_frames: list[str], output_temp: str) -> str:
    """source strategy: reuse a provided frame unchanged as a visual asset."""
    if spec.source_frame_index < 0 or spec.source_frame_index >= len(extracted_frames):
        raise ValueError(
            f"Source prior '{spec.name}' references invalid source_frame_index="
            f"{spec.source_frame_index}; available frames={len(extracted_frames)}"
        )
    source_path = extracted_frames[spec.source_frame_index]
    output_path = _visual_prior_path(output_temp, spec.name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    from shutil import copy2

    copy2(source_path, output_path)
    return os.path.abspath(output_path)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _norm_point(point: list[float], width: int, height: int) -> tuple[int, int]:
    x = _clamp01(point[0] if len(point) > 0 else 0.0)
    y = _clamp01(point[1] if len(point) > 1 else 0.0)
    return round(x * width), round(y * height)


def _norm_bbox(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int] | None:
    if len(bbox) < 4:
        return None
    left = round(_clamp01(bbox[0]) * width)
    top = round(_clamp01(bbox[1]) * height)
    right = round(_clamp01(bbox[2]) * width)
    bottom = round(_clamp01(bbox[3]) * height)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _overlay_colors(name: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    palette = {
        "green": ((22, 163, 74, 235), (34, 197, 94, 48)),
        "blue": ((37, 99, 235, 235), (59, 130, 246, 46)),
        "red": ((220, 38, 38, 235), (239, 68, 68, 46)),
        "amber": ((217, 119, 6, 235), (245, 158, 11, 48)),
        "purple": ((124, 58, 237, 235), (139, 92, 246, 46)),
        "gray": ((71, 85, 105, 220), (100, 116, 139, 42)),
    }
    return palette.get(name, palette["green"])


def _draw_arrow(draw, points: list[tuple[int, int]], stroke: tuple[int, int, int, int], width: int) -> None:
    if len(points) < 2:
        return
    import math

    draw.line(points, fill=stroke, width=width, joint="curve")
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    size = max(12, width * 4)
    head = [
        (x2, y2),
        (
            round(x2 - size * math.cos(angle - math.pi / 7)),
            round(y2 - size * math.sin(angle - math.pi / 7)),
        ),
        (
            round(x2 - size * math.cos(angle + math.pi / 7)),
            round(y2 - size * math.sin(angle + math.pi / 7)),
        ),
    ]
    draw.polygon(head, fill=stroke)


def _render_overlay_plan(source_path: str, output_path: str, plan: OverlayPlan) -> None:
    from PIL import Image, ImageDraw, ImageFont

    base = Image.open(source_path).convert("RGBA")
    width, height = base.size
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    line_width = max(4, round(max(width, height) / 260))
    font = ImageFont.load_default()

    for mark in plan.marks[:12]:
        stroke, fill = _overlay_colors(mark.color)
        bbox = _norm_bbox(mark.bbox, width, height)
        points = [_norm_point(point, width, height) for point in mark.points]

        if mark.kind == "box" and bbox:
            draw.rounded_rectangle(bbox, radius=10, outline=stroke, width=line_width, fill=fill)
        elif mark.kind == "mask" and bbox:
            draw.rounded_rectangle(bbox, radius=10, outline=stroke, width=line_width, fill=fill)
        elif mark.kind == "cross" and bbox:
            draw.rounded_rectangle(bbox, radius=10, outline=stroke, width=max(2, line_width - 1))
            draw.line((bbox[0], bbox[1], bbox[2], bbox[3]), fill=stroke, width=line_width)
            draw.line((bbox[0], bbox[3], bbox[2], bbox[1]), fill=stroke, width=line_width)
        elif mark.kind == "arrow":
            _draw_arrow(draw, points, stroke, line_width)
        elif mark.kind == "line" and len(points) >= 2:
            draw.line(points, fill=stroke, width=line_width, joint="curve")
        elif mark.kind == "circle":
            if not bbox and points:
                x, y = points[0]
                r = max(12, line_width * 3)
                bbox = (x - r, y - r, x + r, y + r)
            if bbox:
                draw.ellipse(bbox, outline=stroke, width=line_width, fill=fill)
        elif mark.kind == "dot" and points:
            x, y = points[0]
            r = max(7, line_width * 2)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=stroke)

        if mark.label and len(mark.label) <= 1 and points:
            x, y = points[0]
            draw.text((x + line_width * 2, y + line_width * 2), mark.label, fill=stroke, font=font)

    Image.alpha_composite(base, overlay).convert("RGB").save(output_path, format="PNG", optimize=True)


def _handle_overlay(spec: VisualPriorSpec, extracted_frames: list[str], output_temp: str) -> str:
    """overlay strategy: ask the LLM for sparse marks, then render them locally."""
    if spec.source_frame_index < 0 or spec.source_frame_index >= len(extracted_frames):
        raise ValueError(
            f"Overlay prior '{spec.name}' references invalid source_frame_index="
            f"{spec.source_frame_index}; available frames={len(extracted_frames)}"
        )
    source_path = extracted_frames[spec.source_frame_index]
    visual_contract = (
        f"Visual rationale: {spec.visual_rationale}\n"
        f"Allowed visual encodings:\n"
        + "\n".join(f"- {item}" for item in spec.visual_encodings)
        + "\n"
        f"Information that must stay in Markdown, not in the image:\n"
        + "\n".join(f"- {item}" for item in spec.text_exclusions)
        + "\n"
        f"Forbidden image elements:\n"
        + "\n".join(f"- {item}" for item in spec.forbidden_elements)
        + "\n"
        f"Maximum text tokens allowed inside the image: {spec.max_text_tokens}\n"
    )
    content_blocks: list[dict | str] = [
        {
            "type": "text",
            "text": (
                f"Plan a sparse source-image overlay for this concrete visual prior.\n\n"
                f"Content description:\n{spec.content_description}\n\n"
                f"Visual Prior Contract:\n{visual_contract}\n"
                f"Overlay instructions:\n{spec.draw_instructions}\n\n"
                "Critical: return only visual marks. Preserve the source image. "
                "Do not add prose labels or a legend inside the bitmap."
            ),
        },
        {"type": "image_url", "image_url": {"url": image_to_base64(source_path)}},
    ]
    messages = [
        SystemMessage(content=OVERLAY_PLAN_SYSTEM),
        HumanMessage(content=content_blocks),
    ]
    plan: OverlayPlan = call_llm_structured(messages, OverlayPlan)

    output_path = _visual_prior_path(output_temp, spec.name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _render_overlay_plan(source_path, output_path, plan)
    return os.path.abspath(output_path)


def _handle_search(spec: VisualPriorSpec, output_temp: str) -> str:
    """search strategy: Tavily search, download candidates, ask LLM to select."""
    candidates = search_images(spec.search_query, max_results=5)
    if not candidates:
        raise RuntimeError(f"No image search candidates found for query: {spec.search_query}")

    os.makedirs(output_temp, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="search_candidates_", dir=output_temp)
    downloaded: list[str] = []
    for idx, candidate in enumerate(candidates):
        try:
            p = os.path.join(tmp_dir, f"candidate_{idx}.png")
            download_image(candidate["url"], p)
            downloaded.append(p)
        except Exception:
            continue

    if not downloaded:
        raise RuntimeError(f"No image search candidates could be downloaded for query: {spec.search_query}")

    if len(downloaded) == 1:
        selected_path = downloaded[0]
    else:
        content_blocks: list[dict] = [
            {
                "type": "text",
                "text": f"Needed image: {spec.content_description}\n\nCandidates:",
            },
        ]
        for idx, downloaded_path in enumerate(downloaded):
            content_blocks.append({"type": "text", "text": f"[Candidate {idx}]"})
            content_blocks.append(
                {"type": "image_url", "image_url": {"url": image_to_base64(downloaded_path)}}
            )

        messages = [
            SystemMessage(content=IMAGE_SELECTION_SYSTEM),
            HumanMessage(content=content_blocks),
        ]
        selection: ImageSelection = call_llm_structured(messages, ImageSelection)
        sel_idx = max(0, min(selection.selected_index, len(downloaded) - 1))
        selected_path = downloaded[sel_idx]

    output_path = _visual_prior_path(output_temp, spec.name)
    from shutil import copy2

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    copy2(selected_path, output_path)
    return os.path.abspath(output_path)


def _handle_draw(spec: VisualPriorSpec, output_temp: str) -> str:
    """draw strategy: ask the LLM for Pillow code, then execute it."""
    visual_contract = (
        f"Visual rationale: {spec.visual_rationale}\n"
        f"Allowed visual encodings:\n"
        + "\n".join(f"- {item}" for item in spec.visual_encodings)
        + "\n"
        f"Information that must stay in Markdown, not in the image:\n"
        + "\n".join(f"- {item}" for item in spec.text_exclusions)
        + "\n"
        f"Forbidden image elements:\n"
        + "\n".join(f"- {item}" for item in spec.forbidden_elements)
        + "\n"
        f"Maximum text tokens allowed inside the image: {spec.max_text_tokens}\n"
    )
    messages = [
        SystemMessage(content=DRAWING_CODE_SYSTEM),
        HumanMessage(
            content=(
                f"Draw this visual-first prior.\n\n"
                f"Content description:\n{spec.content_description}\n\n"
                f"Visual Prior Contract:\n{visual_contract}\n"
                f"Draw instructions:\n{spec.draw_instructions}\n\n"
                "Critical: the final image must be mostly visual. Do not turn "
                "the contract into labels or prose inside the bitmap."
            )
        ),
    ]
    result: DrawingCode = call_llm_structured(messages, DrawingCode)

    output_path = _visual_prior_path(output_temp, spec.name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    from PIL import ImageDraw as PILImageDraw

    if not hasattr(PILImageDraw.ImageDraw, "textsize"):
        def _compat_textsize(self, text, font=None, *args, **kwargs):
            left, top, right, bottom = self.textbbox((0, 0), text, font=font, *args, **kwargs)
            return right - left, bottom - top
        PILImageDraw.ImageDraw.textsize = _compat_textsize

    exec_globals = {"output_path": output_path}
    exec(result.python_code, exec_globals)

    if not os.path.isfile(output_path):
        raise RuntimeError(f"Drawing code did not produce file: {output_path}")

    return os.path.abspath(output_path)


def _handle_api(spec: VisualPriorSpec, output_temp: str, config: dict) -> str:
    """api strategy: call an external image-generation API such as NanoBanana."""
    base_url = (
        config.get("image_generation_base_url")
        or os.environ.get("AUTOVISUALSKILL_IMAGE_API_BASE_URL")
        or ""
    )
    api_key = os.environ.get("AUTOVISUALSKILL_IMAGE_API_KEY", "")
    model = (
        spec.image_generation_model
        or config.get("image_generation_model")
        or os.environ.get("AUTOVISUALSKILL_IMAGE_API_MODEL")
        or "nanobanana"
    )
    timeout = float(config.get("image_generation_timeout", 120.0))
    prompt = spec.image_generation_prompt or spec.draw_instructions or spec.content_description
    contract_lines = [
        "Create a visual-first protocol prior, not an infographic.",
        "The image should express spatial information through shapes, boundaries, flow, containment, masks, anchors, and overlays.",
        "Do not include long text, paragraphs, headings, prose legends, brand names, app names, dataset text, answers, or coordinates.",
        f"Maximum text tokens inside the image: {spec.max_text_tokens}.",
    ]
    if spec.visual_rationale:
        contract_lines.append(f"Visual rationale: {spec.visual_rationale}")
    if spec.visual_encodings:
        contract_lines.append("Allowed visual encodings: " + "; ".join(spec.visual_encodings))
    if spec.text_exclusions:
        contract_lines.append("Keep out of the image: " + "; ".join(spec.text_exclusions))
    if spec.forbidden_elements:
        contract_lines.append("Forbidden: " + "; ".join(spec.forbidden_elements))
    prompt = prompt + "\n\n" + "\n".join(contract_lines)

    output_path = _visual_prior_path(output_temp, spec.name)
    return generate_image_via_api(
        prompt=prompt,
        output_path=output_path,
        base_url=base_url,
        api_key=api_key,
        model=model,
        size=spec.image_generation_size,
        timeout=timeout,
    )


def run(state: GraphState) -> dict:
    blueprint = SkillBlueprint.model_validate_json(state["skill_blueprint"])
    config = state.get("run_config", {})
    output_temp = os.path.join(state.get("temp_dir") or state.get("run_config", {}).get("temp_dir", ""), "visual_priors")
    if not output_temp.strip(os.sep):
        output_temp = os.path.join(os.getcwd(), ".autovisualskill_tmp", "visual_priors")

    os.makedirs(output_temp, exist_ok=True)

    visual_prior_paths: list[str] = []
    visual_prior_descriptions: list[str] = []
    provenance: list[dict] = []

    for spec in blueprint.visual_prior_specs:
        if spec.strategy == "renderer" or spec.prior_kind == "dynamic":
            provenance.append(
                provenance_record(
                    "generate_visual",
                    "registered_dynamic_visual_prior",
                    name=spec.name,
                    strategy=spec.strategy,
                    renderer=spec.renderer_name,
                )
            )
            continue

        if spec.strategy == "source":
            path = _handle_source(spec, state["extracted_frames"], output_temp)
        elif spec.strategy == "crop":
            if spec.source_frame_index < 0 or spec.source_frame_index >= len(state["extracted_frames"]):
                raise ValueError(
                    f"Static crop prior '{spec.name}' references invalid source_frame_index="
                    f"{spec.source_frame_index}; available frames={len(state['extracted_frames'])}"
                )
            path = _handle_crop(spec, state["extracted_frames"], output_temp)
        elif spec.strategy == "overlay":
            path = _handle_overlay(spec, state["extracted_frames"], output_temp)
        elif spec.strategy == "search":
            path = _handle_search(spec, output_temp)
        elif spec.strategy == "draw":
            path = _handle_draw(spec, output_temp)
        elif spec.strategy == "api":
            path = _handle_api(spec, output_temp, config)
        else:
            raise ValueError(f"Unsupported visual prior strategy: {spec.strategy}")

        provenance.append(
            provenance_record(
                "generate_visual",
                "generated_static_visual_prior",
                name=spec.name,
                strategy=spec.strategy,
                path=path,
            )
        )
        visual_prior_paths.append(path)
        visual_prior_descriptions.append(spec.content_description)

    return {
        "visual_prior_paths": visual_prior_paths,
        "visual_prior_descriptions": visual_prior_descriptions,
        "provenance": append_records(state, "provenance", provenance),
    }
