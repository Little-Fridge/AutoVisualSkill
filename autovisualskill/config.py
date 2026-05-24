import os
import time
import uuid
from typing import Any


def new_run_id() -> str:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}_{suffix}"


def build_run_config(
    *,
    run_id: str | None = None,
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
    image_generation_model: str | None = None,
    image_generation_timeout: float = 120.0,
    image_generation_api_key_provided: bool = False,
) -> dict[str, Any]:
    resolved_run_id = run_id or new_run_id()
    cwd = os.getcwd()
    resolved_output_root = os.path.abspath(output_root or os.path.join(cwd, "skill_output"))
    resolved_temp_root = os.path.abspath(temp_root or os.path.join(cwd, ".autovisualskill_tmp"))
    resolved_output_dir = os.path.abspath(output_dir or os.path.join(resolved_output_root, resolved_run_id))
    resolved_temp_dir = os.path.abspath(os.path.join(resolved_temp_root, resolved_run_id))

    return {
        "run_id": resolved_run_id,
        "output_dir": resolved_output_dir,
        "output_root": resolved_output_root,
        "temp_dir": resolved_temp_dir,
        "enable_web_research": enable_web_research,
        "max_web_results": max_web_results,
        "max_url_images": max_url_images,
        "max_video_frames": max_video_frames,
        "max_images_to_llm": max_images_to_llm,
        "max_text_chars": max_text_chars,
        "image_generation_base_url": image_generation_base_url
        or os.environ.get("AUTOVISUALSKILL_IMAGE_API_BASE_URL", ""),
        "image_generation_model": image_generation_model
        or os.environ.get("AUTOVISUALSKILL_IMAGE_API_MODEL", "nanobanana"),
        "image_generation_timeout": image_generation_timeout,
        "image_generation_api_key_provided": bool(
            image_generation_api_key_provided or os.environ.get("AUTOVISUALSKILL_IMAGE_API_KEY")
        ),
    }
