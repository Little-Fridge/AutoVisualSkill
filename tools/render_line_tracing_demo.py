#!/usr/bin/env python3
"""Render a concrete line-tracing dynamic-prior demo image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "demo_line_tracing_trace.png"

CANVAS_W = 1088
CANVAS_H = 454
PANEL_W = 520
PANEL_H = 420
MARGIN = 16

BOARD_X = 28
BOARD_Y = 74
BOARD_W = 464
BOARD_H = 330

NODES = {
    "A": (70, 70),
    "P1": (70, 210),
    "P2": (205, 70),
    "P3": (320, 135),
    "P4": (320, 210),
    "P5": (185, 285),
    "B": (395, 285),
    "R1": (395, 70),
    "R2": (430, 210),
    "D1": (185, 320),
    "D2": (320, 320),
}

EDGES = [
    ("A", "P1"),
    ("A", "P2"),
    ("P2", "P3"),
    ("P3", "P4"),
    ("P4", "P1"),
    ("P4", "P5"),
    ("P5", "B"),
    ("P2", "R1"),
    ("R1", "R2"),
    ("R2", "P4"),
    ("P5", "D1"),
    ("D1", "D2"),
]

TRACE_PATH = ["A", "P2", "P3", "P4", "P5", "B"]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE = _font(26, bold=True)
SUBTITLE = _font(15)
LABEL = _font(13, bold=True)
SMALL = _font(12, bold=True)


def _pt(name: str, offset_x: int, offset_y: int) -> tuple[int, int]:
    x, y = NODES[name]
    return offset_x + BOARD_X + x, offset_y + BOARD_Y + y


def _draw_panel_base(draw: ImageDraw.ImageDraw, offset_x: int, offset_y: int, title: str, subtitle: str) -> None:
    panel = [offset_x, offset_y, offset_x + PANEL_W, offset_y + PANEL_H]
    draw.rectangle(panel, fill="#ffffff", outline="#d9dee8", width=2)
    draw.text((offset_x + 12, offset_y + 8), title, fill="#1f2937", font=TITLE)
    draw.text((offset_x + 13, offset_y + 38), subtitle, fill="#4b5563", font=SUBTITLE)

    board = [
        offset_x + BOARD_X,
        offset_y + BOARD_Y,
        offset_x + BOARD_X + BOARD_W,
        offset_y + BOARD_Y + BOARD_H,
    ]
    draw.rounded_rectangle(board, radius=18, fill="#fbfcff", outline="#cfd7e6", width=2)

    for a, b in EDGES:
        draw.line([_pt(a, offset_x, offset_y), _pt(b, offset_x, offset_y)], fill="#c9ced7", width=8)
        draw.line([_pt(a, offset_x, offset_y), _pt(b, offset_x, offset_y)], fill="#edf0f4", width=4)

    for name in NODES:
        x, y = _pt(name, offset_x, offset_y)
        draw.ellipse((x - 17, y - 17, x + 17, y + 17), fill="#f8fafc", outline="#374151", width=2)

    for name, label in {"A": "A", "B": "B"}.items():
        x, y = _pt(name, offset_x, offset_y)
        draw.text((x - 5, y - 36), label, fill="#111827", font=LABEL)


def _draw_runtime_overlay(draw: ImageDraw.ImageDraw, offset_x: int, offset_y: int) -> None:
    # Accepted trajectory: this is the dynamic state rendered back onto the task image.
    trace_points = [_pt(name, offset_x, offset_y) for name in TRACE_PATH]
    for a, b in zip(trace_points, trace_points[1:]):
        draw.line([a, b], fill="#18a558", width=12)
        draw.line([a, b], fill="#20d477", width=6)

    for step, name in enumerate(TRACE_PATH, start=1):
        x, y = _pt(name, offset_x, offset_y)
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill="#20d477", outline="#087f3f", width=2)
        text = str(step)
        bbox = draw.textbbox((0, 0), text, font=SMALL)
        draw.text((x - (bbox[2] - bbox[0]) / 2, y - 8), text, fill="#052e16", font=SMALL)

    bx, by = _pt("B", offset_x, offset_y)
    draw.ellipse((bx - 24, by - 24, bx + 24, by + 24), outline="#dc2626", width=5)
    draw.ellipse((bx - 8, by - 8, bx + 8, by + 8), fill="#dc2626")


def render() -> None:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "#f6f8fb")
    draw = ImageDraw.Draw(img)

    _draw_panel_base(
        draw,
        MARGIN,
        MARGIN,
        "Original Image",
        "Trace the connected line from A to B.",
    )
    _draw_panel_base(
        draw,
        MARGIN + PANEL_W + 18,
        MARGIN,
        "Final Runtime Trace",
        "Confirmed trajectory and endpoint are visible.",
    )
    _draw_runtime_overlay(draw, MARGIN + PANEL_W + 18, MARGIN)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    render()
