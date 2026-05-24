"""Render the ARC-AGI route-state showcase from the official ls20 environment.

This optional helper requires the public `arc_agi` package and downloaded
environment files. It renders a side-by-side animation: the direct Gemini branch
takes the recorded wrong action, while the visual-skill branch follows the
corrected action and then plays the official remaining route so the full
route-state effect is visible.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from arc_agi import Arcade, OperationMode
from arc_agi.rendering import frame_to_rgb_array
from arcengine import GameAction


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "assets"
VIDEOS = DOCS / "videos"
CASE = ROOT / "examples" / "curated_skills" / "open_source_homepage_regenerated" / "12_arc_agi_route_planning"
ASSETS = CASE / "assets"

ENV_DIR = Path("/tmp/arc_env_files")
RECORDINGS_DIR = Path("/tmp/arc_recordings")
GAME_ID = "ls20"

ACTION_NAMES = {1: "up", 2: "down", 3: "left", 4: "right"}
OFFICIAL_ROUTE = [3, 3, 3, 1, 1, 1, 1, 4, 4, 4, 1, 1, 1]
SCREENED_PREFIX = [3, 3, 3, 1]
DIRECT_WRONG_ACTION = 2
SKILL_CORRECT_ACTION = 1

W, H = 1720, 1060
PAPER = "#f8fafc"
INK = "#172033"
MUTED = "#64748b"
LINE = "#cbd5e1"
BLUE = "#2563eb"
GREEN = "#10b981"
RED = "#ef4444"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(38, True)
F_PANEL = font(30, True)
F_BODY = font(24)
F_SMALL = font(20)


def setup_arc() -> Arcade:
    logger = logging.getLogger("arc_route_demo")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(ENV_DIR),
        recordings_dir=str(RECORDINGS_DIR),
        logger=logger,
    )


def observation_after(prefix: list[int]):
    arc = setup_arc()
    env = arc.make(GAME_ID, seed=0)
    obs = env.observation_space
    for action in prefix:
        obs = env.step(getattr(GameAction, f"ACTION{action}"))
    return obs


def frame_image(prefix: list[int]) -> Image.Image:
    obs = observation_after(prefix)
    return Image.fromarray(frame_to_rgb_array(0, obs.frame[0], scale=12)).convert("RGB")


def object_center_from_obs(obs) -> tuple[int, int] | None:
    arr = obs.frame[0]
    orange: list[tuple[int, int]] = []
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            if int(arr[y, x]) == 9 and 5 < y < 58 and 5 < x < 58:
                orange.append((x, y))
    if not orange:
        return None
    return round(sum(x for x, _ in orange) / len(orange)), round(sum(y for _, y in orange) / len(orange))


def object_center(prefix: list[int]) -> tuple[int, int] | None:
    return object_center_from_obs(observation_after(prefix))


def white_target_center(obs) -> tuple[int, int] | None:
    arr = obs.frame[0]
    points: set[tuple[int, int]] = set()
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            if int(arr[y, x]) in {0, 14} and 5 < y < 58 and 5 < x < 58:
                points.add((x, y))
    if not points:
        return None
    seen: set[tuple[int, int]] = set()
    comps: list[list[tuple[int, int]]] = []
    for point in points:
        if point in seen:
            continue
        stack = [point]
        seen.add(point)
        comp: list[tuple[int, int]] = []
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nb in points and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if 2 <= len(comp) <= 40:
            comps.append(comp)
    if not comps:
        return None
    comp = max(comps, key=len)
    return round(sum(x for x, _ in comp) / len(comp)), round(sum(y for _, y in comp) / len(comp))


def scale_point(point: tuple[int, int], scale: float) -> tuple[int, int]:
    return int((point[0] + 0.5) * scale), int((point[1] + 0.5) * scale)


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    import math

    sx, sy = start
    ex, ey = end
    draw.line([sx, sy, ex, ey], fill=color, width=10)
    angle = math.atan2(ey - sy, ex - sx)
    head = 28
    left = (ex - head * math.cos(angle - 0.55), ey - head * math.sin(angle - 0.55))
    right = (ex - head * math.cos(angle + 0.55), ey - head * math.sin(angle + 0.55))
    draw.polygon([left, (ex, ey), right], fill=color)


def draw_action_marker(src: Image.Image, prefix_before_action: list[int], action: int, color: str) -> Image.Image:
    out = src.copy().convert("RGBA")
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    center = object_center(prefix_before_action)
    if not center:
        return src
    scale = src.width / 64
    x, y = scale_point(center, scale)
    draw.ellipse([x - 34, y - 34, x + 34, y + 34], outline=color, width=7)
    deltas = {
        1: (0, -115),
        2: (0, 115),
        3: (-115, 0),
        4: (115, 0),
    }
    dx, dy = deltas[action]
    draw_arrow(draw, (x, y), (x + dx, y + dy), color)
    return Image.alpha_composite(out, layer).convert("RGB")


def route_overlay(prefix: list[int]) -> Image.Image:
    raw = frame_image(prefix)
    obs = observation_after(prefix)
    out = raw.copy().convert("RGBA")
    layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    scale = raw.width / 64

    for k in range(0, 65, 8):
        pos = int(k * scale)
        draw.line([pos, 0, pos, raw.height], fill=(255, 255, 255, 42), width=1)
        draw.line([0, pos, raw.width, pos], fill=(255, 255, 255, 42), width=1)

    centers: list[tuple[int, int]] = []
    for i in range(len(prefix) + 1):
        c = object_center(prefix[:i])
        if c:
            centers.append(c)
    if len(centers) >= 2:
        pts = [scale_point(c, scale) for c in centers]
        draw.line(pts, fill=(16, 185, 129, 230), width=6)
        for px, py in pts[:-1]:
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(16, 185, 129, 255))

    current = object_center_from_obs(obs)
    if current:
        x, y = scale_point(current, scale)
        draw.rounded_rectangle([x - 28, y - 28, x + 28, y + 28], radius=8, outline=(16, 185, 129, 255), width=5)
        draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(16, 185, 129, 255))

    target = white_target_center(obs)
    if target:
        x, y = scale_point(target, scale)
        draw.ellipse([x - 24, y - 24, x + 24, y + 24], outline=(255, 255, 255, 240), width=5)

    return Image.alpha_composite(out, layer).convert("RGB")


def fit_image(img: Image.Image, size: tuple[int, int], bg: str = "white") -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, bg)
    out.paste(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return out


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, ink: str) -> None:
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=F_PANEL)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.rounded_rectangle([x, y, x + w + 34, y + h + 18], radius=22, fill=fill)
    draw.text((x + 17, y + 9), text, font=F_PANEL, fill=ink)


def comparison_frame(
    left_img: Image.Image,
    right_img: Image.Image,
    *,
    title: str,
    subtitle: str,
    left_note: str,
    right_note: str,
    footer: str = "",
) -> Image.Image:
    canvas = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.text((54, 42), title, font=F_TITLE, fill=INK)
    draw.text((54, 92), subtitle, font=F_BODY, fill=MUTED)
    draw.line([54, 150, W - 54, 150], fill=LINE, width=2)

    panel_w = 790
    panel_h = 800
    panel_y = 190
    gap = 70
    panels = [
        (54, "Without visual skill", left_note, left_img, BLUE, "#eff6ff"),
        (54 + panel_w + gap, "With visual skill", right_note, right_img, GREEN, "#ecfdf5"),
    ]
    for x, panel_title, note, img, color, bg in panels:
        draw.rounded_rectangle([x, panel_y, x + panel_w, panel_y + panel_h], radius=24, fill="white", outline=LINE, width=2)
        pill(draw, (x + 26, panel_y + 26), panel_title, bg, color)
        draw.text((x + 30, panel_y + 88), note, font=F_SMALL, fill=MUTED)
        frame = [x + 26, panel_y + 132, x + panel_w - 26, panel_y + panel_h - 48]
        draw.rounded_rectangle(frame, radius=18, fill="white", outline="#e2e8f0", width=2)
        fitted = fit_image(img, (panel_w - 70, panel_h - 200), "white")
        canvas.paste(fitted, (x + 35 + (panel_w - 70 - fitted.width) // 2, panel_y + 146 + (panel_h - 200 - fitted.height) // 2))

    if footer:
        draw.text((54, H - 42), footer, font=F_SMALL, fill=INK)
    return canvas


def write_gif(path: Path, frames: list[Image.Image], durations: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    paletted = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    paletted[0].save(
        path,
        save_all=True,
        append_images=paletted[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    VIDEOS.mkdir(parents=True, exist_ok=True)

    decision_raw = frame_image(SCREENED_PREFIX)
    decision_overlay = route_overlay(SCREENED_PREFIX)
    decision_raw.save(ASSETS / "arc_ls20_source_frame.png")
    decision_overlay.save(ASSETS / "arc_ls20_route_state_overlay.png")

    wrong_prefix = SCREENED_PREFIX + [DIRECT_WRONG_ACTION]
    final_prefix = OFFICIAL_ROUTE
    wrong_final = draw_action_marker(frame_image(wrong_prefix), SCREENED_PREFIX, DIRECT_WRONG_ACTION, BLUE)
    skill_final_overlay = route_overlay(final_prefix)
    skill_final_overlay.save(DOCS / "demo_arc_agi_route_trace.png")

    final = comparison_frame(
        wrong_final,
        skill_final_overlay,
        title="ARC-AGI route-state planning",
        subtitle="Same official LS20 episode: direct takes the wrong branch; visual skill follows the full route.",
        left_note="Gemini direct chose ACTION2 / down",
        right_note="visual-skill branch follows ACTION1 / up, then the official route",
        footer="Official route from start: left, left, left, up, up, up, up, right, right, right, up, up, up.",
    )
    final.save(DOCS / "demo_arc_agi_route_comparison.png")
    final.save(ASSETS / "arc_ls20_runtime_trace.png")

    frames: list[Image.Image] = []
    durations: list[int] = []

    def add(left: Image.Image, right: Image.Image, subtitle: str, left_note: str, right_note: str, duration: int) -> None:
        frames.append(
            comparison_frame(
                left,
                right,
                title="ARC-AGI route-state planning",
                subtitle=subtitle,
                left_note=left_note,
                right_note=right_note,
                footer="Actions: ACTION1=up, ACTION2=down, ACTION3=left, ACTION4=right.",
            )
        )
        durations.append(duration)

    add(
        frame_image([]),
        route_overlay([]),
        "Both branches start from the same original LS20 frame.",
        "raw frame only",
        "route-state overlay initializes",
        850,
    )

    for i, action in enumerate(SCREENED_PREFIX, start=1):
        prefix = SCREENED_PREFIX[:i]
        add(
            frame_image(prefix),
            route_overlay(prefix),
            f"Shared prefix step {i}: ACTION{action} / {ACTION_NAMES[action]}.",
            "raw returned frame",
            "route history stays visible",
            620,
        )

    decision_left = draw_action_marker(frame_image(SCREENED_PREFIX), SCREENED_PREFIX, DIRECT_WRONG_ACTION, BLUE)
    decision_right = draw_action_marker(route_overlay(SCREENED_PREFIX), SCREENED_PREFIX, SKILL_CORRECT_ACTION, GREEN)
    add(
        decision_left,
        decision_right,
        "At the screened frame, the two branches diverge.",
        "direct chooses ACTION2 / down",
        "visual skill chooses ACTION1 / up",
        1200,
    )

    add(
        wrong_final,
        route_overlay(SCREENED_PREFIX + [SKILL_CORRECT_ACTION]),
        "The direct branch moves away from the waypoint; the visual branch continues upward.",
        "wrong branch after ACTION2",
        "correct branch after ACTION1",
        850,
    )

    for idx in range(len(SCREENED_PREFIX) + 2, len(OFFICIAL_ROUTE) + 1):
        prefix = OFFICIAL_ROUTE[:idx]
        action = prefix[-1]
        add(
            wrong_final,
            route_overlay(prefix),
            f"Visual-skill branch continues: ACTION{action} / {ACTION_NAMES[action]}.",
            "direct branch already off route",
            f"visible route state: {idx}/{len(OFFICIAL_ROUTE)} actions",
            520,
        )

    frames.append(final)
    durations.append(1400)
    frames.append(final)
    durations.append(800)

    write_gif(VIDEOS / "demo_arc_agi_route_visual_skill.gif", frames, durations)
    write_gif(ASSETS / "arc_ls20_route_state_demo.gif", frames, durations)
    print("Rendered ARC route demo:")
    print(f"- {VIDEOS / 'demo_arc_agi_route_visual_skill.gif'}")
    print(f"- {ASSETS / 'arc_ls20_route_state_demo.gif'}")


if __name__ == "__main__":
    main()
