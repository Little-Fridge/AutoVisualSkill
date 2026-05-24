"""Gradio demo for AutoVisualSkill.

Run from the repository root:

    python demo_gradio.py

Required environment variables for live generation:

    LLM_BASE_URL
    LLM_API_KEY
    LLM_MODEL_NAME

The demo can still render curated examples without API credentials.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent


def _import_gradio_package():
    """Import the external gradio package."""
    original_path = list(sys.path)
    filtered_path: list[str] = []
    for entry in original_path:
        resolved = Path(entry or os.getcwd()).resolve()
        if resolved == THIS_DIR:
            continue
        filtered_path.append(entry)
    sys.path = filtered_path
    try:
        import gradio as gradio_package
    finally:
        sys.path = original_path
    return gradio_package


gr = _import_gradio_package()

from autovisualskill.main import run as run_autovisualskill


ROOT = THIS_DIR
EXAMPLE_ROOT = ROOT / "examples" / "curated_skills"
REGENERATED_ROOT = EXAMPLE_ROOT / "open_source_homepage_regenerated"
RUN_ROOT = ROOT / "skill_output" / "gradio_runs"
RUN_ROOT.mkdir(parents=True, exist_ok=True)


CSS = """
:root {
  --vs-ink: #172033;
  --vs-muted: #667085;
  --vs-panel: rgba(255, 255, 255, 0.78);
  --vs-line: rgba(27, 39, 64, 0.10);
  --vs-green: #087f5b;
  --vs-blue: #2563eb;
  --vs-amber: #b7791f;
  --vs-purple: #7c3aed;
}

.gradio-container {
  max-width: 1320px !important;
  background:
    radial-gradient(circle at 8% 8%, rgba(37, 99, 235, 0.12), transparent 30%),
    radial-gradient(circle at 88% 12%, rgba(8, 127, 91, 0.12), transparent 32%),
    linear-gradient(180deg, #f8fbff 0%, #f7f4ec 100%);
}

.hero {
  padding: 34px 34px 28px 34px;
  border: 1px solid var(--vs-line);
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.92), rgba(245,250,255,0.86)),
    linear-gradient(135deg, rgba(37,99,235,0.10), rgba(8,127,91,0.10));
  box-shadow: 0 24px 80px rgba(22, 34, 60, 0.10);
}

.hero h1 {
  font-size: 46px;
  line-height: 1.02;
  margin: 0 0 12px 0;
  letter-spacing: 0;
  color: var(--vs-ink);
}

.hero p {
  max-width: 900px;
  color: var(--vs-muted);
  font-size: 17px;
  line-height: 1.65;
  margin: 0;
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.pill {
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(27,39,64,0.12);
  color: #344054;
  font-size: 13px;
  font-weight: 650;
}

.section-title {
  margin: 26px 0 8px 0;
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.74);
  border: 1px solid var(--vs-line);
  color: var(--vs-ink);
}

.section-title h2 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0;
}

.section-title p {
  margin: 5px 0 0 0;
  color: var(--vs-muted);
}

.example-strip {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,0.70);
  border: 1px solid var(--vs-line);
  color: var(--vs-muted);
  font-size: 13px;
  line-height: 1.5;
}

.case-card {
  border-radius: 24px;
  border: 1px solid var(--vs-line);
  background: var(--vs-panel);
  box-shadow: 0 14px 50px rgba(16,24,40,0.07);
  padding: 16px;
}

.case-card h3 {
  margin-top: 0;
  color: var(--vs-ink);
  font-size: 20px;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  margin: 0 6px 8px 0;
  font-size: 12px;
  font-weight: 750;
  border: 1px solid rgba(0,0,0,0.08);
}

