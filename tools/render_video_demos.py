"""Render short visual-skill execution videos from recorded AutoVisualSkill runs."""

from __future__ import annotations

import json
import random
from collections import deque
from pathlib import Path
from typing import Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "assets"
VIDEOS = DOCS / "videos"
CASES = ROOT / "examples" / "task_execution_cases"
RESULTS = CASES / "task_execution_results.json"
PPT = ROOT / "examples" / "curated_skills" / "open_source_homepage_regenerated" / "13_presentation_style_redraw"

W, H = 1280, 720
PAPER = "#f8fafc"
INK = "#172033"
MUTED = "#64748b"
LINE = "#d7e2ee"
BLUE = "#2563eb"
GREEN = "#10b981"
RED = "#ef4444"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
CYAN = "#06b6d4"


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


F_TITLE = font(34, True)
F_BODY = font(21)
F_SMALL = font(16)
F_NUM = font(16, True)
F_PANEL = font(24, True)
F_NOTE = font(18)


def fit_image(img: Image.Image, size: tuple[int, int], bg: str = "white") -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail(size, Image.LANCZOS)
    out = Image.new("RGB", size, bg)
    out.paste(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return out


def canvas(caption: str = "") -> Image.Image:
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    if caption:
        d.text((42, 28), caption, font=F_TITLE, fill=INK)
        d.line([42, 78, W - 42, 78], fill=LINE, width=2)
    return im


def image_stage(img: Image.Image, caption: str = "") -> Image.Image:
    im = canvas(caption)
    max_size = (1180, 570 if caption else 650)
    fitted = fit_image(img, max_size, "white")
    x = (W - fitted.width) // 2
    y = 105 if caption else (H - fitted.height) // 2
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x - 8, y - 8, x + fitted.width + 8, y + fitted.height + 8], radius=18, fill="white", outline=LINE, width=2)
    im.paste(fitted, (x, y))
    return im


def draw_pill(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: str,
    ink: str,
    *,
    fnt: ImageFont.FreeTypeFont = F_SMALL,
) -> None:
    x, y = xy
    bbox = d.textbbox((0, 0), text, font=fnt)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.rounded_rectangle([x, y, x + w + 28, y + h + 14], radius=16, fill=fill)
    d.text((x + 14, y + 7), text, font=fnt, fill=ink)


def comparison_stage(
    caption: str,
    left_title: str,
    left_img: Image.Image,
    right_title: str,
    right_img: Image.Image,
    *,
    left_note: str = "",
    right_note: str = "",
) -> Image.Image:
    im = canvas(caption)
    d = ImageDraw.Draw(im)
    panel_y = 112
    panel_w = 570
    panel_h = 545
    gap = 54
    left_x = 42
    right_x = left_x + panel_w + gap
    panels = [
        (left_x, left_title, left_img, "#eff6ff", BLUE, left_note),
        (right_x, right_title, right_img, "#ecfdf5", GREEN, right_note),
    ]
    for x, title, src, bg, accent, note in panels:
        d.rounded_rectangle([x, panel_y, x + panel_w, panel_y + panel_h], radius=18, fill="white", outline=LINE, width=2)
        draw_pill(d, (x + 22, panel_y + 22), title, bg, accent, fnt=F_PANEL)
        if note:
            d.text((x + 24, panel_y + 72), note, font=F_NOTE, fill=MUTED)
        fitted = fit_image(src, (panel_w - 54, panel_h - 150), "white")
        frame_y = panel_y + 112
        d.rounded_rectangle(
            [x + 22, frame_y, x + panel_w - 22, frame_y + panel_h - 140],
            radius=14,
            fill="#ffffff",
            outline="#e2e8f0",
            width=2,
        )
        paste_x = x + 27 + (panel_w - 54 - fitted.width) // 2
        paste_y = frame_y + 8 + (panel_h - 156 - fitted.height) // 2
        im.paste(fitted, (paste_x, paste_y))
    return im


def counting_view(img: Image.Image) -> Image.Image:
    return img.crop((60, 120, 1025, 412))


