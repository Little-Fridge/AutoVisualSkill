if __package__ is None or __package__ == "":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autovisualskill.graph import app
from autovisualskill.config import build_run_config
from autovisualskill.state import GraphState


def run(
    user_goal: str,
    input_files: list[str] | None = None,
    *,
    output_dir: str | None = None,
    output_root: str | None = None,
    temp_root: str | None = None,
    enable_web_research: bool = True,
    max_web_results: int = 5,
    max_url_images: int = 8,
    max_video_frames: int = 12,
    max_images_to_llm: int = 4,
    max_text_chars: int = 8000,
    image_generation_base_url: str | None = None,
    image_generation_api_key: str | None = None,
    image_generation_model: str | None = None,
    image_generation_timeout: float = 120.0,
) -> dict:
    """
    Run the AutoVisualSkill agent.

    Args:
        user_goal: User's natural-language goal.
        input_files: File paths or URLs. None is treated as an empty list.
        output_dir: Exact artifact directory. If omitted, a run-specific
            directory is created under output_root.
        output_root: Parent directory for generated artifacts.
        temp_root: Parent directory for run-scoped temporary files.
        enable_web_research: Whether to search the web when context is missing.
        max_web_results: Maximum web results to collect for missing context.
        max_url_images: Maximum tutorial/documentation images to extract from
            each URL input and expose as candidate visual assets.
        max_video_frames: Maximum VLM-selected keyframes to retain from each
            local video input after 1 FPS candidate sampling.
        max_images_to_llm: Maximum images/frames passed to analysis/design calls.
        max_text_chars: Maximum extracted text characters passed to LLM calls.
        image_generation_base_url: Base URL for the external image-generation API.
        image_generation_api_key: API key for the external image-generation API.
            It is injected through the process environment for this run and is not
            written to run_config.json.
        image_generation_model: Default image-generation model name, e.g. "nanobanana".
        image_generation_timeout: Timeout in seconds for image-generation calls.

    Returns:
        The final GraphState dictionary.
    """
    run_config = build_run_config(
        output_dir=output_dir,
        output_root=output_root,
        temp_root=temp_root,
        enable_web_research=enable_web_research,
        max_web_results=max_web_results,
        max_url_images=max_url_images,
        max_video_frames=max_video_frames,
        max_images_to_llm=max_images_to_llm,
        max_text_chars=max_text_chars,
        image_generation_base_url=image_generation_base_url,
        image_generation_model=image_generation_model,
        image_generation_timeout=image_generation_timeout,
        image_generation_api_key_provided=bool(image_generation_api_key),
    )
    initial_state: GraphState = {
        "run_id": run_config["run_id"],
        "run_config": run_config,
        "temp_dir": run_config["temp_dir"],
        "user_goal": user_goal,
        "input_files": input_files or [],
        "modalities": [],
        "input_artifacts": [],
        "extracted_texts": [],
        "extracted_frames": [],
        "needs_web_research": False,
        "missing_context_notes": [],
        "search_queries": [],
        "web_context": "",
        "web_sources": [],
        "task_domain": "",
        "material_summary": "",
        "skill_type": "text",
        "visual_skill_kind": "text",
        "skill_blueprint": "",
        "visual_prior_paths": [],
        "visual_prior_descriptions": [],
        "skill_md_content": "",
        "output_dir": run_config["output_dir"],
        "warnings": [],
        "errors": [],
        "provenance": [],
    }

    import os

    image_key_env = "AUTOVISUALSKILL_IMAGE_API_KEY"
    previous_image_api_key = os.environ.get(image_key_env)
    if image_generation_api_key:
        os.environ[image_key_env] = image_generation_api_key

    try:
        final_state = app.invoke(initial_state)
    finally:
        if image_generation_api_key:
            if previous_image_api_key is None:
                os.environ.pop(image_key_env, None)
            else:
                os.environ[image_key_env] = previous_image_api_key

    return final_state


def build_arg_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m autovisualskill.main",
        description="Generate an AutoVisualSkill artifact from a goal and optional local files, videos, or URLs.",
    )
    parser.add_argument(
        "goal",
        nargs="?",
        default="Create a skill for identifying buttons in a GUI screenshot",
        help="Natural-language goal describing the skill to generate.",
    )
    parser.add_argument(
        "input_files",
        nargs="*",
        help="Optional local text/image/video files or URLs to use as source material.",
    )
    parser.add_argument("--output-dir", help="Exact artifact directory to write.")
    parser.add_argument("--output-root", help="Parent directory for generated artifacts.")
    parser.add_argument("--temp-root", help="Parent directory for temporary run files.")
    parser.add_argument(
        "--no-web-research",
        action="store_true",
        help="Disable web research even when the graph detects missing context.",
    )
    parser.add_argument("--max-web-results", type=int, default=5)
    parser.add_argument("--max-url-images", type=int, default=8)
    parser.add_argument("--max-video-frames", type=int, default=12)
    parser.add_argument("--max-images-to-llm", type=int, default=4)
    parser.add_argument("--max-text-chars", type=int, default=8000)
    parser.add_argument(
        "--backend",
        help="Optional LLM backend override, e.g. 'subagent' for the bundled mock backend.",
    )
    parser.add_argument(
        "--subagent-cmd",
        help="Command used when --backend=subagent, e.g. 'python tools/mock_subagent_backend.py'.",
    )
    parser.add_argument("--image-generation-base-url")
    parser.add_argument("--image-generation-api-key")
    parser.add_argument("--image-generation-model")
    parser.add_argument("--image-generation-timeout", type=float, default=120.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    import os

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.backend:
        os.environ["AUTOVISUALSKILL_LLM_BACKEND"] = args.backend
    if args.subagent_cmd:
        os.environ["AUTOVISUALSKILL_SUBAGENT_CMD"] = args.subagent_cmd

    result = run(
        args.goal,
        args.input_files,
        output_dir=args.output_dir,
        output_root=args.output_root,
        temp_root=args.temp_root,
        enable_web_research=not args.no_web_research,
        max_web_results=args.max_web_results,
        max_url_images=args.max_url_images,
        max_video_frames=args.max_video_frames,
        max_images_to_llm=args.max_images_to_llm,
        max_text_chars=args.max_text_chars,
        image_generation_base_url=args.image_generation_base_url,
        image_generation_api_key=args.image_generation_api_key,
        image_generation_model=args.image_generation_model,
        image_generation_timeout=args.image_generation_timeout,
    )
    print(f"\nSkill artifact saved to: {result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