.badge.text { background: #eef2ff; color: #3730a3; }
.badge.static { background: #ecfdf5; color: #047857; }
.badge.dynamic { background: #fff7ed; color: #c2410c; }
.badge.interleaved { background: #f5f3ff; color: #6d28d9; }

.idea-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.idea-card {
  border-radius: 20px;
  padding: 15px;
  background: rgba(255,255,255,0.78);
  border: 1px solid var(--vs-line);
  box-shadow: 0 10px 36px rgba(16,24,40,0.055);
}

.idea-card h3 {
  margin: 0 0 7px 0;
  font-size: 17px;
  color: var(--vs-ink);
}

.idea-card p {
  margin: 6px 0;
  color: #475467;
  line-height: 1.45;
}

.idea-card code {
  white-space: normal;
  color: #0f766e;
}

.mini-flow {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 14px;
  border-radius: 18px;
  background: #fffaf0;
  border: 1px solid rgba(180, 120, 20, 0.20);
}

.flow-step {
  min-height: 110px;
  border-radius: 14px;
  background: white;
  border: 1px solid rgba(180, 120, 20, 0.18);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #304050;
  font-weight: 700;
}

.dots {
  display: flex;
  gap: 7px;
  margin-top: 12px;
}

.dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #34d399;
  border: 2px solid white;
  box-shadow: 0 0 0 1px rgba(8, 127, 91, 0.4);
}

.output-path {
  color: #475467;
  font-size: 12px;
  word-break: break-all;
}

textarea, .cm-editor {
  border-radius: 16px !important;
}
"""


CURATED_CASES = [
    {
        "key": "gui",
        "title": "Button click target",
        "badge": "static",
        "input_type": "Image input",
        "output_type": "Static visual skill",
        "path": REGENERATED_ROOT / "03_gui_icon_grounding",
        "prompt": "Generate a visual skill for a simple toolbar screenshot that marks the search button hitbox and click center.",
        "why": "Shows why the clickable button envelope is not the same thing as the small icon strokes.",
    },
    {
        "key": "table",
        "title": "Table cell intersection",
        "badge": "static",
        "input_type": "Image input",
        "output_type": "Static visual skill",
        "path": REGENERATED_ROOT / "04_table_cell_intersection",
        "prompt": "Generate a visual skill for a 4x4 table screenshot that marks the target row, target column, and intersection cell.",
        "why": "Turns row-column lookup into a visible 2D spatial operation.",
    },
    {
        "key": "chart",
        "title": "Bar chart projection",
        "badge": "static",
        "input_type": "Image input",
        "output_type": "Static visual skill",
        "path": REGENERATED_ROOT / "05_chart_projection",
        "prompt": "Generate a visual skill for a bar chart screenshot that marks the selected bar and projects its height to the y-axis.",
        "why": "On the held-out task, the direct model trusts a floating label; the visual skill makes it project the bar to the y-axis.",
    },
    {
        "key": "presentation",
        "title": "PPT critique-and-redraw",
        "badge": "dynamic",
        "input_type": "Real PPT application trace",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "13_presentation_style_redraw",
        "prompt": "Generate a visual skill for a slide-making agent that critiques a generic AI-looking draft directly on the slide, then guides a cleaner professional redraw.",
        "why": "Shows the agent-facing loop on a real public slide: input -> red region critique overlay -> region-linked redraw.",
    },
    {
        "key": "counting",
        "title": "Dynamic anchors for dense counting",
        "badge": "dynamic",
        "input_type": "Pure text input",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "02_dense_counting",
        "prompt": "Generate a visual skill for dense object counting with dynamic point anchors.",
        "why": "Chooses a dynamic prior: the runtime writes anchors back onto the task image as visual working memory.",
    },
    {
        "key": "lines",
        "title": "Incremental line tracing",
        "badge": "dynamic",
        "input_type": "Pure text input",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "06_connect_lines",
        "prompt": "Generate a visual skill for line tracing and endpoint matching that advances along visible segments and draws the trajectory back onto the image.",
        "why": "Externalizes continuous trajectory state so the model does not need to remember the traced path internally.",
    },
    {
        "key": "geometry",
        "title": "Geometry auxiliary-line construction",
        "badge": "dynamic",
        "input_type": "Synthetic geometry diagram",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "10_geometry_auxiliary_lines",
        "prompt": "Generate a visual skill for geometry problems that draws justified auxiliary lines, equal-length marks, and angle focus back onto the diagram.",
        "why": "Shows dynamic visual reasoning beyond counting: the runtime creates construction state that the next reasoning step can inspect.",
    },
    {
        "key": "different",
        "title": "Odd-one-out visual search",
        "badge": "dynamic",
        "input_type": "Pure text input",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "07_find_different",
        "prompt": "Generate a visual skill for finding the odd item among repeated candidates by marking checked candidates and the current hypothesis back onto the image.",
        "why": "Turns fine-grained comparison into a visible checked-candidate trajectory rather than a one-shot guess.",
    },
    {
        "key": "arc_route",
        "title": "ARC-AGI route-state planning",
        "badge": "dynamic",
        "input_type": "Interactive ARC-AGI frame",
        "output_type": "Dynamic visual skill",
        "path": REGENERATED_ROOT / "12_arc_agi_route_planning",
        "prompt": "Generate a dynamic visual skill for ARC-AGI-3 route-state planning that renders current object, visited route, waypoint, and next local plan onto each returned frame.",
        "why": "Animates the same ARC-AGI episode: the direct branch goes off-route at the split, while the route-state overlay keeps the visual-skill branch on the official route.",
    },
    {
        "key": "video_proof",
        "title": "Pythagorean video proof",
        "badge": "interleaved",
        "input_type": "Sampled video keyframes",
        "output_type": "Interleaved visual skill",
        "path": REGENERATED_ROOT / "09_pythagorean_visual_proof_video",
        "prompt": "Generate an interleaved visual skill from sampled keyframes of a short Pythagorean theorem visual proof.",
        "why": "Keeps each reasoning step next to the frame that grounds the triangle side, area rearrangement, or final equation.",
    },
    {
        "key": "url",
        "title": "Documentation to interleaved skill",
        "badge": "interleaved",
        "input_type": "Documentation URL input",
        "output_type": "Interleaved visual skill",
        "path": REGENERATED_ROOT / "08_vscode_remote_ssh_url",
        "prompt": "Read the VS Code Remote-SSH documentation and generate an interleaved visual skill for connecting to a remote host.",
        "why": "Binds each procedural step to the source screenshot or diagram that visually grounds it.",
    },
    {
        "key": "colleague",
        "title": "Visual colleague skill",
        "badge": "interleaved",
        "input_type": "Multimodal chat input",
        "output_type": "Interleaved visual skill",
        "path": REGENERATED_ROOT / "11_visual_colleague_skill",
        "prompt": "Generate an interleaved visual skill from multimodal chat history that captures how a colleague critiques slides, marks local visual problems, and redraws AI-looking layouts.",
        "why": "Shows that interleaved skills are not only tutorials: reusable visual style rules stay bound to the chat attachments that demonstrate them.",
    },
]


STATIC_PREVIEW_ASSETS = {
    "gui": ROOT / "docs" / "assets" / "demo_gui_hitbox_prior.png",
}


COMPARISON_PREVIEW_ASSETS = {
    "table": ROOT / "docs" / "assets" / "demo_table_intersection_comparison.png",
    "chart": ROOT / "docs" / "assets" / "demo_chart_projection_comparison.png",
    "presentation": ROOT / "docs" / "assets" / "demo_presentation_redraw_trace.png",
}


DYNAMIC_PREVIEW_ASSETS = {
    "counting": ROOT / "docs" / "assets" / "demo_counting_trace.png",
    "lines": ROOT / "docs" / "assets" / "demo_line_tracing_trace.png",
    "geometry": ROOT / "docs" / "assets" / "demo_geometry_auxiliary_trace.png",
    "different": ROOT / "docs" / "assets" / "demo_odd_one_out_trace.png",
    "arc_route": ROOT / "docs" / "assets" / "demo_arc_agi_route_comparison.png",
}


INTERLEAVED_PREVIEW_ASSETS = {
    "video_proof": ROOT / "docs" / "assets" / "demo_pythagorean_interleaved_effect.png",
    "url": ROOT / "docs" / "assets" / "demo_vscode_interleaved_effect.png",
    "colleague": ROOT / "docs" / "assets" / "demo_visual_colleague_interleaved_effect.png",
}


EXAMPLE_INPUTS = [
    [
        "Generate a GUI grounding visual skill for small icon buttons, toolbar buttons, and action icons nested inside cards.",
        "",
        False,
    ],
    [
        "Generate a visual skill for a slide-making agent that critiques a generic AI-looking draft directly on the slide, then guides a cleaner professional redraw.",
        "",
        False,
    ],
    [
        "Generate a visual skill for dense object counting with dynamic point anchors.",
        "",
        False,
    ],
    [
        "Read this documentation page and generate an interleaved visual skill for connecting VS Code to a remote host over SSH.",
        "https://code.visualstudio.com/docs/remote/ssh",
        False,
    ],
    [
        "Generate a visual skill for geometry problems that draws justified auxiliary lines and relation marks back onto the diagram.",
        "",
        False,
    ],
]


VISUAL_PRIOR_IDEAS = [
    {
        "title": "GUI Hitbox Priority",
        "kind": "static",
        "prompt": "Generate a GUI grounding visual skill that resolves glyph ink, clickable hitbox, nested child controls, and sibling exclusion zones.",
        "prior": "A priority map showing wrong glyph centroid, target hitbox envelope, nested child precedence, neighboring exclusion regions, and click center.",
        "why": "The useful signal is boundary and precedence geometry, not a prose reminder to click the icon.",
    },
    {
        "title": "PPT Critique-and-Redraw",
        "kind": "dynamic",
        "prompt": "Generate a visual skill for a slide-making agent that critiques a generic AI-looking draft directly on the slide, then guides a cleaner professional redraw.",
        "prior": "Runtime draws hierarchy, clutter, default-shape, diagram, and footer critique regions directly onto the slide.",
        "why": "Slide polish is visual and spatial; the critique overlay gives a redraw agent concrete layout state rather than vague taste words.",
    },
    {
        "title": "Find the Different",
        "kind": "dynamic",
        "prompt": "Generate a visual skill for find-the-different tasks that compares candidate regions incrementally and marks checked regions back onto the image.",
        "prior": "Runtime marks each checked tile with a neutral check dot and marks the current comparison pair with linked outlines; no answer-like template.",
        "why": "Dynamic marks externalize comparison state, preventing the model from rechecking the same candidate or skipping one.",
    },
    {
        "title": "Connect the Lines",
        "kind": "dynamic",
        "prompt": "Generate a visual skill for line tracing and endpoint matching that advances along visible segments and draws the trajectory back onto the image.",
        "prior": "Runtime draws the traced segment, current endpoint, and unresolved branches on the task image after each step.",
        "why": "The bottleneck is continuous visual tracking; a dynamic trajectory is more useful than a static instruction sheet.",
    },
    {
        "title": "Geometry Auxiliary Lines",
        "kind": "dynamic",
        "prompt": "Generate a visual skill for geometry problems that draws justified auxiliary lines and relation marks back onto the diagram.",
        "prior": "Runtime draws one accepted construction at a time, plus compact equality and angle-focus marks on the original geometry diagram.",
        "why": "The intermediate construction is the reasoning state; making it visible helps the next step inspect the actual diagram.",
    },
    {
        "title": "Shadow / Object Matching",
        "kind": "static",
        "prompt": "Generate a visual skill for matching objects to shadows, icons to silhouettes, or parts to slots.",
        "prior": "Separated source and target sets connected by shape-envelope matching lines; show rotation/scale tolerance with ghost outlines, not words.",
        "why": "The reusable protocol is one-to-one spatial matching under transformation, which is naturally visual.",
    },
]


THEME = gr.themes.Soft(
    primary_hue="emerald",
    secondary_hue="blue",
    neutral_hue="slate",
    font=["Avenir Next", "Segoe UI", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=["SFMono-Regular", "Menlo", "Consolas", "ui-monospace", "monospace"],
)


def _safe_read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def _load_manifest(case_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _section(text: str, title: str, max_chars: int = 900) -> str:
    pattern = rf"## {re.escape(title)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return text[:max_chars].strip()
    body = match.group(1).strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 3].rstrip() + "..."


def _first_asset(case_dir: Path) -> str | None:
    assets_dir = case_dir / "assets"
    if not assets_dir.exists():
        return None
    for path in sorted(assets_dir.iterdir()):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return str(path)
    return None


def _preview_asset(case: dict[str, Any]) -> str | None:
    explicit_preview = case.get("preview_asset")
    if explicit_preview and explicit_preview.exists():
        return str(explicit_preview)
    static_preview = STATIC_PREVIEW_ASSETS.get(case["key"])
    if static_preview and static_preview.exists():
        return str(static_preview)
    comparison_preview = COMPARISON_PREVIEW_ASSETS.get(case["key"])
    if comparison_preview and comparison_preview.exists():
        return str(comparison_preview)
    runtime_trace = DYNAMIC_PREVIEW_ASSETS.get(case["key"])
    if runtime_trace and runtime_trace.exists():
        return str(runtime_trace)
    interleaved_preview = INTERLEAVED_PREVIEW_ASSETS.get(case["key"])
    if interleaved_preview and interleaved_preview.exists():
        return str(interleaved_preview)
    return _first_asset(case["path"])


def _badge_html(kind: str) -> str:
    label = {
        "static": "static visual prior",
        "dynamic": "dynamic visual prior",
        "interleaved": "interleaved visual skill",
    }.get(kind, kind)
    return f'<span class="badge {kind}">{label}</span>'


def _case_intro(case: dict[str, Any]) -> str:
    manifest = _load_manifest(case["path"])
    skill = _safe_read(case["path"] / "skill.md")
    description = _section(skill, "Description", 560)
    prior_kind = manifest.get("prior_kind", "unknown")
    skill_type = manifest.get("skill_type", "unknown")
    visual_skill_kind = manifest.get("visual_skill_kind") or case["badge"]
    bottleneck = manifest.get("bottleneck", "none")
    return f"""
<div class="case-card">
  <h3>{case['title']}</h3>
  {_badge_html(case['badge'])}
  <span class="badge text">{skill_type}</span>
  <span class="badge text">{visual_skill_kind}</span>
  <p><b>Input:</b> {case['input_type']}<br>
     <b>Output:</b> {case['output_type']}<br>
     <b>Prior:</b> {prior_kind}; <b>Bottleneck:</b> {bottleneck}</p>
  <p><b>Example request</b><br><code>{case['prompt']}</code></p>
  <p><b>Generated description</b><br>{description}</p>
  <p><b>Why it works</b><br>{case['why']}</p>
  <p class="output-path">{case['path']}</p>
</div>
"""


def _dynamic_flow_html() -> str:
    return """
<div class="mini-flow">
  <div class="flow-step">Original<div class="dots"><span class="dot"></span><span class="dot"></span></div></div>
  <div class="flow-step">Mark new<div class="dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
  <div class="flow-step">Feedback<div class="dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
  <div class="flow-step">Stop<div class="dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
</div>
"""


def _idea_bank_html() -> str:
    cards = []
    for idea in VISUAL_PRIOR_IDEAS:
        cards.append(
            f"""
<div class="idea-card">
  <h3>{idea['title']}</h3>
  {_badge_html(idea['kind'])}
  <p><b>Example request</b><br><code>{idea['prompt']}</code></p>
  <p><b>Visual prior should encode</b><br>{idea['prior']}</p>
  <p><b>Why it is promising</b><br>{idea['why']}</p>
</div>
"""
        )
    return '<div class="idea-grid">' + "\n".join(cards) + "</div>"


def _paths_from_uploads(uploaded_files: list[Any] | None) -> list[str]:
    paths: list[str] = []
    for item in uploaded_files or []:
        path = getattr(item, "name", None) or item
        if path:
            paths.append(str(path))
    return paths


def _paths_from_urls(urls: str) -> list[str]:
    return [line.strip() for line in (urls or "").splitlines() if line.strip()]


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", text.strip())
    text = text.strip("_") or "skill"
    return text[:40]


def generate_skill(
    user_goal: str,
    urls: str,
    enable_web_research: bool,
    uploaded_files: list[Any] | None,
    api_key: str | None,
) -> tuple[str, str, dict[str, Any], list[str]]:
    if not user_goal.strip():
        return "Please enter a goal.", "", {}, []

    previous_api_key = os.environ.get("LLM_API_KEY")
    if api_key and api_key.strip():
        os.environ["LLM_API_KEY"] = api_key.strip()

    if not os.environ.get("LLM_API_KEY"):
        return (
            "No API key provided. The curated gallery still works; enter an API key to run live generation.",
            "",
            {},
            [],
        )

    input_files = _paths_from_urls(urls) + _paths_from_uploads(uploaded_files)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + _slug(user_goal)
    out_dir = RUN_ROOT / run_id

    try:
        result = run_autovisualskill(
            user_goal=user_goal,
            input_files=input_files,
            output_dir=str(out_dir),
            enable_web_research=enable_web_research,
            max_video_frames=12,
            max_images_to_llm=4,
        )
    except Exception as exc:
        return f"Generation failed:\n\n{type(exc).__name__}: {exc}", str(out_dir), {}, []
    finally:
        if api_key and api_key.strip():
            if previous_api_key is None:
                os.environ.pop("LLM_API_KEY", None)
            else:
                os.environ["LLM_API_KEY"] = previous_api_key

    skill_md = _safe_read(out_dir / "skill.md", "No skill.md was produced.")
    manifest = _load_manifest(out_dir)
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    assets = []
    assets_dir = out_dir / "assets"
    if assets_dir.exists():
        assets = [
            str(path)
            for path in sorted(assets_dir.iterdir())
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]

    status = f"Output directory: {out_dir}\n\nErrors: {errors}\nWarnings: {warnings}"
    return skill_md, status, manifest, assets


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="AutoVisualSkill Visual Skill Factory", analytics_enabled=False) as demo:
        gr.HTML(
            """
<div class="hero">
  <h1>AutoVisualSkill: turn context into reusable visual skills.</h1>
  <p>
    AutoVisualSkill reads text, images, accessible URLs, documents, multimodal chat evidence, or sampled video frames and packages them into structured visual-skill artifacts:
    declarative logic, visual priors, binding protocols, runtime protocols, constraints, and manifest metadata.
    Use it as a skill factory; plug the generated artifact into your own multimodal agent runtime.
  </p>
  <div class="pill-row">
    <span class="pill">static visual priors</span>
    <span class="pill">dynamic visual priors</span>
    <span class="pill">interleaved visual skills</span>
  </div>
</div>
"""
        )

        with gr.Tab("Generate"):
            gr.HTML(
                """
<div class="section-title">
  <h2>Try the skill factory</h2>
  <p>Enter a goal, optionally add text/image/document/video files or URLs, then generate a packaged skill artifact.</p>
</div>
"""
            )
            with gr.Row():
                with gr.Column(scale=5):
                    goal = gr.Textbox(
                        label="User goal",
                        lines=7,
                        placeholder="Example: Generate a visual skill for dense object counting with dynamic point anchors.",
                    )
                    urls = gr.Textbox(
                        label="Optional URLs, one per line",
                        lines=3,
                        placeholder="https://www.w3.org/WAI/tutorials/forms/labels/",
                    )
                    uploaded = gr.File(label="Optional text/image/document/video files", file_count="multiple")
                    api_key = gr.Textbox(
                        label="API key for live generation",
                        type="password",
                        placeholder="Optional: paste a key only when you want to run generation.",
                    )
                    enable_web = gr.Checkbox(label="Enable web research", value=False)
                    submit = gr.Button("Generate skill", variant="primary")
                    gr.HTML(
                        """
<div class="example-strip">
  <strong>Try:</strong>
  icon-grounding visual skill · dense-counting dynamic skill · interleaved multimodal skill
</div>
"""
                    )
                with gr.Column(scale=7):
                    status = gr.Textbox(label="Run status", lines=5)
                    manifest = gr.JSON(label="manifest.json")
                    assets = gr.Gallery(label="Generated visual priors", columns=2, height=300)
            skill = gr.Code(label="skill.md", language="markdown", lines=28)
            submit.click(
                generate_skill,
                inputs=[goal, urls, enable_web, uploaded, api_key],
                outputs=[skill, status, manifest, assets],
            )

        with gr.Tab("Curated examples"):
            gr.HTML(
                """
<div class="section-title">
  <h2>Curated homepage examples</h2>
  <p>Complete generated skill artifacts across static, dynamic, and interleaved visual-skill modes.</p>
</div>
"""
            )

            for case in CURATED_CASES:
                with gr.Row(equal_height=True):
                    with gr.Column(scale=5, elem_classes=["case-card"]):
                        gr.HTML(_case_intro(case))
                    with gr.Column(scale=4, elem_classes=["case-card"]):
                        asset = _preview_asset(case)
                        if asset:
                            if case["key"] in STATIC_PREVIEW_ASSETS:
                                label = "Visual prior"
                            elif case["key"] == "presentation":
                                label = "Runtime critique trace"
                            elif case["key"] in COMPARISON_PREVIEW_ASSETS:
                                label = "Task-solving output comparison"
                            elif case["key"] in DYNAMIC_PREVIEW_ASSETS:
                                label = "Runtime state trace"
                            elif case["key"] in INTERLEAVED_PREVIEW_ASSETS or case["badge"] == "interleaved":
                                label = "Interleaved visual reference"
                            else:
                                label = "Visual prior"
                            gr.Image(value=asset, label=label, show_label=True, height=360)
                        elif case["badge"] == "dynamic":
                            gr.HTML(_dynamic_flow_html())
                            gr.Markdown(
                                "Dynamic prior: no static image is cached. The runtime draws state directly on the task image after each iteration."
                            )
                        else:
                            skill_text = _safe_read(case["path"] / "skill.md")
                            gr.Code(value=_section(skill_text, "Output Format", 1000), language="markdown", label="Output schema")

        with gr.Tab("Artifact schema"):
            gr.HTML(
                """
<div class="section-title">
  <h2>What AutoVisualSkill produces</h2>
  <p>Every generated skill is a structured artifact, not just a prompt.</p>
</div>
"""
            )
            gr.Markdown(
                """
| Component | Purpose |
|---|---|
| `skill.md` | Human-readable and agent-readable instructions. |
| Declarative Textual Logic | The reusable semantic procedure. |
| Visual Priors | Static reference images or dynamic rendering protocols. |
| Interleaved Skill Kind | Ordered text bound to the visual evidence or references each step depends on. |
| Multimodal Binding Protocol | How text rules bind to images, coordinates, and task inputs. |
| Runtime Protocol | Single-turn vs iterative state updates, stop condition, renderer behavior. |
| Usage Constraints | Safety, anti-leakage, anti-template-copying rules. |
| Output Format | JSON/text schema expected from downstream execution. |
| `manifest.json` | Machine-readable metadata for routing, versioning, and packaging. |
"""
            )

    return demo


if __name__ == "__main__":
    app = build_demo()
    app.queue(default_concurrency_limit=2, api_open=False)
    app.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")),
        share=os.environ.get("GRADIO_SHARE", "0").lower() in {"1", "true", "yes"},
        footer_links=[],
        theme=THEME,
        css=CSS,
    )
