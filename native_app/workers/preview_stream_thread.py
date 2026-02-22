"""Background thread for continuously reading MJPEG preview frames."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from native_app.services.camera_service import PreviewFrame


class PreviewStreamThread(QThread):
    frame_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, video_url: str, target_fps: float = 12.0, parent=None):
        super().__init__(parent)
        self._video_url = (video_url or "").strip()
        self._target_fps = max(1.0, float(target_fps))
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not self._video_url:
            self.failed.emit("Stream URL is required.")
            return

        try:
            import cv2  # type: ignore
        except ModuleNotFoundError as error:
            if "cv2" in str(error):
                self.failed.emit(
                    "OpenCV dependency missing. Install with: python3 -m pip install opencv-python"
                )
                return
            self.failed.emit(str(error))
            return

        cap = cv2.VideoCapture(self._video_url)
        if not cap.isOpened():
            cap.release()
            self.failed.emit("Could not open stream URL.")
            return

        frame_interval = 1.0 / self._target_fps
        try:
            while self._running:
                frame_started_at = time.time()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                self.frame_ready.emit(PreviewFrame(width=width, height=height, rgb_bytes=rgb.tobytes()))

                elapsed = time.time() - frame_started_at
                sleep_for = frame_interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            cap.release()
