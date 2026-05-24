import os

import cv2


def select_evenly_spaced_indices(total_items: int, max_items: int) -> list[int]:
    """Return evenly spaced item indices that include the first and last item."""
    if total_items <= 0 or max_items <= 0:
        return []
    count = min(total_items, max_items)
    if count == 1:
        return [0]
    return [
        round(i * (total_items - 1) / (count - 1))
        for i in range(count)
    ]


def _one_fps_frame_indices(total_frames: int, fps: float) -> list[int]:
    """Return approximately one frame per second, preserving the final frame."""
    if total_frames <= 0:
        return []
    if fps <= 0:
        return select_evenly_spaced_indices(total_frames, min(total_frames, 8))

    duration_seconds = max((total_frames - 1) / fps, 0)
    indices = [min(round(second * fps), total_frames - 1) for second in range(int(duration_seconds) + 1)]
    if indices[-1] != total_frames - 1:
        indices.append(total_frames - 1)
    return list(dict.fromkeys(indices))


def extract_one_fps_frames(video_path: str, output_dir: str) -> list[dict]:
    """Sample approximately one candidate frame per second and return metadata."""
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if total <= 0:
        cap.release()
        return []

    target_indices = set(_one_fps_frame_indices(total, fps))
    records: list[dict] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx in target_indices:
            p = os.path.join(output_dir, f"frame_{idx:06d}.png")
            cv2.imwrite(p, frame)
            timestamp_sec = idx / fps if fps > 0 else float(len(records))
            records.append(
                {
                    "path": os.path.abspath(p),
                    "frame_index": idx,
                    "timestamp_sec": round(timestamp_sec, 3),
                }
            )
        idx += 1

    cap.release()
    return records


def extract_key_frames(video_path: str, output_dir: str, max_frames: int = 8) -> list[str]:
    """Sample one-frame-per-second candidates, then return evenly spaced keyframes."""
    candidates = extract_one_fps_frames(video_path, output_dir)
    selected_indices = select_evenly_spaced_indices(len(candidates), max_frames)
    return [candidates[index]["path"] for index in selected_indices]