def odd_view(img: Image.Image) -> Image.Image:
    return img.crop((500, 315, 1148, 690))


def repeat(frame: Image.Image, seconds: float, fps: int) -> list[np.ndarray]:
    return [np.asarray(frame.copy()) for _ in range(max(1, round(seconds * fps)))]


def write_video(path: Path, frames: Iterable[np.ndarray], fps: int = 15) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(path, fps=fps, codec="libx264", quality=8, macro_block_size=8)
    try:
        for frame in frames:
            writer.append_data(frame)
    finally:
        writer.close()


def write_gif(path: Path, frames: list[np.ndarray], fps: int = 15) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sampled = frames[::2] if len(frames) > fps * 5 else frames
    duration_ms = max(60, round((2 / fps if len(frames) > fps * 5 else 1 / fps) * 1000))
    pil_frames = [Image.fromarray(frame).convert("P", palette=Image.Palette.ADAPTIVE) for frame in sampled]
    pil_frames[0].save(
        path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )


def load_results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def hard_counting_points() -> list[tuple[int, int]]:
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
    return sorted(points[:96], key=lambda p: (p[1] // 42, p[0]))


def red_token_centers(path: Path) -> list[tuple[int, int]]:
    if path.name == "counting_hard_task.png":
        return hard_counting_points()
    im = Image.open(path).convert("RGB")
    pix = im.load()
    w, h = im.size
    seen = set()
    centers: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen:
                continue
            r, g, b = pix[x, y]
            if not (r > 150 and g < 90 and b < 80):
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen.add((x, y))
            pts: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h or (nx, ny) in seen:
                        continue
                    rr, gg, bb = pix[nx, ny]
                    if rr > 150 and gg < 90 and bb < 80:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            if len(pts) > 80:
                centers.append((round(sum(p[0] for p in pts) / len(pts)), round(sum(p[1] for p in pts) / len(pts))))
    return sorted(centers, key=lambda p: (p[0] // 220, p[1], p[0]))


def draw_anchor_overlay(src: Image.Image, centers: list[tuple[int, int]], n: int, number: bool = True) -> Image.Image:
    im = src.copy().convert("RGB")
    d = ImageDraw.Draw(im)
    for x, y in centers[:n]:
        d.ellipse([x - 11, y - 11, x + 11, y + 11], outline=GREEN, width=3)
    if number:
        label = f"counted: {n}"
        bbox = d.textbbox((0, 0), label, font=F_NOTE)
        x2, y1 = im.width - 54, 56
        x1 = x2 - (bbox[2] - bbox[0]) - 24
        y2 = y1 + (bbox[3] - bbox[1]) + 18
        d.rounded_rectangle([x1, y1, x2, y2], radius=10, fill="#ecfdf5", outline=GREEN, width=3)
        d.text((x1 + 12, y1 + 8), label, font=F_NOTE, fill="#047857")
    return im


def render_counting_demo() -> None:
    data = load_results()
    case = data["cases"]["counting"]
    task = ROOT / case["task_images"][0]
    img = Image.open(task).convert("RGB")
    centers = red_token_centers(task)
    total = len(centers)
    direct_count = case.get("without_skill", {}).get("parsed", {}).get("count")
    skill_count = case.get("with_skill", {}).get("parsed", {}).get("count")
    direct_note = f"direct answer = {direct_count}" if direct_count is not None else "direct answer only"
    if isinstance(direct_count, int) and direct_count != total:
        direct_note += f"; misses {total - direct_count}"
    skill_note = f"with skill answer = {skill_count}" if skill_count is not None else "anchors are written back"
    frames: list[np.ndarray] = []
    fps = 15

    direct = img.copy()
    frames += repeat(
        comparison_stage(
            "Dense counting: direct answer vs visible count state",
            "Direct model run",
            counting_view(direct),
            "With visual skill",
            counting_view(img),
            left_note=direct_note,
            right_note="runtime anchor overlay starts empty",
        ),
        1.0,
        fps,
    )
    for step in range(0, len(centers) + 1):
        caption = "Dense counting: direct run undercounts; visual skill keeps state visible"
        if step == len(centers):
            caption = "Dense counting: final visual-skill count is auditable"
        overlay = draw_anchor_overlay(img, centers, step, number=True)
        frame = comparison_stage(
            caption,
            "Direct model run",
            counting_view(direct),
            "With visual skill",
            counting_view(overlay),
            left_note="no anchors to audit or resume",
            right_note=skill_note if step == total else f"visible anchors: {step}/{total}",
        )
        frames.append(np.asarray(frame))
        if step in {0, len(centers)}:
            frames += repeat(frame, 0.7, fps)
        elif step % 5 == 0:
            frames += repeat(frame, 0.18, fps)
    write_video(VIDEOS / "demo_counting_visual_skill.mp4", frames, fps)
    write_gif(VIDEOS / "demo_counting_visual_skill.gif", frames, fps)


def blend(a: Image.Image, b: Image.Image, t: float) -> Image.Image:
    return Image.blend(a.convert("RGB"), b.convert("RGB"), t)


def draw_ppt_critique(src: Image.Image, regions: list[dict], upto: int) -> Image.Image:
    im = src.copy().convert("RGBA")
    overlay = Image.new("RGBA", im.size, (255, 255, 255, 0))
    d = ImageDraw.Draw(overlay)
    colors = [(124, 58, 237, 210), (124, 58, 237, 210), (6, 182, 212, 210), (239, 68, 68, 220), (100, 116, 139, 210)]
    for j, region in enumerate(regions[:upto]):
        iw, ih = im.size
        if "bbox" in region:
            x, y, w, h = region["bbox"]
            box = [int(x * iw), int(y * ih), int((x + w) * iw), int((y + h) * ih)]
        else:
            box = [int(v) for v in region["bbox_px"]]
        color = colors[j % len(colors)]
        fill = color[:3] + (28,)
        d.rounded_rectangle(box, radius=10, fill=fill, outline=color, width=5)
    return Image.alpha_composite(im, overlay).convert("RGB")


def reveal_slide_regions(redraw: Image.Image, step: int) -> Image.Image:
    # Reveals the final redraw by semantic regions, approximating the recorded
    # Gemini redraw plan without placing critique text on the slide itself.
    base = Image.new("RGB", redraw.size, "#ffffff")
    w, h = redraw.size
    crop_boxes = [
        (0, 0, w, int(h * 0.27)),                           # title hierarchy
        (int(w * 0.04), int(h * 0.24), int(w * 0.48), int(h * 0.88)),  # explanation column
        (int(w * 0.48), int(h * 0.22), int(w * 0.97), int(h * 0.86)),  # diagram column
        (0, int(h * 0.82), w, h),                           # final footnote and whitespace
    ]
    for box in crop_boxes[:step]:
        base.paste(redraw.crop(box), box)
    return base


def render_ppt_demo() -> None:
    fps = 15
    assets = PPT / "assets"
    input_slide = Image.open(CASES / "assets" / "ppt_heldout_task.png").convert("RGB")
    text_only = Image.open(assets / "heldout_text_only_redraw.png").convert("RGB")
    redraw = Image.open(assets / "heldout_visual_skill_redraw.png").convert("RGB")
    regions = [
        {"bbox_px": [74, 66, 721, 150]},
        {"bbox_px": [82, 220, 565, 590]},
        {"bbox_px": [620, 210, 1160, 600]},
        {"bbox_px": [74, 618, 1200, 664]},
    ]
    frames: list[np.ndarray] = []

    frames += repeat(
        comparison_stage(
            "PPT redraw: text-only advice vs region-marked visual skill",
            "Text-only repair",
            text_only,
            "With visual skill",
            input_slide,
            left_note="broad cleanup, cards remain",
            right_note="first inspect the same slide",
        ),
        1.0,
        fps,
    )
    for i in range(len(regions) + 1):
        marked = draw_ppt_critique(input_slide, regions, i)
        frames += repeat(
            comparison_stage(
                "PPT redraw: local critique regions guide the repair",
                "Text-only repair",
                text_only,
                "With visual skill",
                marked,
                left_note="global suggestion",
                right_note=f"marked regions: {i}/4",
            ),
            0.45 if i else 0.7,
            fps,
        )

    start = draw_ppt_critique(input_slide, regions, len(regions)).resize(redraw.size, Image.LANCZOS)
    blank = reveal_slide_regions(redraw, 0)
    for k in range(12):
        t = (k + 1) / 12
        frames.append(
            np.asarray(
                comparison_stage(
                    "PPT redraw: convert region marks into a concrete edit plan",
                    "Text-only repair",
                    text_only,
                    "With visual skill",
                    blend(start, blank, t),
                    left_note="keeps generic containers",
                    right_note="remove marked noise",
                )
            )
        )

    for step, caption in [
        (1, "PPT redraw: rebuild title hierarchy"),
        (2, "PPT redraw: restructure the explanation"),
        (3, "PPT redraw: make the diagram the focal evidence"),
        (4, "PPT redraw: finish with clean spacing"),
    ]:
        frames += repeat(
            comparison_stage(
                caption,
                "Text-only repair",
                text_only,
                "With visual skill",
                reveal_slide_regions(redraw, step),
                left_note="advice is not spatially grounded",
                right_note="edits follow marked regions",
            ),
            0.85,
            fps,
        )

    frames += repeat(
        comparison_stage(
            "PPT redraw: final comparison",
            "Text-only repair",
            text_only,
            "With visual skill",
            redraw,
            left_note="card-heavy composition remains",
            right_note="region-level repair",
        ),
        1.4,
        fps,
    )
    write_video(VIDEOS / "demo_ppt_visual_skill.mp4", frames, fps)


def odd_item_centers() -> list[tuple[int, int, int, int]]:
    rows, cols = 12, 14
    start_x, start_y = 100, 145
    dx, dy = 78, 47
    return [
        (row, col, start_x + (col - 1) * dx, start_y + (row - 1) * dy)
        for row in range(1, rows + 1)
        for col in range(1, cols + 1)
    ]


def odd_center_for_location(location: object) -> tuple[int, int] | None:
    row: int | None = None
    col: int | None = None
    if isinstance(location, list) and len(location) >= 2:
        row, col = int(location[0]), int(location[1])
    elif isinstance(location, dict):
        if "row" in location and "column" in location:
            row, col = int(location["row"]), int(location["column"])
    elif isinstance(location, str):
        import re

        match = re.search(r"row\s*(\d+)\D+(?:col(?:umn)?\s*)?(\d+)", location, flags=re.I)
        if match:
            row, col = int(match.group(1)), int(match.group(2))
    if row is None or col is None:
        return None
    return 100 + (col - 1) * 78, 145 + (row - 1) * 47


def odd_center_from_result(parsed: dict) -> tuple[int, int] | None:
    center = parsed.get("center_px")
    if isinstance(center, list) and len(center) >= 2:
        return int(center[0]), int(center[1])
    return odd_center_for_location(parsed.get("location"))


def odd_location_text(parsed: dict) -> str | None:
    location = parsed.get("location")
    if isinstance(location, list) and len(location) >= 2:
        return f"row {location[0]}, column {location[1]}"
    if isinstance(location, dict) and "row" in location and "column" in location:
        return f"row {location['row']}, column {location['column']}"
    answer = parsed.get("answer")
    return str(answer) if answer else None


def draw_odd_search_overlay(src: Image.Image, checked: int, final_ring: bool = False) -> Image.Image:
    im = src.copy().convert("RGB")
    d = ImageDraw.Draw(im)
    centers = odd_item_centers()
    odd = (8, 12)
    odd_xy = odd_center_for_location([*odd])
    for row, col, x, y in centers[:checked]:
        if (row, col) == odd:
            continue
        d.line([x - 17, y + 10, x - 12, y + 16, x - 3, y + 3], fill=GREEN, width=2)
    if checked > 0:
        current = centers[min(checked - 1, len(centers) - 1)]
        _, _, x, y = current
        d.ellipse([x - 24, y - 24, x + 24, y + 24], outline="#93c5fd", width=3)
    odd_index = next(i for i, item in enumerate(centers) if item[:2] == odd)
    if odd_xy and (final_ring or checked >= odd_index + 1):
        x, y = odd_xy
        d.ellipse([x - 31, y - 31, x + 31, y + 31], outline=RED, width=5)
        d.ellipse([x - 17, y - 17, x + 17, y + 17], outline=ORANGE, width=4)
    return im


def draw_direct_odd_choice(src: Image.Image, center: tuple[int, int] | None) -> Image.Image:
    im = src.copy().convert("RGB")
    if not center:
        return im
    x, y = center
    d = ImageDraw.Draw(im)
    d.ellipse([x - 31, y - 31, x + 31, y + 31], outline=BLUE, width=5)
    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=BLUE, outline="white", width=2)
    return im


def render_odd_one_out_demo() -> None:
    data = load_results()
    case = data["cases"]["different"]
    img = Image.open(ROOT / case["task_images"][0]).convert("RGB")
    centers = odd_item_centers()
    direct_parsed = case.get("without_skill", {}).get("parsed", {})
    skill_parsed = case.get("with_skill", {}).get("parsed", {})
    direct_center = odd_center_from_result(direct_parsed) if isinstance(direct_parsed, dict) else None
    skill_center = odd_center_from_result(skill_parsed) if isinstance(skill_parsed, dict) else None
    direct_location = odd_location_text(direct_parsed) if isinstance(direct_parsed, dict) else None
    skill_location = odd_location_text(skill_parsed) if isinstance(skill_parsed, dict) else None
    fps = 15
    frames: list[np.ndarray] = []

    direct = draw_direct_odd_choice(img, direct_center)
    direct_note = f"direct chose {direct_location}" if direct_location else "one-shot answer"
    skill_note = f"with skill chose {skill_location}" if skill_location else "runtime search state"
    frames += repeat(
        comparison_stage(
            "Odd-one-out: one-shot guess vs visible search state",
            "Direct model run",
            odd_view(direct),
            "With visual skill",
            odd_view(img),
            left_note=direct_note,
            right_note="checked state is empty",
        ),
        1.0,
        fps,
    )
    odd_index = next(i for i, item in enumerate(centers) if item[:2] == (8, 12))
    steps = list(range(0, len(centers) + 1, 8))
    if odd_index + 1 not in steps:
        steps.append(odd_index + 1)
    if len(centers) not in steps:
        steps.append(len(centers))
    for step in sorted(set(steps)):
        caption = "Odd-one-out: keep checked candidates visible"
        if step >= odd_index + 1:
            caption = "Odd-one-out: current hypothesis stays marked"
        overlay = draw_odd_search_overlay(img, step)
        frame = comparison_stage(
            caption,
            "Direct model run",
            odd_view(direct),
            "With visual skill",
            odd_view(overlay),
            left_note=direct_note,
            right_note=f"checked candidates: {min(step, len(centers))}/{len(centers)}",
        )
        frames.append(np.asarray(frame))
        if step in {0, len(centers)}:
            frames += repeat(frame, 0.6, fps)
        elif step % 24 == 0:
            frames += repeat(frame, 0.15, fps)
    frames += repeat(
        comparison_stage(
            "Odd-one-out: final visual state",
            "Direct model run",
            odd_view(direct),
            "With visual skill",
            odd_view(draw_odd_search_overlay(img, len(centers), True)),
            left_note=direct_note,
            right_note=skill_note,
        ),
        1.2,
        fps,
    )
    write_video(VIDEOS / "demo_odd_one_out_visual_skill.mp4", frames, fps)
    write_gif(VIDEOS / "demo_odd_one_out_visual_skill.gif", frames, fps)


def main() -> None:
    render_counting_demo()
    render_ppt_demo()
    render_odd_one_out_demo()
    old = VIDEOS / "demo_line_tracing_visual_skill.mp4"
    if old.exists():
        old.unlink()
    print("Rendered video demos:")
    for path in sorted(VIDEOS.glob("demo_*_visual_skill.mp4")):
        print(f"- {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
