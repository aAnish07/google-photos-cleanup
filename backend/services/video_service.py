"""Video frame sampling and per-frame result aggregation.

For each video we sample VIDEO_FRAMES frames at evenly spaced, mid-interval
positions (for 10 frames: 5%, 15%, ... 95% of the timeline), classify each
frame with the same Choice questions as photos, then aggregate the per-frame
answers into a single judgment for the whole video.

Frame extraction uses OpenCV's bundled decoder, so no system ffmpeg install is
required.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

import cv2
from PIL import Image

from services.classifier import QUESTIONS

# Ordinal scales for aggregating ranked answers (higher = more keep-worthy /
# higher quality). Used to average across frames.
_KEEP_ORDINAL = {
    "definitely_keep": 3,
    "maybe_keep": 2,
    "likely_delete": 1,
    "definitely_delete": 0,
}
_QUALITY_ORDINAL = {"high": 3, "medium": 2, "low": 1, "blurry": 0}


def extract_frames(video_path: str, out_dir: str, n_frames: int) -> list[str]:
    """Sample n_frames frames and write them as JPEGs. Returns their paths.

    Frames are taken at mid-interval positions so we never land on the very
    first or last (often black) frame.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open the video (unsupported codec?)")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    try:
        for i in range(n_frames):
            frac = (i + 0.5) / n_frames  # 0.05, 0.15, ... for n=10
            if total > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(total - 1, int(frac * total)))
            else:
                # Unknown length: seek by time position as a fraction.
                cap.set(cv2.CAP_PROP_POS_AVI_RATIO, frac)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            # BGR (OpenCV) -> RGB (PIL)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            dest = str(Path(out_dir) / f"frame_{i:02d}.jpg")
            Image.fromarray(rgb).save(dest, "JPEG", quality=90)
            paths.append(dest)
    finally:
        cap.release()

    if not paths:
        raise RuntimeError("No frames could be extracted from the video")
    return paths


def aggregate(frame_results: list[dict[str, dict]]) -> dict[str, dict]:
    """Combine per-frame Choice answers into one result for the video.

    - keep_signal / quality_signal: average their ordinal rank across frames,
      then map back to the nearest category (keep the best-moment bias modest by
      using a plain mean).
    - photo_type: majority vote across frames.
    - has_text: "yes" if at least one frame clearly has text (text anywhere in
      the video is significant), else "no".
    Confidence for each is the mean per-frame confidence of that question.
    """
    if not frame_results:
        raise ValueError("No frame results to aggregate")

    def mean_conf(key: str) -> float:
        vals = [
            fr[key]["confidence"]
            for fr in frame_results
            if fr.get(key) and fr[key].get("confidence") is not None
        ]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def ordinal_avg(key: str, scale: dict[str, int]) -> str:
        vals = [scale.get(fr[key]["choice"]) for fr in frame_results if fr.get(key)]
        vals = [v for v in vals if v is not None]
        if not vals:
            return list(scale.keys())[0]
        avg = sum(vals) / len(vals)
        # nearest category by ordinal
        return min(scale.items(), key=lambda kv: abs(kv[1] - avg))[0]

    def majority(key: str) -> str:
        choices = [fr[key]["choice"] for fr in frame_results if fr.get(key)]
        return Counter(choices).most_common(1)[0][0] if choices else "other"

    has_text_choice = (
        "yes"
        if any(fr.get("has_text", {}).get("choice") == "yes" for fr in frame_results)
        else "no"
    )

    result = {
        "photo_type": {"choice": majority("photo_type"), "confidence": mean_conf("photo_type")},
        "keep_signal": {
            "choice": ordinal_avg("keep_signal", _KEEP_ORDINAL),
            "confidence": mean_conf("keep_signal"),
        },
        "has_text": {"choice": has_text_choice, "confidence": mean_conf("has_text")},
        "quality_signal": {
            "choice": ordinal_avg("quality_signal", _QUALITY_ORDINAL),
            "confidence": mean_conf("quality_signal"),
        },
    }
    # Guard: only emit keys we actually model.
    return {k: result[k] for k in QUESTIONS}


def best_frame_path(frame_paths: list[str], frame_results: list[dict]) -> Optional[str]:
    """Pick a representative frame (most keep-worthy) to use as the thumbnail."""
    if not frame_paths:
        return None
    best_i, best_rank = 0, -1.0
    for i, fr in enumerate(frame_results):
        if i >= len(frame_paths):
            break
        ks = fr.get("keep_signal", {})
        rank = _KEEP_ORDINAL.get(ks.get("choice"), 0) + (ks.get("confidence") or 0)
        if rank > best_rank:
            best_rank, best_i = rank, i
    return frame_paths[min(best_i, len(frame_paths) - 1)]
