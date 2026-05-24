"""Run downstream task executions with and without generated visual skills.

The script calls an OpenAI-compatible multimodal chat endpoint. It stores the
model outputs, but never stores API credentials.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "curated_skills" / "open_source_homepage_regenerated"
DOCS = ROOT / "docs" / "assets"
EVAL_ROOT = ROOT / "examples" / "task_execution_cases"
EVAL_ASSETS = EVAL_ROOT / "assets"
RESULTS_PATH = EVAL_ROOT / "task_execution_results.json"


@dataclass(frozen=True)
class Case:
    key: str
    title: str
    skill_dir: Path
    task_prompt: str
    task_images: tuple[Path, ...]
    skill_images: tuple[Path, ...] = ()
    runtime_images: tuple[Path, ...] = ()
    expected: str | None = None
    skill_text_override: str | None = None


def _image_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def _image_part(path: Path) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {
            "url": _image_data_url(path),
            "detail": "high",
        },
    }


def _write_left_panel(src: Path, out: Path) -> Path:
    if out.exists():
        return out
    im = Image.open(src).convert("RGB")
    im.crop((0, 0, im.width // 2, im.height)).save(out)
    return out


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Times New Roman Bold.ttf" if bold else "Times New Roman.ttf"
    path = Path("/System/Library/Fonts/Supplemental") / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _draw_search_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=5)
    draw.line([cx + r - 3, cy + r - 3, cx + r + 20, cy + r + 20], fill=color, width=5)


def _write_hard_gui_task(out: Path) -> Path:
    im = Image.new("RGB", (900, 420), "#f6f8fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([92, 118, 808, 302], radius=34, fill="white", outline="#c8d2e2", width=3)
    x = 132
    buttons = [
        ("home", 82),
        ("search", 128),
        ("add", 82),
        ("sync", 82),
        ("search-small", 82),
        ("user", 82),
    ]
    for name, w in buttons:
        box = [x, 168, x + w, 252]
        fill = "#ffffff"
        d.rounded_rectangle(box, radius=14, fill=fill, outline="#b9c7da", width=2)
        if name == "home":
            d.polygon([(x + 28, 213), (x + 41, 194), (x + 54, 213)], outline="#334155", fill=None)
            d.rectangle([x + 34, 213, x + 48, 229], outline="#334155", width=3)
        elif name == "search":
            # Deliberately off-center glyph: the button hitbox center is to the
            # lower-right of the icon ink, making the task expose hitbox-vs-glyph
            # grounding.
            _draw_search_icon(d, x + 42, 197, 14, "#334155")
        elif name == "add":
            d.line([x + w // 2, 190, x + w // 2, 230], fill="#334155", width=5)
            d.line([x + w // 2 - 20, 210, x + w // 2 + 20, 210], fill="#334155", width=5)
        elif name == "sync":
            d.arc([x + 24, 188, x + 58, 226], 205, 30, fill="#334155", width=4)
            d.line([x + 58, 226, x + 66, 224], fill="#334155", width=4)
            d.ellipse([x + 39, 229, x + 47, 237], fill="#334155")
        elif name == "search-small":
            _draw_search_icon(d, x + w // 2, 210, 10, "#94a3b8")
        else:
            d.ellipse([x + 35, 190, x + 51, 206], outline="#334155", width=4)
            d.arc([x + 24, 206, x + 62, 238], 200, 340, fill="#334155", width=4)
        x += w + 22
    d.text((120, 86), "Hard UI hitbox task", font=_font(24, True), fill="#1f2530")
    im.save(out)
    return out


def _hard_counting_points() -> list[tuple[int, int]]:
    return _hard_counting_layout()[0]


def _hard_counting_red_distractors() -> list[tuple[int, int]]:
    return _hard_counting_layout()[1]


def _hard_counting_layout() -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    rng = random.Random(20260528)
    avoid = [(285, 170), (296, 226), (515, 175), (790, 238), (970, 190)]
    points: list[tuple[int, int]] = []
    while len(points) < 152:
        x = rng.randint(92, 995)
        y = rng.randint(140, 358)
        if any((x - ax) ** 2 + (y - ay) ** 2 < 30**2 for ax, ay in avoid):
            continue
        if all((x - px) ** 2 + (y - py) ** 2 >= 24**2 for px, py in points):
            points.append((x, y))
    rng.shuffle(points)
    targets = sorted(points[:96], key=lambda p: (p[1] // 42, p[0]))
    red_distractors = sorted(points[96:], key=lambda p: (p[1] // 42, p[0]))
    return targets, red_distractors


def _write_hard_counting_task(out: Path) -> Path:
    im = Image.new("RGB", (1088, 454), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([26, 32, 1062, 422], radius=20, fill="white", outline="#cbd5e1", width=3)
    d.text((54, 52), "Count red target tokens", font=_font(30, True), fill="#1f2530")
    d.text((54, 88), "Count red circles with a white center dot. Ignore solid red and non-red distractors.", font=_font(20), fill="#64748b")
    red = "#d92d20"
    points = _hard_counting_points()
    red_distractors = _hard_counting_red_distractors()
    distractors = [
        (285, 170, "gray", "#94a3b8"), (296, 226, "diamond", "#8b5cf6"),
        (515, 175, "square", "#2563eb"), (790, 238, "gray", "#94a3b8"),
        (970, 190, "square", "#2563eb"),
    ]
    for x, y in red_distractors:
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=red, outline="#9f1d16", width=2)
    for x, y, kind, color in distractors:
        if kind == "square":
            d.rounded_rectangle([x - 12, y - 12, x + 12, y + 12], radius=4, fill=color, outline="#1d4ed8", width=2)
        elif kind == "diamond":
            d.polygon([(x, y - 15), (x + 15, y), (x, y + 15), (x - 15, y)], fill=color, outline="#6d28d9")
        else:
            d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=color, outline="#64748b", width=2)
    for x, y in points:
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=red, outline="#9f1d16", width=2)
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill="#fee2e2")
    im.save(out)
    return out


def _write_hard_counting_runtime_overlay(src: Path, out: Path) -> Path:
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im)
    points = _hard_counting_points()
    for x, y in points:
        d.ellipse([x - 11, y - 11, x + 11, y + 11], outline="#10b981", width=3)
    badge_font = _font(22, True)
    label = f"Counted red tokens: {len(points)}"
    bbox = d.textbbox((0, 0), label, font=badge_font)
    x2, y1 = im.width - 54, 56
    x1 = x2 - (bbox[2] - bbox[0]) - 28
    y2 = y1 + (bbox[3] - bbox[1]) + 20
    d.rounded_rectangle([x1, y1, x2, y2], radius=12, fill="#ecfdf5", outline="#10b981", width=3)
    d.text((x1 + 14, y1 + 9), label, font=badge_font, fill="#047857")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _write_hard_odd_one_out_task(out: Path) -> Path:
    im = Image.new("RGB", (1220, 760), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([28, 28, 1192, 732], radius=22, fill="white", outline="#cbd5e1", width=3)
    d.text((58, 54), "Find the shape anomaly", font=_font(30, True), fill="#1f2530")
    d.text((58, 90), "Ignore color accents; compare the tiny icon structure.", font=_font(20), fill="#64748b")
    odd = (8, 12)
    decoys = {(3, 8), (6, 3), (2, 5), (8, 2), (11, 7), (5, 13)}
    label_font = _font(14, True)
    for col in range(1, 15):
        cx = 100 + (col - 1) * 78
        d.text((cx - 5, 117), str(col), font=label_font, fill="#94a3b8")
    for row in range(1, 13):
        cy = 145 + (row - 1) * 47
        d.text((58, cy - 8), str(row), font=label_font, fill="#94a3b8")

    for row, col, cx, cy in _odd_one_out_centers():
        fill = "#fff7ed" if (row, col) in decoys else "#f8fafc"
        outline = "#fb923c" if (row, col) in decoys else "#dbe5f0"
        d.rounded_rectangle([cx - 23, cy - 17, cx + 23, cy + 17], radius=7, fill=fill, outline=outline, width=1)
        d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline="#2563eb", width=3)
        d.line([cx + 6, cy - 6, cx + 13, cy - 13], fill="#94a3b8", width=2)
        if (row, col) != odd:
            d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill="#2563eb")
    im.save(out)
    return out


def _odd_one_out_centers() -> list[tuple[int, int, int, int]]:
    rows, cols = 12, 14
    start_x, start_y = 100, 145
    dx, dy = 78, 47
    return [
        (row, col, start_x + (col - 1) * dx, start_y + (row - 1) * dy)
        for row in range(1, rows + 1)
        for col in range(1, cols + 1)
    ]


def _write_hard_odd_one_out_runtime_overlay(src: Path, out: Path) -> Path:
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im)
    odd = (8, 12)
    for row, col, cx, cy in _odd_one_out_centers():
        if (row, col) == odd:
            continue
        d.line([cx - 17, cy + 10, cx - 12, cy + 16, cx - 3, cy + 3], fill="#10b981", width=2)
    for row, col, cx, cy in _odd_one_out_centers():
        if (row, col) == odd:
            d.ellipse([cx - 31, cy - 31, cx + 31, cy + 31], outline="#ef4444", width=5)
            d.ellipse([cx - 17, cy - 17, cx + 17, cy + 17], outline="#f97316", width=4)
            break
    im.save(out)
    return out


def _write_odd_one_out_gallery_trace(task: Path, overlay: Path, out: Path) -> Path:
    left = Image.open(task).convert("RGB")
    right = Image.open(overlay).convert("RGB")
    canvas = Image.new("RGB", (1088, 454), "#f7f9fc")
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([14, 14, 532, 440], radius=18, fill="white", outline="#cbd5e1", width=2)
    d.rounded_rectangle([556, 14, 1074, 440], radius=18, fill="white", outline="#cbd5e1", width=2)
    d.text((32, 32), "Original Image", font=_font(26, True), fill="#1f2530")
    d.text((574, 32), "Runtime Overlay", font=_font(26, True), fill="#1f2530")
    d.text((32, 62), "No checked state yet.", font=_font(17), fill="#64748b")
    d.text((574, 62), "Checked candidates and hypothesis are visible.", font=_font(17), fill="#64748b")
    crop = (50, 122, 1166, 718)
    left_thumb = left.crop(crop)
    right_thumb = right.crop(crop)
    left_thumb.thumbnail((480, 330), Image.Resampling.LANCZOS)
    right_thumb.thumbnail((480, 330), Image.Resampling.LANCZOS)
    canvas.paste(left_thumb, (34 + (480 - left_thumb.width) // 2, 92 + (330 - left_thumb.height) // 2))
    canvas.paste(right_thumb, (576 + (480 - right_thumb.width) // 2, 92 + (330 - right_thumb.height) // 2))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def _write_heldout_table_task(out: Path) -> Path:
    im = Image.new("RGB", (900, 420), "#f6f8fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([150, 70, 750, 360], radius=18, fill="white", outline="#c8d2e2", width=3)
    d.text((185, 90), "Held-out table task", font=_font(24, True), fill="#1f2530")
    cols = ["Q1", "Q2", "Q3", "Q4"]
    rows = ["W", "X", "Y", "Z"]
    left, top = 265, 145
    cell_w, cell_h = 92, 50
    for i, col in enumerate(cols):
        d.text((left + i * cell_w + 35, top - 34), col, font=_font(20, True), fill="#1f2530")
    for i, row in enumerate(rows):
        d.text((left - 46, top + i * cell_h + 14), row, font=_font(20, True), fill="#1f2530")
    for r in range(5):
        y = top + r * cell_h
        d.line([left, y, left + 4 * cell_w, y], fill="#b8c4d6", width=3)
    for c in range(5):
        x = left + c * cell_w
        d.line([x, top, x, top + 4 * cell_h], fill="#b8c4d6", width=3)
    for r in range(4):
        for c in range(4):
            cx = left + c * cell_w + cell_w // 2
            cy = top + r * cell_h + cell_h // 2
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill="#cbd5e1")
    im.save(out)
    return out


def _write_heldout_chart_task(out: Path) -> Path:
    im = Image.new("RGB", (900, 420), "#f6f8fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([95, 48, 805, 376], radius=18, fill="white", outline="#c8d2e2", width=3)
    d.text((128, 72), "Held-out projection task", font=_font(24, True), fill="#1f2530")
    x0, y0, y_top = 180, 320, 105
    lo, hi = 40, 100
    d.line([x0, y_top, x0, y0], fill="#1f2530", width=4)
    d.line([x0, y0, 720, y0], fill="#1f2530", width=4)
    for value in range(lo, hi + 1, 20):
        y = y0 - int((value - lo) * (y0 - y_top) / (hi - lo))
        d.line([x0 - 8, y, x0, y], fill="#1f2530", width=3)
        d.text((x0 - 45, y - 10), str(value), font=_font(16), fill="#475569")
        d.line([x0, y, 720, y], fill="#e2e8f0", width=1)
    labels = ["A", "B", "C", "D", "E"]
    values = [42, 67, 73, 58, 91]
    bar_w, gap = 38, 40
    start = 225
    for i, (label, value) in enumerate(zip(labels, values)):
        x1 = start + i * (bar_w + gap)
        y1 = y0 - int((value - lo) * (y0 - y_top) / (hi - lo))
        d.rounded_rectangle([x1, y1, x1 + bar_w, y0], radius=5, fill="#60a5fa", outline="#2563eb", width=2)
        d.text((x1 + 12, y0 + 14), label, font=_font(18, True), fill="#1f2530")
    d.rounded_rectangle([371, 156, 441, 188], radius=8, fill="#fff7ed", outline="#fb923c", width=3)
    d.text((388, 162), "80", font=_font(20, True), fill="#9a3412")
    im.save(out)
    return out


def _write_heldout_line_task(out: Path) -> Path:
    im = Image.new("RGB", (1088, 454), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([26, 32, 1062, 422], radius=20, fill="white", outline="#cbd5e1", width=3)
    d.text((54, 52), "Trace the connected line from A to B", font=_font(30, True), fill="#1f2530")
    pts = {
        "A": (170, 130),
        "1": (330, 130),
        "2": (465, 210),
        "3": (465, 295),
        "4": (315, 350),
        "B": (640, 350),
        "X": (675, 130),
        "Y": (750, 260),
        "Z": (170, 295),
        "W": (555, 130),
        "V": (555, 350),
    }
    route_edges = [("A", "1"), ("1", "2"), ("2", "3"), ("3", "4"), ("4", "B")]
    distractor_edges = [("A", "Z"), ("1", "W"), ("W", "X"), ("X", "Y"), ("V", "B")]
    for a, b in distractor_edges:
        d.line([pts[a], pts[b]], fill="#cbd5e1", width=9)
        d.line([pts[a], pts[b]], fill="#f8fafc", width=3)
    for a, b in route_edges:
        d.line([pts[a], pts[b]], fill="#cbd5e1", width=9)
        d.line([pts[a], pts[b]], fill="#f8fafc", width=3)
    for label, (x, y) in pts.items():
        d.ellipse([x - 20, y - 20, x + 20, y + 20], fill="#ffffff", outline="#1f2937", width=3)
        if label in {"A", "B"}:
            d.text((x - 7, y - 50), label, font=_font(22, True), fill="#1f2530")
        else:
            d.text((x - 5, y - 10), label, font=_font(16, True), fill="#64748b")
    im.save(out)
    return out


def _write_heldout_geometry_task(out: Path) -> Path:
    im = Image.new("RGB", (1088, 454), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([26, 32, 1062, 422], radius=20, fill="white", outline="#cbd5e1", width=3)
    d.text((54, 52), "Held-out geometry problem", font=_font(30, True), fill="#1f2530")
    d.text((54, 88), "Triangle PQR is isosceles with PQ = PR.", font=_font(20), fill="#64748b")
    p, q, r = (540, 105), (265, 350), (815, 350)
    d.line([q, p, r, q], fill="#1f2530", width=5)
    d.text((p[0] - 8, p[1] - 38), "P", font=_font(22, True), fill="#1f2530")
    d.text((q[0] - 34, q[1] + 8), "Q", font=_font(22, True), fill="#1f2530")
    d.text((r[0] + 16, r[1] + 8), "R", font=_font(22, True), fill="#1f2530")
    d.line([390, 223, 407, 238], fill="#2563eb", width=4)
    d.line([673, 238, 690, 223], fill="#2563eb", width=4)
    d.arc([220, 315, 292, 387], 205, 270, fill="#f59e0b", width=4)
    d.arc([778, 315, 850, 387], 270, 335, fill="#f59e0b", width=4)
    im.save(out)
    return out


def _write_heldout_ppt_task(out: Path) -> Path:
    im = Image.new("RGB", (1280, 720), "#f7f9fc")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1280, 720], fill="#f7f9fc")
    d.rounded_rectangle([46, 38, 1234, 682], radius=18, fill="white", outline="#cbd5e1", width=3)
    d.rounded_rectangle([74, 66, 720, 150], radius=12, fill="#0f766e")
    d.text((102, 82), "July 2024: Urban Heat Islands", font=_font(40, True), fill="white")
    d.text((96, 172), "How city surfaces trap heat.", font=_font(26, True), fill="#1f2530")
    d.rounded_rectangle([82, 220, 565, 590], radius=18, fill="#f0fdfa", outline="#5eead4", width=3)
    body = [
        "Dark roads and roofs absorb sunlight.",
        "Less vegetation means less evaporative cooling.",
        "Dense buildings slow heat release after sunset.",
        "Urban areas can stay several degrees warmer.",
    ]
    for i, text in enumerate(body):
        y = 250 + i * 74
        d.ellipse([110, y + 4, 126, y + 20], fill="#0f766e")
        d.text((146, y), text, font=_font(25), fill="#1f2530")
    d.rounded_rectangle([620, 210, 1160, 600], radius=22, fill="#fee2e2", outline="#fb7185", width=3)
    d.text((650, 238), "Heat flow diagram", font=_font(30, True), fill="#7f1d1d")
    for x in [700, 835, 970, 1105]:
        d.polygon([(x, 292), (x + 28, 355), (x + 10, 355), (x + 10, 440), (x - 10, 440), (x - 10, 355), (x - 28, 355)], fill="#f97316", outline="#9a3412")
    d.rectangle([682, 470, 1122, 500], fill="#111827")
    d.text((724, 515), "Roads + Roofs", font=_font(27, True), fill="#1f2530")
    d.text((650, 560), "Causes", font=_font(30, True), fill="#dc2626")
    d.text((748, 560), "Heating", font=_font(30, True), fill="#dc2626")
    d.rounded_rectangle([74, 618, 1200, 664], radius=8, fill="#ecfeff", outline="#67e8f9", width=2)
    d.text((94, 629), "Footer: generic dots, decorative bar, and cramped source notes", font=_font(21), fill="#64748b")
    for x in range(930, 1145, 30):
        d.ellipse([x, 631, x + 12, 643], fill="#bae6fd")
    im.save(out)
    return out


def _write_heldout_pythagorean_frames(prefix: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    specs = [
        ("Step 1", "right triangle", "a", "b", "c"),
        ("Step 2", "same outer square", "c^2", "", ""),
        ("Step 3", "rearranged empty space", "a^2", "b^2", ""),
        ("Step 4", "area equality", "a^2 + b^2", "=", "c^2"),
    ]
    for i, (title, subtitle, left, mid, right) in enumerate(specs, start=1):
        out = prefix.with_name(f"{prefix.name}_{i}.png")
        im = Image.new("RGB", (640, 360), "#0f172a")
        d = ImageDraw.Draw(im)
        d.text((34, 26), title, font=_font(30, True), fill="#e2e8f0")
        d.text((34, 62), subtitle, font=_font(20), fill="#94a3b8")
        if i == 1:
            d.polygon([(155, 265), (155, 105), (405, 265)], fill="#1d4ed8", outline="#93c5fd")
            d.text((120, 175), left, font=_font(30, True), fill="#f8fafc")
            d.text((260, 276), mid, font=_font(30, True), fill="#f8fafc")
            d.text((285, 160), right, font=_font(30, True), fill="#f8fafc")
        elif i == 2:
            d.rectangle([165, 105, 485, 305], outline="#e2e8f0", width=4)
            d.polygon([(165, 105), (305, 105), (165, 245)], fill="#1d4ed8")
            d.polygon([(485, 305), (345, 305), (485, 165)], fill="#1d4ed8")
            d.rectangle([270, 160, 385, 275], outline="#22c55e", width=4)
            d.text((302, 198), left, font=_font(30, True), fill="#bbf7d0")
        elif i == 3:
            d.rectangle([165, 105, 485, 305], outline="#e2e8f0", width=4)
            d.rectangle([205, 145, 305, 245], outline="#22c55e", width=4)
            d.rectangle([350, 170, 450, 270], outline="#f59e0b", width=4)
            d.text((232, 178), left, font=_font(27, True), fill="#bbf7d0")
            d.text((376, 203), mid, font=_font(27, True), fill="#fde68a")
        else:
            d.text((145, 166), left, font=_font(38, True), fill="#bbf7d0")
            d.text((330, 166), mid, font=_font(38, True), fill="#e2e8f0")
            d.text((390, 166), right, font=_font(38, True), fill="#93c5fd")
        im.save(out)
        paths.append(out)
    return tuple(paths)


def _write_heldout_remote_ssh_frames(prefix: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    titles = [
        ("Connection model", "Local editor -> SSH tunnel -> remote server"),
        ("Choose host", "dev-box.internal"),
        ("Select platform", "Linux"),
        ("Advanced option", "Remote server listen on socket"),
    ]
    for i, (title, body) in enumerate(titles, start=1):
        out = prefix.with_name(f"{prefix.name}_{i}.png")
        im = Image.new("RGB", (720, 360), "#f8fafc")
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([28, 32, 692, 328], radius=16, fill="white", outline="#cbd5e1", width=3)
        d.text((56, 58), title, font=_font(31, True), fill="#1f2530")
        if i == 1:
            d.rounded_rectangle([78, 160, 238, 222], radius=14, fill="#dbeafe", outline="#60a5fa", width=3)
            d.rounded_rectangle([482, 160, 642, 222], radius=14, fill="#dcfce7", outline="#4ade80", width=3)
            d.line([246, 191, 474, 191], fill="#2563eb", width=6)
            d.text((104, 179), "Local", font=_font(22, True), fill="#1e3a8a")
            d.text((506, 179), "Remote", font=_font(22, True), fill="#166534")
        elif i == 2:
            d.rounded_rectangle([92, 150, 628, 225], radius=10, fill="#eff6ff", outline="#93c5fd", width=3)
            d.text((122, 171), "ssh user@" + body, font=_font(25), fill="#1f2530")
        elif i == 3:
            for idx, option in enumerate(["Linux", "Windows", "macOS"]):
                y = 128 + idx * 58
                fill = "#dcfce7" if option == "Linux" else "#ffffff"
                d.rounded_rectangle([120, y, 600, y + 42], radius=8, fill=fill, outline="#cbd5e1", width=2)
                d.text((145, y + 8), option, font=_font(24), fill="#1f2530")
        else:
            d.rounded_rectangle([94, 145, 626, 230], radius=10, fill="#fff7ed", outline="#fdba74", width=3)
            d.text((124, 171), body, font=_font(24), fill="#1f2530")
        im.save(out)
        paths.append(out)
    return tuple(paths)


def _write_heldout_visual_colleague_slide(out: Path) -> Path:
    im = Image.new("RGB", (960, 560), "#f8fafc")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([32, 32, 928, 528], radius=24, fill="white", outline="#cbd5e1", width=3)
    d.text((70, 70), "Held-out slide draft", font=_font(34, True), fill="#1f2530")
    d.text((70, 112), "Critique and redraw using the generated visual colleague skill.", font=_font(21), fill="#64748b")
    d.rounded_rectangle([82, 155, 878, 470], radius=18, fill="#ffffff", outline="#cbd5e1", width=3)
    d.rounded_rectangle([110, 188, 842, 240], radius=8, fill="#4f46e5")
    d.text((132, 202), "Q4 Customer Insights", font=_font(28, True), fill="white")
    for i, title in enumerate(["Signals", "Segments", "Actions", "KPIs"]):
        x = 120 + (i % 2) * 245
        y = 270 + (i // 2) * 86
        d.rounded_rectangle([x, y, x + 210, y + 64], radius=9, fill="#eef2ff", outline="#cbd5e1", width=2)
        d.text((x + 16, y + 12), title, font=_font(18, True), fill="#1f2530")
        d.line([x + 16, y + 40, x + 180, y + 40], fill="#94a3b8", width=3)
    d.rounded_rectangle([620, 270, 835, 420], radius=10, fill="#fff1f2", outline="#f87171", width=3)
    for x in [675, 730, 785]:
        d.polygon([(x, 315), (x - 18, 360), (x - 6, 360), (x - 6, 394), (x + 6, 394), (x + 6, 360), (x + 18, 360)], fill="#f97316")
    d.rectangle([650, 405, 815, 414], fill="#111827")
    d.rounded_rectangle([112, 488, 842, 512], radius=5, fill="#e0f2fe", outline="#67e8f9", width=2)
    im.save(out)
    return out


def _prepare_assets() -> None:
    EVAL_ASSETS.mkdir(parents=True, exist_ok=True)
    _write_hard_gui_task(EVAL_ASSETS / "gui_hard_hitbox_task.png")
    _write_hard_counting_task(EVAL_ASSETS / "counting_hard_task.png")
    _write_hard_counting_runtime_overlay(
        EVAL_ASSETS / "counting_hard_task.png",
        EVAL_ASSETS / "counting_hard_task_runtime_overlay.png",
    )
    _write_hard_odd_one_out_task(EVAL_ASSETS / "odd_one_out_hard_task.png")
    _write_hard_odd_one_out_runtime_overlay(
        EVAL_ASSETS / "odd_one_out_hard_task.png",
        EVAL_ASSETS / "odd_one_out_hard_task_runtime_overlay.png",
    )
    _write_heldout_table_task(EVAL_ASSETS / "table_heldout_task.png")
    _write_heldout_chart_task(EVAL_ASSETS / "chart_heldout_task.png")
    _write_heldout_line_task(EVAL_ASSETS / "line_heldout_task.png")
    _write_heldout_geometry_task(EVAL_ASSETS / "geometry_heldout_task.png")
    _write_heldout_ppt_task(EVAL_ASSETS / "ppt_heldout_task.png")
    _write_heldout_pythagorean_frames(EVAL_ASSETS / "pythagorean_heldout")
    _write_heldout_remote_ssh_frames(EVAL_ASSETS / "remote_ssh_heldout")
    _write_heldout_visual_colleague_slide(EVAL_ASSETS / "visual_colleague_heldout_slide.png")
    _write_left_panel(DOCS / "demo_counting_trace.png", EVAL_ASSETS / "counting_task.png")
    _write_left_panel(DOCS / "demo_line_tracing_trace.png", EVAL_ASSETS / "line_tracing_task.png")
    _write_odd_one_out_gallery_trace(
        EVAL_ASSETS / "odd_one_out_hard_task.png",
        EVAL_ASSETS / "odd_one_out_hard_task_runtime_overlay.png",
        DOCS / "demo_odd_one_out_trace.png",
    )


def _cases() -> list[Case]:
    _prepare_assets()
    return [
        Case(
            key="gui",
            title="Button click target",
            skill_dir=EXAMPLES / "03_gui_icon_grounding",
            task_images=(EVAL_ASSETS / "gui_hard_hitbox_task.png",),
            skill_images=(
                EXAMPLES / "03_gui_icon_grounding" / "assets" / "search_button_hitbox_overlay.png",
            ),
            task_prompt=(
                "Task: click the Search control in this toolbar. Return compact JSON "
                "with keys answer, click_point_px, confidence, and evidence. The "
                "click_point_px must be pixel coordinates in the task image."
            ),
            expected="Click the center of the Search button hitbox, not the off-center magnifier glyph.",
        ),
        Case(
            key="table",
            title="Table cell intersection",
            skill_dir=EXAMPLES / "04_table_cell_intersection",
            task_images=(EVAL_ASSETS / "table_heldout_task.png",),
            skill_images=(
                EXAMPLES / "04_table_cell_intersection" / "assets" / "row_col_intersection_overlay.png",
            ),
            task_prompt=(
                "Task: locate the target cell at row Y and column Q2. Return compact "
                "JSON with keys answer, cell, target_cell_bbox_px, center_px, "
                "confidence, and evidence. All coordinates must be in the task image."
            ),
            expected="Target cell is row Y, column Q2 in the held-out table.",
        ),
        Case(
            key="chart",
            title="Bar chart projection",
            skill_dir=EXAMPLES / "05_chart_projection",
            task_images=(EVAL_ASSETS / "chart_heldout_task.png",),
            skill_images=(
                EXAMPLES / "05_chart_projection" / "assets" / "bar_projection_guide.png",
            ),
            task_prompt=(
                "Task: read the value of bar C from the chart image. Return compact "
                "JSON with keys answer, value_estimate, target_bar_bbox_px, "
                "projection_y_px, evidence_source_bbox_px, confidence, and evidence."
            ),
            expected="Bar C is about 73; the floating label 80 is a distractor, not the axis readout.",
            skill_text_override=(
                "Use the generated bar-projection visual skill: locate the requested "
                "bar by its x-axis label, identify the actual top edge of the bar, "
                "project that top edge horizontally to the y-axis, and interpolate "
                "between the nearest ticks. Treat floating annotation labels as "
                "non-axis evidence; do not use them as the answer unless the task "
                "explicitly asks for annotation text."
            ),
        ),
        Case(
            key="presentation",
            title="PPT critique-and-redraw",
            skill_dir=EXAMPLES / "13_presentation_style_redraw",
            task_images=(EVAL_ASSETS / "ppt_heldout_task.png",),
            skill_images=(
                EXAMPLES
                / "13_presentation_style_redraw"
                / "assets"
                / "style_reference_board.png",
                EXAMPLES
                / "13_presentation_style_redraw"
                / "assets"
                / "real_ppt_nasa_critique_overlay.png",
            ),
            task_prompt=(
                "Task: redesign this held-out teaching slide into a cleaner professional "
                "PPT slide while preserving the scientific content. Return compact JSON "
                "with keys summary, layout_plan, concrete_changes, critique_regions, "
                "and preserved_content. critique_regions should be a short list of "
                "objects with label, issue, and bbox_px in the task image."
            ),
            expected="Preserve urban-heat content while improving hierarchy, spacing, and diagram clarity.",
        ),
        Case(
            key="counting",
            title="Dense counting",
            skill_dir=EXAMPLES / "02_dense_counting",
            task_images=(EVAL_ASSETS / "counting_hard_task.png",),
            runtime_images=(EVAL_ASSETS / "counting_hard_task_runtime_overlay.png",),
            task_prompt=(
                "Task: count how many red circular tokens with a white center dot are visible. "
                "Return compact JSON with keys answer, count, confidence, and evidence. "
                "Ignore solid red tokens and blue, purple, and gray distractors."
            ),
            expected="There are 96 red circular tokens with a white center dot.",
        ),
        Case(
            key="lines",
            title="Line tracing",
            skill_dir=EXAMPLES / "06_connect_lines",
            task_images=(EVAL_ASSETS / "line_heldout_task.png",),
            task_prompt=(
                "Task: trace the connected route from A to B. Return compact JSON "
                "with keys answer, route, confidence, and evidence. Do not use an "
                "edge unless it is visibly connected. Use visible node labels when available."
            ),
            expected="Trace A -> 1 -> 2 -> 3 -> 4 -> B in the held-out graph.",
        ),
        Case(
            key="geometry",
            title="Geometry auxiliary lines",
            skill_dir=EXAMPLES / "10_geometry_auxiliary_lines",
            task_images=(EVAL_ASSETS / "geometry_heldout_task.png",),
            skill_images=(EXAMPLES / "10_geometry_auxiliary_lines" / "assets" / "geometry_auxiliary_overlay.png",),
            task_prompt=(
                "Task: propose the first useful auxiliary construction for this "
                "isosceles-triangle diagram. Return compact JSON with keys answer, "
                "construction, visual_marks, confidence, and evidence. Keep "
                "visual_marks as short point/segment labels, not pixel coordinate arrays."
            ),
            expected="Construct the altitude/median from P to QR in the held-out triangle.",
        ),
        Case(
            key="different",
            title="Odd-one-out visual search",
            skill_dir=EXAMPLES / "07_find_different",
            task_images=(EVAL_ASSETS / "odd_one_out_hard_task.png",),
            skill_images=(EXAMPLES / "07_find_different" / "assets" / "incremental_comparison_protocol.png",),
            runtime_images=(EVAL_ASSETS / "odd_one_out_hard_task_runtime_overlay.png",),
            task_prompt=(
                "Task: find the one shape-anomaly item in the grid. Ignore color "
                "accents or tinted backgrounds. Return compact JSON with keys "
                "answer, location, distinguishing_feature, confidence, and evidence. "
                "The candidate grid has 12 rows and 14 columns. Count rows from "
                "the top visible candidate row and columns from the leftmost "
                "visible candidate column, starting at 1."
            ),
            expected="The shape anomaly is row 8, column 12; it is missing the central dot.",
        ),
        Case(
            key="video_proof",
            title="Pythagorean video proof",
            skill_dir=EXAMPLES / "09_pythagorean_visual_proof_video",
            task_images=(
                EVAL_ASSETS / "pythagorean_heldout_1.png",
                EVAL_ASSETS / "pythagorean_heldout_2.png",
                EVAL_ASSETS / "pythagorean_heldout_3.png",
                EVAL_ASSETS / "pythagorean_heldout_4.png",
            ),
            task_prompt=(
                "Task: explain the visual proof of the Pythagorean theorem from these "
                "held-out ordered frames. Return compact JSON with keys answer, "
                "ordered_steps, frame_references, confidence, and evidence."
            ),
            expected="Each proof step should cite the held-out frame that supports it.",
        ),
        Case(
            key="url",
            title="VS Code Remote-SSH docs",
            skill_dir=EXAMPLES / "08_vscode_remote_ssh_url",
            task_images=(
                EVAL_ASSETS / "remote_ssh_heldout_1.png",
                EVAL_ASSETS / "remote_ssh_heldout_2.png",
                EVAL_ASSETS / "remote_ssh_heldout_3.png",
                EVAL_ASSETS / "remote_ssh_heldout_4.png",
            ),
            task_prompt=(
                "Task: produce the ordered Remote-SSH procedure shown by these held-out "
                "screenshots. Return compact JSON with keys answer, steps, "
                "screenshot_references, confidence, and evidence. Use no more than "
                "four short steps."
            ),
            expected="Procedure should bind each action to the held-out screenshot that shows it.",
        ),
        Case(
            key="visual_colleague",
            title="Visual colleague slide critique skill",
            skill_dir=EXAMPLES / "11_visual_colleague_skill",
            task_images=(EVAL_ASSETS / "visual_colleague_heldout_slide.png",),
            skill_images=(
                EXAMPLES / "11_visual_colleague_skill" / "assets" / "annotated_anti_patterns.png",
                EXAMPLES / "11_visual_colleague_skill" / "assets" / "hierarchy_comparison.png",
                EXAMPLES / "11_visual_colleague_skill" / "assets" / "visual_snippets.png",
            ),
            task_prompt=(
                "Task: critique this held-out slide using the generated visual colleague "
                "skill. Return compact JSON with keys visual_critique, redraw_strategy, "
                "evidence_bindings, uncertainty, and privacy_note. evidence_bindings "
                "should name the source visual reference that supports each region-level "
                "design decision."
            ),
            expected="Use the colleague's region-marked critique habit, hierarchy comparison, and visual snippets to propose local redraw actions.",
            skill_text_override=(
                "Visual colleague slide critique skill: inspect the slide for heavy "
                "banner weight, fragmented boxes, generic diagrams, and footer noise. "
                "Bind critique points to the annotated anti-pattern reference, then "
                "use the hierarchy comparison and visual snippets to propose a cleaner "
                "redraw with whitespace, one visual argument, restrained palette, and "
                "focal orange only where the viewer should look first. Return JSON only."
            ),
        ),
    ]


def _case_messages(case: Case, *, with_skill: bool) -> list[dict[str, Any]]:
    mode = "with generated visual skill" if with_skill else "without generated visual skill"
    content: list[dict[str, Any]] = [
        {
            "type": "text",
                "text": (
                    "You are a vision-capable task agent. Solve the downstream task "
                    f"{mode}. Return JSON only, with concise values and no Markdown. "
                    "Keep the JSON under 1200 characters."
                ),
        },
        {"type": "text", "text": case.task_prompt},
        {"type": "text", "text": "Task image(s):"},
    ]
    for image_path in case.task_images:
        content.append(_image_part(image_path))

    if with_skill:
        skill_md = case.skill_text_override or (case.skill_dir / "skill.md").read_text(encoding="utf-8")
        content.extend(
            [
                {
                    "type": "text",
                    "text": (
                        "Generated AutoVisualSkill artifact: use this skill as the "
                        "operating procedure for the task. Visual-prior images are "
                        "references from a separate source example only; never treat "
                        "them as the current task image or an answer key. Return "
                        "coordinates in the task image, not in any reference image."
                    ),
                },
                {"type": "text", "text": skill_md[:12000]},
            ]
        )
        if case.skill_images:
            content.append(
                {
                    "type": "text",
                    "text": "Generated visual-skill prior or protocol reference(s) from a different source example:",
                }
            )
            for image_path in case.skill_images:
                content.append(_image_part(image_path))
        if case.runtime_images:
            content.append(
                {
                    "type": "text",
                    "text": (
                        "Runtime visual state generated on the current task image by "
                        "executing the dynamic visual skill. Use this as visible "
                        "working state, not as a separate source example."
                    ),
                }
            )
            for image_path in case.runtime_images:
                content.append(_image_part(image_path))

    if case.expected and os.environ.get("AUTOVISUALSKILL_INCLUDE_EXPECTED_IN_PROMPT") == "1":
        content.append(
            {
                "type": "text",
                "text": (
                    "For reproducibility, do not optimize for the expected answer; "
                    f"use visual evidence. Human check target: {case.expected}"
                ),
            }
        )
    return [{"role": "user", "content": content}]


def _extract_json(raw: str) -> Any:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    candidates = [fence.group(1).strip()] if fence else []
    candidates.append(text)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _call(client: Any, model: str, case: Case, *, with_skill: bool) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=_case_messages(case, with_skill=with_skill),
                temperature=0,
                max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "4096")),
            )
            break
        except Exception as exc:
            last_exc = exc
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError("unreachable retry state") from last_exc
    raw = resp.choices[0].message.content or ""
    return {
        "raw": raw,
        "parsed": _extract_json(raw),
        "usage": getattr(resp, "usage", None).model_dump() if getattr(resp, "usage", None) else None,
    }


def main() -> int:
    from openai import OpenAI

    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("LLM_API_KEY or OPENAI_API_KEY must be set.")

    base_url = os.environ.get("LLM_BASE_URL") or None
    model = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=float(os.environ.get("LLM_TIMEOUT", "120")))

    results: dict[str, Any] = {
        "model": model,
        "base_url": base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "credential_note": "API credentials are supplied through environment variables and are not stored.",
        "cases": {},
    }
    if RESULTS_PATH.exists():
        existing = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        results["cases"].update(existing.get("cases", {}))

    only_raw = os.environ.get("AUTOVISUALSKILL_EVAL_CASES", "").strip()
    only = {item.strip() for item in only_raw.split(",") if item.strip()}
    for case in _cases():
        if only and case.key not in only:
            continue
        print(f"running {case.key}: without skill")
        without_skill = _call(client, model, case, with_skill=False)
        print(f"running {case.key}: with skill")
        with_skill = _call(client, model, case, with_skill=True)
        results["cases"][case.key] = {
            "title": case.title,
            "task_prompt": case.task_prompt,
            "expected": case.expected,
            "task_images": [str(p.relative_to(ROOT)) for p in case.task_images],
            "skill_dir": str(case.skill_dir.relative_to(ROOT)),
            "skill_images": [str(p.relative_to(ROOT)) for p in case.skill_images],
            "runtime_images": [str(p.relative_to(ROOT)) for p in case.runtime_images],
            "without_skill": without_skill,
            "with_skill": with_skill,
        }
        EVAL_ROOT.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"saved {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
