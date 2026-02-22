"""Camera operations shared by Electron wrappers and native Qt UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time


class CameraError(RuntimeError):
    """Raised when camera capture or recording fails."""


class DependencyError(CameraError):
    """Raised when required runtime dependencies are unavailable."""


@dataclass(frozen=True)
class PreviewFrame:
    width: int
    height: int
    rgb_bytes: bytes


def _load_cv2():
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as error:
        if "cv2" in str(error):
            raise DependencyError(
                "OpenCV dependency missing. Install with: python3 -m pip install opencv-python"
            ) from error
        raise
    return cv2


def _normalize_url(video_url: str) -> str:
    url = (video_url or "").strip()
    if not url:
        raise CameraError("Stream URL is required.")
    return url


def _normalize_duration(clip_seconds: int) -> int:
    try:
        parsed = int(clip_seconds)
    except (TypeError, ValueError):
        return 5
    if parsed <= 0:
        return 5
    return parsed


def _resolve_output_dir(output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return Path.cwd().parent
    return Path(output_dir)


def _timestamp_label() -> str:
    return datetime.now().strftime("%y-%m-%d-%H-%M")


def capture_preview_frame(video_url: str) -> PreviewFrame:
    cv2 = _load_cv2()
    url = _normalize_url(video_url)
    cap = cv2.VideoCapture(url)

    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise CameraError("Could not read a frame from stream URL.")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        return PreviewFrame(width=width, height=height, rgb_bytes=rgb.tobytes())
    finally:
        cap.release()


def capture_snapshot(video_url: str, output_dir: str | Path | None = None) -> Path:
    cv2 = _load_cv2()
    url = _normalize_url(video_url)
    destination_dir = _resolve_output_dir(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"frame--{_timestamp_label()}.png"

    cap = cv2.VideoCapture(url)
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise CameraError("Could not read a frame from stream URL.")

        write_ok = cv2.imwrite(str(destination_path), frame)
        if not write_ok:
            raise CameraError("OpenCV failed to write the snapshot file.")
        return destination_path
    finally:
        cap.release()


def record_clip(
    video_url: str,
    clip_seconds: int = 5,
    output_dir: str | Path | None = None,
    fps: float = 5.0,
    frame_size: tuple[int, int] = (640, 480),
) -> Path:
    cv2 = _load_cv2()
    url = _normalize_url(video_url)
    duration = _normalize_duration(clip_seconds)
    destination_dir = _resolve_output_dir(output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"output--{_timestamp_label()}.mp4"

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        cap.release()
        raise CameraError("Could not open stream URL.")

    fourcc = cv2.VideoWriter_fourcc(*"MP4V")
    writer = cv2.VideoWriter(str(destination_path), fourcc, fps, frame_size)
    if not writer.isOpened():
        cap.release()
        writer.release()
        raise CameraError("Could not create video output file.")

    frames_written = 0
    started_at = time.time()
    try:
        while time.time() < started_at + duration:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            if frame.shape[1] != frame_size[0] or frame.shape[0] != frame_size[1]:
                frame = cv2.resize(frame, frame_size)
            writer.write(frame)
            frames_written += 1
    finally:
        cap.release()
        writer.release()

    if frames_written == 0:
        destination_path.unlink(missing_ok=True)
        raise CameraError("No frames were recorded from stream URL.")

    return destination_path

