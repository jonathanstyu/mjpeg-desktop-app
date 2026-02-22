"""Compatibility wrapper used by the Electron shell."""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) in sys.path:
    sys.path.remove(str(SCRIPT_DIR))

REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from native_app.services.camera_service import CameraError, record_clip


def _verify_cv2_dependency() -> bool:
    try:
        import cv2  # noqa: F401
    except ModuleNotFoundError as error:
        if "cv2" in str(error):
            print("ERROR: OpenCV dependency missing. Install with: python3 -m pip install opencv-python")
            return False
        raise
    return True


def _parse_duration(argv: list[str]) -> int:
    if len(argv) < 3:
        return 5
    try:
        parsed = int(argv[2])
    except ValueError:
        return 5
    if parsed <= 0:
        return 5
    return parsed


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Fail: missing stream URL")
        return 1

    if not _verify_cv2_dependency():
        return 1

    video_url = argv[1]
    clip_seconds = _parse_duration(argv)

    try:
        record_clip(video_url, clip_seconds=clip_seconds, output_dir=Path.cwd().parent)
    except CameraError as error:
        print(f"Fail: {error}")
        return 1

    print("Success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
