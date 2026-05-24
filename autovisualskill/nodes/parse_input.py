import mimetypes
import os

from langchain_core.messages import HumanMessage, SystemMessage

from autovisualskill.llm.client import call_llm_structured, image_to_base64
from autovisualskill.media.web_capture import fetch_url_images, fetch_url_text
from autovisualskill.media.image_proc import prepare_image_for_llm
from autovisualskill.media.video_proc import extract_one_fps_frames, select_evenly_spaced_indices
from autovisualskill.models.llm_responses import VideoFrameSelection
from autovisualskill.prompts.templates import VIDEO_FRAME_SELECTION_SYSTEM
from autovisualskill.state import GraphState
from autovisualskill.utils import append_records, issue_record, provenance_record, sanitize_filename

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def _artifact(source: str, modality: str, **extra) -> dict:
    return {"source": source, "modality": modality, **extra}


def _prepared_frame(
    source_path: str,
    output_dir: str,
    prefix: str,
    index: int,
    artifacts: list[dict],
    source: str,
) -> str:
    filename = sanitize_filename(f"{prefix}_{index}.png", default="frame", suffix=".png")
    output_path = os.path.join(output_dir, filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    prepared = prepare_image_for_llm(source_path, output_path)
    artifacts.append(
        _artifact(
            source,
            "image",
            extracted_path=os.path.abspath(prepared),
            original_path=os.path.abspath(source_path),
        )
    )
    return os.path.abspath(prepared)


def _is_video_input(file_path: str, mime: str) -> bool:
    return mime.startswith("video/") or os.path.splitext(file_path)[1].lower() in VIDEO_EXTENSIONS


def _select_video_frame_indices(
    *,
    user_goal: str,
    source_path: str,
    candidates: list[dict],
    max_frames: int,
) -> tuple[list[int], str, str]:
    if not candidates:
        return [], "none", "No 1 FPS video candidates were available."

    max_selected = min(max(1, max_frames), len(candidates))
    if len(candidates) <= max_selected:
        return list(range(len(candidates))), "all_1fps_candidates", "All 1 FPS candidate frames were retained."

    candidate_lines = [
        (
            f"[Candidate {idx}] timestamp_sec={candidate.get('timestamp_sec')} "
            f"source_frame_index={candidate.get('frame_index')}"
        )
        for idx, candidate in enumerate(candidates)
    ]
    content_blocks: list[dict] = [
        {
            "type": "text",
            "text": (
                f"User goal: {user_goal}\n"
                f"Source video: {source_path}\n"
                f"Candidate frame count: {len(candidates)}\n"
                f"Maximum selected frames: {max_selected}\n\n"
                "Candidate frames:\n"
                + "\n".join(candidate_lines)
            ),
        }
    ]
    for idx, candidate in enumerate(candidates):
        content_blocks.append({"type": "text", "text": f"[Candidate {idx}]"})
        content_blocks.append({"type": "image_url", "image_url": {"url": image_to_base64(candidate["path"])}})

    messages = [
        SystemMessage(content=VIDEO_FRAME_SELECTION_SYSTEM),
        HumanMessage(content=content_blocks),
    ]
    selection: VideoFrameSelection = call_llm_structured(messages, VideoFrameSelection)
    selected: list[int] = []
    for raw_index in selection.selected_indices:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(candidates) and index not in selected:
            selected.append(index)
        if len(selected) >= max_selected:
            break
    if not selected:
        selected = select_evenly_spaced_indices(len(candidates), max_selected)
        return selected, "fallback_even_after_empty_vlm_selection", selection.rationale
    selected.sort()
    return selected, "vlm_selected_from_1fps_candidates", selection.rationale


def run(state: GraphState) -> dict:
    modalities: list[str] = []
    input_artifacts: list[dict] = []
    extracted_texts: list[str] = []
    extracted_frames: list[str] = []
    warnings: list[dict] = []
    errors: list[dict] = []

    config = state.get("run_config", {})
    temp_dir = config.get("temp_dir") or state.get("temp_dir") or os.path.join(os.getcwd(), ".autovisualskill_tmp")
    media_dir = os.path.join(temp_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    for i, file_path in enumerate(state["input_files"]):
        # URL tutorial / documentation page. Treat it as remote text context.
        if file_path.startswith("http://") or file_path.startswith("https://"):
            try:
                text = fetch_url_text(file_path)
            except Exception as exc:
                errors.append(
                    issue_record(
                        "parse_input",
                        "Failed to fetch URL text",
                        source=file_path,
                        modality="url",
                        error=str(exc),
                    )
                )
                continue

            modalities.append("text")
            filename = sanitize_filename(f"url_{i}.txt", default="url", suffix=".txt")
            extracted_path = os.path.abspath(os.path.join(media_dir, filename))
            os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
            with open(extracted_path, "w", encoding="utf-8") as f:
                f.write(text)
            input_artifacts.append(
                _artifact(
                    file_path,
                    "url",
                    extracted_path=extracted_path,
                    content_type="text/html",
                    extraction="visible_text",
                )
            )

            image_records = fetch_url_images(
                file_path,
                os.path.join(media_dir, f"url_{i}_images"),
                max_images=int(config.get("max_url_images", 8)),
            )
            image_notes: list[str] = []
            for image_record in image_records:
                frame_index = len(extracted_frames)
                prepared = _prepared_frame(
                    image_record["path"],
                    media_dir,
                    f"url_{i}_image",
                    frame_index,
                    input_artifacts,
                    image_record["url"],
                )
                input_artifacts[-1].update(
                    {
                        "source_url": image_record["url"],
                        "alt": image_record.get("alt", ""),
                        "caption": image_record.get("caption", ""),
                        "width": image_record.get("width"),
                        "height": image_record.get("height"),
                        "extraction": "url_embedded_image",
                    }
                )
                extracted_frames.append(prepared)
                modalities.append("image")
                image_notes.append(
                    " | ".join(
                        part
                        for part in [
                            f"[Image {frame_index}]",
                            f"source={image_record['url']}",
                            f"alt={image_record.get('alt', '')}",
                            f"caption={image_record.get('caption', '')}",
                        ]
                        if part
                    )
                )

            image_section = ""
            if image_notes:
                image_section = "\n\nExtracted tutorial images:\n" + "\n".join(image_notes)

            extracted_texts.append(f"Source URL: {file_path}\n\n{text}{image_section}")
            continue

        # Local file.
        if not os.path.isfile(file_path):
            errors.append(issue_record("parse_input", "File not found", source=file_path))
            continue

        mime, _ = mimetypes.guess_type(file_path)
        mime = mime or ""

        if mime.startswith("image/"):
            modalities.append("image")
            input_artifacts.append(_artifact(file_path, "image", original_path=os.path.abspath(file_path)))
            prepared = _prepared_frame(file_path, media_dir, f"image_{i}", 0, input_artifacts, file_path)
            extracted_frames.append(prepared)

        elif mime.startswith("text/") or file_path.endswith((".txt", ".md", ".json", ".csv")):
            modalities.append("text")
            input_artifacts.append(_artifact(file_path, "text", original_path=os.path.abspath(file_path)))
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                extracted_texts.append(f.read())

        elif _is_video_input(file_path, mime):
            max_video_frames = max(1, int(config.get("max_video_frames", 12)))
            video_path = os.path.abspath(file_path)
            frame_dir = os.path.join(media_dir, f"video_{i}_frames")
            try:
                candidate_frames = extract_one_fps_frames(file_path, frame_dir)
            except Exception as exc:
                errors.append(
                    issue_record(
                        "parse_input",
                        "Failed to sample 1 FPS video candidates",
                        source=file_path,
                        modality="video",
                        error=str(exc),
                    )
                )
                continue

            try:
                selected_candidate_indices, selection_strategy, selection_rationale = _select_video_frame_indices(
                    user_goal=state.get("user_goal", ""),
                    source_path=video_path,
                    candidates=candidate_frames,
                    max_frames=max_video_frames,
                )
            except Exception as exc:
                selected_candidate_indices = select_evenly_spaced_indices(len(candidate_frames), max_video_frames)
                selection_strategy = "fallback_even_after_vlm_error"
                selection_rationale = f"VLM frame selection failed; used evenly spaced fallback. Error: {exc}"
                warnings.append(
                    issue_record(
                        "parse_input",
                        "VLM video frame selection failed; using evenly spaced fallback",
                        source=file_path,
                        modality="video",
                        error=str(exc),
                    )
                )

            sampled_frames = [candidate_frames[index] for index in selected_candidate_indices]

            modalities.append("video")
            input_artifacts.append(
                _artifact(
                    file_path,
                    "video",
                    original_path=video_path,
                    extraction="one_fps_candidates_vlm_selected_keyframes",
                    requested_max_frames=max_video_frames,
                    candidate_frame_count=len(candidate_frames),
                    sampled_frame_count=len(sampled_frames),
                    selected_candidate_indices=selected_candidate_indices,
                    selection_strategy=selection_strategy,
                    selection_rationale=selection_rationale,
                )
            )

            if not candidate_frames:
                warnings.append(
                    issue_record(
                        "parse_input",
                        "No 1 FPS video candidate frames could be sampled",
                        source=file_path,
                        modality="video",
                    )
                )

            frame_notes: list[str] = []
            for frame_order, candidate in enumerate(sampled_frames):
                frame_index = len(extracted_frames)
                prepared = _prepared_frame(
                    candidate["path"],
                    media_dir,
                    f"video_{i}_frame",
                    frame_index,
                    input_artifacts,
                    file_path,
                )
                input_artifacts[-1].update(
                    {
                        "parent_video": video_path,
                        "frame_order": frame_order,
                        "frame_index": frame_index,
                        "candidate_index": selected_candidate_indices[frame_order],
                        "source_frame_index": candidate.get("frame_index"),
                        "timestamp_sec": candidate.get("timestamp_sec"),
                        "extraction": "video_keyframe",
                    }
                )
                extracted_frames.append(prepared)
                modalities.append("image")
                frame_notes.append(
                    " | ".join(
                        [
                            f"[Frame {frame_index}]",
                            f"order={frame_order}",
                            f"candidate_index={selected_candidate_indices[frame_order]}",
                            f"timestamp_sec={candidate.get('timestamp_sec')}",
                            f"source_frame_index={candidate.get('frame_index')}",
                            f"source_video={video_path}",
                        ]
                    )
                )

            extracted_texts.append(
                "Source video: "
                f"{video_path}\n\n"
                "Video candidate frames were sampled at approximately 1 FPS, then selected by a VLM "
                f"for visual-skill authoring. Selection strategy: {selection_strategy}. "
                f"Selection rationale: {selection_rationale}\n"
                "Use selected frames as a coarse visual timeline; this open-source v1 does not extract "
                "audio, speech transcripts, subtitles, or continuous motion semantics.\n"
                + "\n".join(frame_notes)
            )

        else:
            errors.append(
                issue_record(
                    "parse_input",
                    "Unsupported input modality in open-source v1",
                    source=file_path,
                    mime=mime,
                )
            )

    modalities = list(dict.fromkeys(modalities))

    return {
        "modalities": modalities,
        "input_artifacts": input_artifacts,
        "extracted_texts": extracted_texts,
        "extracted_frames": extracted_frames,
        "warnings": append_records(state, "warnings", warnings),
        "errors": append_records(state, "errors", errors),
        "provenance": append_records(
            state,
            "provenance",
            [
                provenance_record(
                    "parse_input",
                    "parsed_inputs",
                    input_count=len(state["input_files"]),
                    frame_count=len(extracted_frames),
                    text_count=len(extracted_texts),
                )
            ],
        ),
    }
