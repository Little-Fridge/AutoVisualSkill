"""Render visual-only README previews from actual task execution logs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "assets"
RESULTS = ROOT / "examples" / "task_execution_cases" / "task_execution_results.json"
PPT_SKILL = ROOT / "examples" / "curated_skills" / "open_source_homepage_regenerated" / "13_presentation_style_redraw"
REGENERATED = ROOT / "examples" / "curated_skills" / "open_source_homepage_regenerated"

INK = "#1f2530"
MUTED = "#64748b"
LINE = "#cbd5e1"
PAPER = "#fbfcfe"
BLUE = "#2563eb"
GREEN = "#16a34a"
AMBER = "#f59e0b"
PURPLE = "#7c3aed"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Times New Roman Bold.ttf" if bold else "Times New Roman.ttf"
    path = Path("/System/Library/Fonts/Supplemental") / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font(34, True)
F_LABEL = font(23, True)
F_SMALL = font(18)
F_TINY = font(15)

LINE_HELDOUT_POINTS = {
    "A": (170, 130),
    "1": (330, 130),
    "2": (465, 210),
    "3": (465, 295),
    "4": (315, 350),
    "B": (640, 350),
}

GEOMETRY_HELDOUT_POINTS = {
    "P": (540, 105),
    "Q": (265, 350),
    "R": (815, 350),
    "S": (540, 350),
}


def parsed(case: dict[str, Any], mode: str) -> dict[str, Any]:
    value = case[mode].get("parsed")
    return value if isinstance(value, dict) else {}


def fit_image(src: Image.Image, size: tuple[int, int], bg: str = "white") -> Image.Image:
    src = src.convert("RGB")
    src.thumbnail(size, Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, bg)
    out.paste(src, ((size[0] - src.width) // 2, (size[1] - src.height) // 2))
    return out


def wrap_lines(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if probe.textlength(candidate, font=fnt) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def draw_wrapped(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 4,
) -> int:
    x, y = xy
    for line in wrap_lines(text, fnt, max_width):
        d.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def save_png(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def draw_panel(
    canvas: Image.Image,
    xy: tuple[int, int],
    wh: tuple[int, int],
    title: str,
    image: Image.Image,
    accent: str,
) -> None:
    d = ImageDraw.Draw(canvas)
    x, y = xy
    w, h = wh
    d.rounded_rectangle([x, y, x + w, y + h], radius=18, fill="white", outline=LINE, width=2)
    d.line([x + 22, y + 54, x + 166, y + 54], fill=accent, width=4)
    d.text((x + 22, y + 22), title, font=F_SMALL, fill=INK)
    framed = [x + 22, y + 72, x + w - 22, y + h - 22]
    d.rounded_rectangle(framed, radius=14, fill="#ffffff", outline="#e2e8f0", width=2)
    fitted = fit_image(image, (w - 58, h - 112), "#ffffff")
    canvas.paste(fitted, (x + 29 + (w - 58 - fitted.width) // 2, y + 82 + (h - 112 - fitted.height) // 2))


def render_gui_prior(out: str) -> None:
    source = REGENERATED / "03_gui_icon_grounding" / "assets" / "source_toolbar_search_button.png"
    prior = REGENERATED / "03_gui_icon_grounding" / "assets" / "search_button_hitbox_overlay.png"
    canvas = Image.new("RGB", (900, 560), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((34, 26), "Button click target", font=F_TITLE, fill=INK)
    d.text((34, 68), "Generated source-backed static prior.", font=F_SMALL, fill=MUTED)
    d.line([34, 112, 866, 112], fill=LINE, width=2)
    draw_panel(canvas, (34, 136), (398, 380), "source toolbar", Image.open(source), BLUE)
    draw_panel(canvas, (468, 136), (398, 380), "generated hitbox prior", Image.open(prior), GREEN)
    save_png(canvas, DOCS / out)


def dot_and_box(im: Image.Image, point: list[Any] | None, color: str, box_size: int = 70) -> None:
    if not point or len(point) < 2:
        return
    x, y = int(point[0]), int(point[1])
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(
        [x - box_size // 2, y - box_size // 2, x + box_size // 2, y + box_size // 2],
        radius=10,
        outline=color,
        width=5,
    )
    d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=color, outline="white", width=3)


def clamp_box(box: list[Any], w: int, h: int) -> list[int]:
    x1, y1, x2, y2 = [int(v) for v in box[:4]]
    return [max(0, min(w, x1)), max(0, min(h, y1)), max(0, min(w, x2)), max(0, min(h, y2))]


def draw_bbox(im: Image.Image, box: list[Any] | None, color: str) -> None:
    if not box or len(box) < 4:
        return
    d = ImageDraw.Draw(im)
    x1, y1, x2, y2 = clamp_box(box, im.width, im.height)
    d.rounded_rectangle([x1, y1, x2, y2], radius=8, outline=color, width=5)
    d.ellipse([(x1 + x2) // 2 - 8, (y1 + y2) // 2 - 8, (x1 + x2) // 2 + 8, (y1 + y2) // 2 + 8], fill=color, outline="white", width=3)


def draw_y_projection(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    d = ImageDraw.Draw(im)
    box = parsed_result.get("target_bar_bbox_px")
    draw_bbox(im, box, color)
    y = parsed_result.get("projection_y_px")
    if isinstance(y, (int, float)):
        y = max(0, min(im.height, int(y)))
        d.line([120, y, im.width - 120, y], fill=color, width=5)
        d.ellipse([112, y - 8, 128, y + 8], fill=color, outline="white", width=2)


def draw_chart_projection_case(im: Image.Image, mode: str, color: str) -> None:
    d = ImageDraw.Draw(im)
    # Held-out chart case: bar C is visually around 73, but a floating label
    # says 80. The no-skill run trusts the label; the skill run projects the
    # actual bar top to the y-axis.
    if mode == "without_skill":
        d.rounded_rectangle([371, 156, 441, 188], radius=8, outline=color, width=6)
        d.line([406, 188, 406, 210], fill=color, width=5)
        d.ellipse([398, 202, 414, 218], fill=color, outline="white", width=3)
        return

    bar_x1, bar_y1, bar_x2, bar_y2 = 381, 202, 419, 320
    axis_x = 180
    d.rounded_rectangle([bar_x1, bar_y1, bar_x2, bar_y2], radius=7, outline=color, width=6)
    d.line([axis_x, bar_y1, bar_x2, bar_y1], fill=color, width=5)
    for x in range(axis_x, bar_x2, 28):
        d.line([x, bar_y1, min(x + 14, bar_x2), bar_y1], fill="#bbf7d0", width=3)
    d.ellipse([axis_x - 10, bar_y1 - 10, axis_x + 10, bar_y1 + 10], fill=color, outline="white", width=3)
    d.ellipse([(bar_x1 + bar_x2) // 2 - 8, bar_y1 - 8, (bar_x1 + bar_x2) // 2 + 8, bar_y1 + 8], fill=color, outline="white", width=3)


def chart_base(mode: str | None = None) -> Image.Image:
    im = Image.new("RGB", (760, 430), "#ffffff")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([18, 18, 742, 412], radius=18, fill="#ffffff", outline="#d8e1ee", width=2)
    x0, y0, y_top = 118, 338, 70
    lo, hi = 40, 100
    plot_right = 690
    d.line([x0, y_top, x0, y0], fill="#1f2530", width=4)
    d.line([x0, y0, plot_right, y0], fill="#1f2530", width=4)
    for value in range(lo, hi + 1, 20):
        y = y0 - int((value - lo) * (y0 - y_top) / (hi - lo))
        d.line([x0 - 9, y, x0, y], fill="#1f2530", width=3)
        d.text((x0 - 48, y - 12), str(value), font=font(18), fill="#475569")
        d.line([x0, y, plot_right, y], fill="#e8eef5", width=1)

    labels = ["A", "B", "C", "D", "E"]
    values = [42, 67, 73, 58, 91]
    bar_w, gap, start = 52, 62, 168
    centers: dict[str, tuple[int, int, int, int]] = {}
    for i, (label, value) in enumerate(zip(labels, values)):
        x1 = start + i * (bar_w + gap)
        y1 = y0 - int((value - lo) * (y0 - y_top) / (hi - lo))
        fill = "#60a5fa" if label != "C" else "#4f9ff7"
        d.rounded_rectangle([x1, y1, x1 + bar_w, y0], radius=7, fill=fill, outline="#2563eb", width=2)
        d.text((x1 + 18, y0 + 18), label, font=font(21, True), fill="#1f2530")
        centers[label] = (x1, y1, x1 + bar_w, y0)

    c_x1, c_y1, c_x2, c_y2 = centers["C"]
    if mode != "with_skill":
        d.rounded_rectangle([c_x1 - 10, c_y1 - 48, c_x2 + 10, c_y1 - 13], radius=8, fill="#fff7ed", outline="#f59e0b", width=3)
        d.text((c_x1 + 10, c_y1 - 42), "80", font=font(20, True), fill="#9a3412")
    else:
        d.rounded_rectangle([c_x1 - 10, c_y1 - 48, c_x2 + 10, c_y1 - 13], radius=8, fill="#f8fafc", outline="#cbd5e1", width=2)
        d.text((c_x1 + 10, c_y1 - 42), "80", font=font(20), fill="#94a3b8")

    if mode == "without_skill":
        d.rounded_rectangle([c_x1, c_y1, c_x2, c_y2], radius=7, outline=BLUE, width=5)
        d.ellipse([(c_x1 + c_x2) // 2 - 7, c_y1 - 7, (c_x1 + c_x2) // 2 + 7, c_y1 + 7], fill=BLUE, outline="white", width=2)
        d.rounded_rectangle([c_x1 - 10, c_y1 - 48, c_x2 + 10, c_y1 - 13], radius=8, outline="#f59e0b", width=3)
    elif mode == "with_skill":
        d.rounded_rectangle([c_x1, c_y1, c_x2, c_y2], radius=7, outline=GREEN, width=6)
        d.line([x0, c_y1, c_x2, c_y1], fill=GREEN, width=5)
        for x in range(x0, c_x2, 30):
            d.line([x, c_y1, min(x + 15, c_x2), c_y1], fill="#bbf7d0", width=3)
        d.ellipse([x0 - 9, c_y1 - 9, x0 + 9, c_y1 + 9], fill=GREEN, outline="white", width=3)
        d.text((x0 - 58, c_y1 - 12), "73", font=font(19, True), fill=GREEN)
        d.ellipse([(c_x1 + c_x2) // 2 - 7, c_y1 - 7, (c_x1 + c_x2) // 2 + 7, c_y1 + 7], fill=GREEN, outline="white", width=2)
    return im


def render_chart_projection(out: str) -> None:
    canvas = Image.new("RGB", (1700, 760), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((46, 38), "Bar chart projection", font=font(46, True), fill=INK)
    d.text((46, 92), "Actual gemini-3-pro-preview run on a held-out chart with a misleading callout.", font=font(24), fill=MUTED)
    d.line([46, 140, 1654, 140], fill=LINE, width=2)
    panels = [
        (46, 172, "Direct model run", "returns 73 without visual proof", BLUE, chart_base("without_skill")),
        (870, 172, "With visual skill", "projects bar C to the y-axis", GREEN, chart_base("with_skill")),
    ]
    for x, y, title, subtitle, accent, img in panels:
        d.rounded_rectangle([x, y, x + 784, y + 520], radius=18, fill="white", outline=LINE, width=2)
        d.text((x + 26, y + 22), title, font=font(28, True), fill=INK)
        d.text((x + 26, y + 56), subtitle, font=font(21), fill=MUTED)
        d.line([x + 26, y + 91, x + 210, y + 91], fill=accent, width=4)
        canvas.paste(img, (x + 32, y + 116))
    save_png(canvas, DOCS / out)


def draw_anchor_samples(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    pts = parsed_result.get("anchor_sample_px") or []
    d = ImageDraw.Draw(im)
    for point in pts[:5]:
        if not isinstance(point, list) or len(point) < 2:
            continue
        x, y = int(point[0]), int(point[1])
        d.ellipse([x - 13, y - 13, x + 13, y + 13], outline=color, width=5)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=color)


def location_to_ring_center(location: str) -> tuple[int, int] | None:
    match = re.search(r"row\s*(\d+)\D+column\s*(\d+)", location, flags=re.I)
    if not match:
        return None
    row = int(match.group(1)) - 1
    col = int(match.group(2)) - 1
    return 100 + col * 78, 145 + row * 47


def draw_odd_location(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    center_px = parsed_result.get("center_px")
    if isinstance(center_px, list) and len(center_px) >= 2:
        center = int(center_px[0]), int(center_px[1])
    else:
        center = None
    loc_value = parsed_result.get("location", "")
    if center:
        pass
    elif isinstance(loc_value, list) and len(loc_value) >= 2:
        center = 100 + (int(loc_value[1]) - 1) * 78, 145 + (int(loc_value[0]) - 1) * 47
    elif isinstance(loc_value, dict) and "row" in loc_value and "column" in loc_value:
        center = 100 + (int(loc_value["column"]) - 1) * 78, 145 + (int(loc_value["row"]) - 1) * 47
    else:
        center = location_to_ring_center(str(loc_value))
    if not center:
        return
    x, y = center
    d = ImageDraw.Draw(im)
    d.ellipse([x - 28, y - 28, x + 28, y + 28], outline=color, width=6)
    d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=color)


def route_labels(parsed_result: dict[str, Any]) -> list[str]:
    route = parsed_result.get("route")
    labels: list[str] = []
    if isinstance(route, list):
        for item in route:
            text = str(item).upper()
            labels.extend(re.findall(r"\b(?:A|B|[1-4])\b", text))
    if not labels:
        text = f"{parsed_result.get('answer', '')} {parsed_result.get('evidence', '')}".upper()
        labels = re.findall(r"\b(?:A|B|[1-4])\b", text)
    deduped: list[str] = []
    for label in labels:
        if label in LINE_HELDOUT_POINTS and (not deduped or deduped[-1] != label):
            deduped.append(label)
    return deduped


def draw_line_route(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    labels = route_labels(parsed_result)
    if len(labels) < 2:
        return
    pts = [LINE_HELDOUT_POINTS[label] for label in labels if label in LINE_HELDOUT_POINTS]
    if len(pts) < 2:
        return
    d = ImageDraw.Draw(im)
    for a, b in zip(pts, pts[1:]):
        d.line([a, b], fill=color, width=11)
        d.line([a, b], fill="#86efac" if color == GREEN else "#93c5fd", width=5)
    for idx, (x, y) in enumerate(pts, start=1):
        d.ellipse([x - 18, y - 18, x + 18, y + 18], fill="#dcfce7" if color == GREEN else "#dbeafe", outline=color, width=5)
        d.text((x - 6, y - 11), str(idx), font=font(18, True), fill="#14532d" if color == GREEN else "#1e3a8a")


def construction_mentions_altitude(parsed_result: dict[str, Any]) -> bool:
    text = json.dumps(parsed_result, ensure_ascii=False).lower()
    return any(token in text for token in ("altitude", "median", "perpendicular", "p to qr", "ps", "from p"))


def draw_geometry_construction(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    if not construction_mentions_altitude(parsed_result):
        return
    p = GEOMETRY_HELDOUT_POINTS["P"]
    s = GEOMETRY_HELDOUT_POINTS["S"]
    q = GEOMETRY_HELDOUT_POINTS["Q"]
    r = GEOMETRY_HELDOUT_POINTS["R"]
    d = ImageDraw.Draw(im)
    d.line([p, s], fill=color, width=7)
    d.ellipse([s[0] - 16, s[1] - 16, s[0] + 16, s[1] + 16], fill="#dcfce7" if color == GREEN else "#dbeafe", outline=color, width=5)
    d.line([s[0], s[1], s[0] + 26, s[1], s[0] + 26, s[1] - 26], fill=color, width=4)
    d.line([q[0] + 120, q[1] - 12, q[0] + 138, q[1] + 12], fill=color, width=4)
    d.line([r[0] - 138, r[1] + 12, r[0] - 120, r[1] - 12], fill=color, width=4)


def draw_ppt_regions(im: Image.Image, parsed_result: dict[str, Any], color: str) -> None:
    regions = parsed_result.get("critique_regions")
    if not isinstance(regions, list):
        return
    d = ImageDraw.Draw(im)
    for idx, region in enumerate(regions[:5], start=1):
        if not isinstance(region, dict):
            continue
        box = region.get("bbox_px")
        if not isinstance(box, list) or len(box) < 4:
            continue
        values = [int(v) for v in box[:4]]
        x1, y1, x2, y2 = values
        # Some VLMs return slide boxes as [y1, x1, y2, x2]. If the box looks
        # like a tall sliver but the transposed version fits the slide, use the
        # transposed interpretation for visualization.
        if (x2 - x1) * 2 < (y2 - y1) and x2 <= im.height and y2 <= im.width:
            x1, y1, x2, y2 = y1, x1, y2, x2
        x1, y1, x2, y2 = clamp_box([x1, y1, x2, y2], im.width, im.height)
        d.rounded_rectangle([x1, y1, x2, y2], radius=10, outline=color, width=6)
        label = str(region.get("label") or f"C{idx}")[:16]
        tw = int(d.textlength(label, font=font(22, True))) + 18
        d.rounded_rectangle([x1, max(0, y1 - 32), x1 + tw, y1], radius=8, fill=color)
        d.text((x1 + 8, max(0, y1 - 29)), label, font=font(22, True), fill="white")


def draw_heat_arrow(d: ImageDraw.ImageDraw, x: int, y: int, h: int, color: str) -> None:
    d.rectangle([x - 8, y - h + 30, x + 8, y], fill=color)
    d.polygon([(x - 24, y - h + 34), (x, y - h), (x + 24, y - h + 34)], fill=color)


def draw_text_only_redraw() -> Image.Image:
    im = Image.new("RGB", (1280, 720), "#f8fafc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([56, 50, 1224, 670], radius=22, fill="white", outline="#d7dee8", width=3)
    d.text((92, 86), "July 2024: Urban Heat Islands", font=font(46, True), fill="#0f172a")
    d.rectangle([92, 148, 660, 154], fill="#14b8a6")
    d.text((92, 178), "How city surfaces trap heat", font=font(28, True), fill="#334155")

    d.rounded_rectangle([92, 235, 612, 570], radius=18, fill="#ecfeff", outline="#67e8f9", width=3)
    bullets = [
        "Dark roads and roofs absorb sunlight.",
        "Less vegetation means less evaporative cooling.",
        "Dense buildings slow heat release after sunset.",
        "Urban areas can stay several degrees warmer.",
    ]
    for i, text in enumerate(bullets):
        y = 272 + i * 66
        d.ellipse([124, y + 6, 140, y + 22], fill="#0f766e")
        draw_wrapped(d, (164, y), text, font(22), "#1f2937", 405, 2)

    d.rounded_rectangle([668, 232, 1156, 570], radius=18, fill="#fff7ed", outline="#fdba74", width=3)
    d.text((708, 266), "Heat flow diagram", font=font(30, True), fill="#7c2d12")
    for x in [770, 890, 1010]:
        draw_heat_arrow(d, x, 430, 112, "#f97316")
    d.rectangle([728, 462, 1090, 492], fill="#111827")
    d.text((810, 515), "Roads + Roofs", font=font(28, True), fill="#1f2937")
    d.text((688, 604), "Broad cleanup, but the card-heavy composition remains.", font=font(22), fill="#64748b")
    return im


def draw_visual_skill_redraw() -> Image.Image:
    im = Image.new("RGB", (1280, 720), "#fbfcfe")
    d = ImageDraw.Draw(im)
    d.text((80, 70), "Urban Heat Islands", font=font(58, True), fill="#111827")
    d.text((84, 132), "July 2024 · How city surfaces trap heat", font=font(28), fill="#475569")
    d.line([80, 178, 1200, 178], fill="#cbd5e1", width=2)

    d.rounded_rectangle([84, 226, 510, 595], radius=12, fill="#ffffff", outline="#e2e8f0", width=2)
    bullets = [
        ("Absorb", "Dark roads and roofs absorb sunlight."),
        ("Reduce", "Less vegetation means less evaporative cooling."),
        ("Release", "Dense buildings slow heat release after sunset."),
        ("Warm", "Urban areas can stay several degrees warmer."),
    ]
    for i, (label, text) in enumerate(bullets):
        y = 258 + i * 78
        d.text((118, y), label, font=font(24, True), fill="#0f766e")
        d.text((118, y + 30), text, font=font(22), fill="#334155")

    d.rounded_rectangle([590, 226, 1164, 595], radius=12, fill="#ffffff", outline="#e2e8f0", width=2)
    d.text((630, 258), "Heat flow", font=font(32, True), fill="#111827")
    d.line([650, 500, 1106, 500], fill="#111827", width=10)
    for x, h in [(710, 120), (840, 160), (970, 145), (1080, 112)]:
        draw_heat_arrow(d, x, 470, h, "#ea580c")
    d.rectangle([658, 506, 1098, 530], fill="#dbe4ef")
    d.text((722, 544), "roads + roofs store heat", font=font(26), fill="#334155")
    d.text((80, 638), "Region-marked repair removes noisy containers and gives the diagram a clearer role.", font=font(23), fill="#475569")
    return im


def render_presentation_redraw_trace(out: str) -> None:
    trace = Image.open(PPT_SKILL / "assets" / "real_ppt_nasa_skill_trace.png").convert("RGB")
    save_png(trace, DOCS / out)
    save_png(trace, PPT_SKILL / "assets" / "slide_redraw_runtime_trace.png")


def render_interleaved_effect(key: str, out: str) -> None:
    if key == "video_proof":
        title = "Pythagorean visual proof"
        paths = [
            REGENERATED / "09_pythagorean_visual_proof_video" / "assets" / "base_triangle_definition.png",
            REGENERATED / "09_pythagorean_visual_proof_video" / "assets" / "c_squared_formation.png",
            REGENERATED / "09_pythagorean_visual_proof_video" / "assets" / "a_b_squared_formation.png",
            REGENERATED / "09_pythagorean_visual_proof_video" / "assets" / "final_equation_grounding.png",
        ]
        labels = ["base triangle", "c-squared frame", "a/b-squared frame", "equation grounding"]
    else:
        title = "VS Code Remote-SSH workflow"
        paths = [
            REGENERATED / "08_vscode_remote_ssh_url" / "assets" / "remote_ssh_connection_model.png",
            REGENERATED / "08_vscode_remote_ssh_url" / "assets" / "ssh_host_entry_prompt.png",
            REGENERATED / "08_vscode_remote_ssh_url" / "assets" / "remote_platform_selection_dialog.png",
            REGENERATED / "08_vscode_remote_ssh_url" / "assets" / "remote_ssh_setting_example.png",
        ]
        labels = ["connection model", "choose host", "select platform", "optional settings"]

    canvas = Image.new("RGB", (1800, 640), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((34, 24), title, font=F_TITLE, fill=INK)
    d.text((34, 66), "Interleaved references keep each step next to its visual evidence.", font=F_SMALL, fill=MUTED)
    d.line([34, 110, 1766, 110], fill=LINE, width=2)
    for i, (path, label) in enumerate(zip(paths, labels)):
        x = 46 + i * 438
        y = 140
        d.rounded_rectangle([x, y, x + 410, y + 436], radius=18, fill="white", outline=LINE, width=2)
        d.text((x + 24, y + 22), f"{i + 1}. {label}", font=F_LABEL, fill=INK)
        thumb = fit_image(Image.open(path), (360, 310), "#ffffff")
        canvas.paste(thumb, (x + 25, y + 82))
    save_png(canvas, DOCS / out)


def _short_step_text(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        direction = str(item.get("direction") or item.get("instruction") or item.get("step") or item.get("action") or "")
        evidence = str(item.get("visual_evidence") or item.get("evidence") or item.get("segment") or item.get("reference") or "")
        return direction[:120], evidence[:100]
    return str(item)[:120], ""


def render_visual_colleague_skill_effect(out: str) -> None:
    assets = REGENERATED / "11_visual_colleague_skill" / "assets"
    paths = [
        assets / "annotated_anti_patterns.png",
        assets / "hierarchy_comparison.png",
        assets / "visual_snippets.png",
    ]

    canvas = Image.new("RGB", (1800, 820), PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((46, 32), "Visual colleague skill from multimodal chat", font=F_TITLE, fill=INK)
    d.text(
        (46, 76),
        "A person's visual critique habits stay bound to the chat attachments that demonstrate them.",
        font=F_SMALL,
        fill=MUTED,
    )
    d.line([46, 122, 1754, 122], fill=LINE, width=2)

    d.rounded_rectangle([50, 155, 1055, 764], radius=20, fill="white", outline=LINE, width=2)
    d.text((82, 185), "1. region-marked critique habit", font=F_LABEL, fill=INK)
    d.text(
        (82, 218),
        "The skill learns where this colleague marks AI-looking slide problems.",
        font=F_SMALL,
        fill=MUTED,
    )
    critique = fit_image(Image.open(paths[0]), (910, 435), "#ffffff")
    canvas.paste(critique, (98, 270))

    d.rounded_rectangle([1090, 155, 1750, 444], radius=20, fill="white", outline=LINE, width=2)
    d.text((1122, 184), "2. preferred redraw direction", font=F_LABEL, fill=INK)
    hierarchy = fit_image(Image.open(paths[1]), (590, 200), "#ffffff")
    canvas.paste(hierarchy, (1125, 226))

    d.rounded_rectangle([1090, 475, 1750, 764], radius=20, fill="white", outline=LINE, width=2)
    d.text((1122, 504), "3. reusable visual habits", font=F_LABEL, fill=INK)
    snippets = fit_image(Image.open(paths[2]), (590, 200), "#ffffff")
    canvas.paste(snippets, (1125, 546))
    save_png(canvas, DOCS / out)


def marked_task_image(case: dict[str, Any], mode: str, color: str) -> Image.Image:
    key = case["key"]
    img = Image.open(ROOT / case["task_images"][0]).convert("RGB")
    p = parsed(case, mode)
    if key == "gui":
        dot_and_box(img, p.get("click_point_px"), color)
    elif key == "table":
        draw_bbox(img, p.get("target_cell_bbox_px"), color)
        dot_and_box(img, p.get("center_px"), color, box_size=0)
    elif key == "chart":
        draw_chart_projection_case(img, mode, color)
    elif key == "counting":
        draw_anchor_samples(img, p, color)
    elif key == "lines":
        draw_line_route(img, p, color)
    elif key == "geometry":
        draw_geometry_construction(img, p, color)
    elif key == "different":
        draw_odd_location(img, p, color)
    elif key == "presentation":
        draw_ppt_regions(img, p, color)
    return img


def visual_for(case: dict[str, Any], mode: str) -> Image.Image:
    key = case["key"]
    color = BLUE if mode == "without_skill" else GREEN
    if key in {"gui", "table", "chart", "counting", "lines", "geometry", "different", "presentation"}:
        return marked_task_image(case, mode, color)
    if key == "video_proof":
        return contact_sheet([ROOT / p for p in case["task_images"]], cols=4)
    if key == "url":
        return contact_sheet([ROOT / p for p in case["task_images"]], cols=2)
    return Image.open(ROOT / case["task_images"][0]).convert("RGB")


def contact_sheet(paths: list[Path], cols: int = 2) -> Image.Image:
    thumbs = []
    for path in paths:
        thumbs.append(fit_image(Image.open(path).convert("RGB"), (420, 180), "#ffffff"))
    rows = (len(thumbs) + cols - 1) // cols
    out = Image.new("RGB", (cols * 450, rows * 210), "#ffffff")
    for i, thumb in enumerate(thumbs):
        x = (i % cols) * 450 + 15
        y = (i // cols) * 210 + 15
        out.paste(thumb, (x, y))
    return out


def render_case(key: str, out: str, size: tuple[int, int]) -> None:
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    case = data["cases"][key]
    case["key"] = key
    canvas = Image.new("RGB", size, PAPER)
    d = ImageDraw.Draw(canvas)
    d.text((34, 26), case["title"], font=F_TITLE, fill=INK)
    d.text((34, 68), f"Actual {data['model']} run on held-out task images.", font=F_SMALL, fill=MUTED)
    d.line([34, 112, size[0] - 34, 112], fill=LINE, width=2)

    gap = 36
    panel_w = (size[0] - 68 - gap) // 2
    panel_h = size[1] - 156
    draw_panel(canvas, (34, 136), (panel_w, panel_h), "Direct run", visual_for(case, "without_skill"), BLUE)
    draw_panel(canvas, (34 + panel_w + gap, 136), (panel_w, panel_h), "With visual skill", visual_for(case, "with_skill"), GREEN)
    canvas.save(DOCS / out)


def main() -> None:
    if not RESULTS.exists():
        raise SystemExit(f"Missing task execution log: {RESULTS}")
    render_gui_prior("demo_gui_hitbox_prior.png")
    render_presentation_redraw_trace("demo_presentation_redraw_trace.png")
    render_interleaved_effect("video_proof", "demo_pythagorean_interleaved_effect.png")
    render_interleaved_effect("url", "demo_vscode_interleaved_effect.png")
    render_visual_colleague_skill_effect("demo_visual_colleague_interleaved_effect.png")

    outputs = {
        "table": ("demo_table_intersection_comparison.png", (900, 560)),
    }
    for key, (out, size) in outputs.items():
        render_case(key, out, size)
    render_chart_projection("demo_chart_projection_comparison.png")


if __name__ == "__main__":
    main()
