# AutoVisualSkill Agent Guide

This file is for AI agents working in this repository. Keep it short and
current; detailed public-facing explanation belongs in `README.md` or
`docs/PROJECT_STATE.md`.

## Project Positioning

AutoVisualSkill is an open-source visual-skill generation system for multimodal
agents. The public story is not "text-only skill generation"; the homepage and
demo should emphasize reusable visual protocols:

- `static`: stable visual priors for spatial conventions.
- `dynamic`: runtime visual state rendered back onto the task image.
- `interleaved`: text steps or style/workflow rules bound to visual evidence.

Keep `prior_kind` as the lower-level execution mechanism:
`none`, `static`, or `dynamic`. Keep `visual_skill_kind` as the user-facing
taxonomy: `text`, `static`, `dynamic`, or `interleaved`.

## Hard Rules

- Repository-facing text must be English.
- Do not reintroduce `AUTOSKILL_*` environment-variable compatibility. The
  public prefix is `AUTOVISUALSKILL_*`.
- Do not restore the old `autoskill/` package path; the Python package is
  `autovisualskill`.
- Do not make text-only skills the README's first impression.
- Do not label the public third category as "source-grounded"; use
  "Interleaved Visual Skill". Source reuse is only an internal asset strategy.
- Never commit API keys, `.env`, private run outputs, or private benchmark
  data. Live model credentials must come from environment variables.
- Prefer local `git`/`gh` commands for repository operations. The user has
  previously asked not to rely on a GitHub connector for this repo.

## Current Input Support

The open-source parser currently supports:

- local images;
- local text-like files: `.txt`, `.md`, `.json`, `.csv`;
- accessible URLs, including visible text and embedded images;
- local videos with extensions `.mp4`, `.mov`, `.webm`, `.avi`, `.mkv`.

Video v1 samples approximately 1 FPS candidates, then asks the VLM to select up
to `max_video_frames` useful keyframes. It does not extract audio, transcripts,
subtitles, or continuous motion semantics.

`autovisualskill/media/pdf_proc.py` exists, but PDF routing is not currently
wired into `autovisualskill/nodes/parse_input.py`; Word input is not implemented.
Do not claim PDF/Word support until this is connected and tested.

## Important Paths

- Core graph: `autovisualskill/graph.py`
- CLI/API entry point: `autovisualskill/main.py`
- Input parsing: `autovisualskill/nodes/parse_input.py`
- Prompt templates: `autovisualskill/prompts/templates.py`
- Manifest schema: `autovisualskill/models/manifest.py`
- Gradio demo: `demo_gradio.py`
- Curated examples: `examples/curated_skills/open_source_homepage_regenerated/`
- Recorded downstream task runs: `examples/task_execution_cases/`
- README/demo videos: `docs/assets/videos/`

## Showcase Discipline

The README gallery should stay organized by visual bottleneck:

1. Static skills clarify spatial conventions.
2. Dynamic skills externalize runtime state.
3. Interleaved skills bind steps to visual evidence.

For dynamic demos, the visible middle state matters more than a polished final
image. Counting anchors, checked candidates, and slide critique regions should
be rendered on the current task image.

When regenerating GIF demos with `tools/render_video_demos.py`, verify each GIF
has more than one frame, positive per-frame duration, and `loop=0`. A previous
bug wrote zero-duration GIF frames, which looked static on GitHub.

## Current Curated Example Set

Static:

- `03_gui_icon_grounding`: button click target.
- `04_table_cell_intersection`: row/column intersection.
- `05_chart_projection`: bar-to-axis projection.

Dynamic:

- `13_presentation_style_redraw`: PPT critique-and-redraw.
- `02_dense_counting`: dense counting with visible anchors.
- `06_connect_lines`: incremental line tracing.
- `07_find_different`: odd-one-out visual search.
- `10_geometry_auxiliary_lines`: geometry construction overlays.

Interleaved:

- `09_pythagorean_visual_proof_video`: sampled proof keyframes.
- `08_vscode_remote_ssh_url`: documentation screenshot workflow.
- `11_visual_colleague_skill`: multimodal chat evidence for a colleague's
  visual critique habit.

## Verification Commands

Run these before committing meaningful changes:

```bash
git diff --check
PYTHONPYCACHEPREFIX=/tmp/autovisualskill_pycache python -m compileall autovisualskill demo_gradio.py examples tools
python examples/mock_smoke.py
```

If local Python lacks dependencies, use an environment with `requirements.txt`
installed. The known server conda environment is suitable for `mock_smoke.py`,
but do not put private server paths or credentials into repo files.

Useful demo checks:

```bash
python tools/render_video_demos.py
python tools/render_task_outcome_comparisons.py
python -m json.tool examples/task_execution_cases/task_execution_results.json >/tmp/task_execution_results.check.json
```

