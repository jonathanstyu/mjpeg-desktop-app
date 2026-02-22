"""Main window for the native PySide6 migration shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from native_app.services.camera_service import (
    PreviewFrame,
    capture_preview_frame,
    capture_snapshot,
    record_clip,
)
from native_app.services.storage import SavedUrl, UrlStore
from native_app.workers.task_thread import TaskThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MJPEG Capture Studio (Native Python)")
        self.resize(1280, 840)
        self.setMinimumSize(1100, 760)

        self._settings = QSettings("mjpeg-desktop-app", "native-shell")
        self._url_store = UrlStore(self._settings)
        self._task_thread: TaskThread | None = None
        self._preview_pixmap: QPixmap | None = None
        self._latest_output_path: Path | None = None
        self._recording_end_ms = 0
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(250)
        self._recording_timer.timeout.connect(self._render_recording_status)
        self._tray_icon: QSystemTrayIcon | None = None

        self._build_ui()
        self._configure_tray_notifications()
        self._refresh_saved_urls(self._url_store.load())
        self._set_status("Enter a stream URL to begin.", "info")

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(16)

        header = QLabel("MJPEG Capture Studio")
        header.setObjectName("appHeader")
        subtitle = QLabel("Native PySide6 shell using shared Python camera services.")
        subtitle.setObjectName("appSubtitle")
        outer_layout.addWidget(header)
        outer_layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        outer_layout.addLayout(grid, stretch=1)

        capture_group = QGroupBox("Capture Controls")
        capture_layout = QVBoxLayout(capture_group)
        capture_layout.setSpacing(10)
        grid.addWidget(capture_group, 0, 0)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("http://example.com/mjpeg")
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self._handle_preview)
        url_row.addWidget(self.url_input, stretch=1)
        url_row.addWidget(self.preview_button)
        capture_layout.addLayout(url_row)

        actions_row = QHBoxLayout()
        self.snapshot_button = QPushButton("Take Snapshot")
        self.snapshot_button.clicked.connect(self._handle_snapshot)
        self.duration_select = QComboBox()
        self.duration_select.addItems(["5", "10", "15", "25"])
        self.duration_select.setToolTip("Clip length in seconds")
        self.record_button = QPushButton("Record Clip")
        self.record_button.clicked.connect(self._handle_record)
        actions_row.addWidget(self.snapshot_button)
        actions_row.addWidget(self.duration_select)
        actions_row.addWidget(self.record_button)
        capture_layout.addLayout(actions_row)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("Preview will render here.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(380)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setObjectName("previewFrame")
        preview_layout.addWidget(self.preview_label)
        grid.addWidget(preview_group, 1, 0)

        status_group = QGroupBox("Session Status")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("statusInfo")
        status_layout.addWidget(self.status_label)
        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.clicked.connect(self._open_latest_output_folder)
        self.open_output_button.setVisible(False)
        status_layout.addWidget(self.open_output_button, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(status_group, 0, 1)

        saved_group = QGroupBox("Saved URLs (click one to load)")
        saved_layout = QVBoxLayout(saved_group)
        self.saved_urls_list = QListWidget()
        self.saved_urls_list.itemClicked.connect(self._handle_saved_url_click)
        saved_layout.addWidget(self.saved_urls_list)
        grid.addWidget(saved_group, 1, 1)

        notes_group = QGroupBox("Migration Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.addWidget(QLabel("This shell keeps output behavior aligned with the Electron version."))
        notes_layout.addWidget(QLabel("Snapshot and recordings still default to the parent directory of cwd."))
        grid.addWidget(notes_group, 2, 1)

        root.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f3f6f9; color: #1f2a37; }
            QLabel#appHeader { font-size: 28px; font-weight: 700; color: #1f2a37; }
            QLabel#appSubtitle { color: #5b6b7d; padding-bottom: 4px; }
            QGroupBox {
              background: #ffffff;
              border: 1px solid #dbe4ef;
              border-radius: 12px;
              margin-top: 8px;
              font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QLabel#previewFrame {
              background: #f8fafc;
              color: #5b6b7d;
              border-radius: 10px;
              border: 1px solid #d2dbe6;
            }
            QLabel#statusInfo {
              border-radius: 8px;
              padding: 10px 12px;
              border: 1px solid #c8ddfb;
              background: #eaf3ff;
              color: #0a3b72;
            }
            QLineEdit, QComboBox, QListWidget {
              background: #ffffff;
              color: #1f2a37;
              border: 1px solid #c8d4e2;
              border-radius: 8px;
              padding: 8px 10px;
              selection-background-color: #dbeafe;
              selection-color: #1f2a37;
            }
            QLineEdit:focus, QComboBox:focus, QListWidget:focus {
              border: 1px solid #0a84ff;
            }
            QComboBox::drop-down {
              border: 0;
              width: 28px;
              background: #f3f6f9;
              border-top-right-radius: 8px;
              border-bottom-right-radius: 8px;
            }
            QListWidget::item {
              background: #ffffff;
              color: #1f2a37;
              border-radius: 6px;
              padding: 6px 8px;
              margin: 2px;
            }
            QListWidget::item:selected {
              background: #dbeafe;
              color: #1f2a37;
            }
            QListWidget::item:hover {
              background: #edf4ff;
            }
            QPushButton {
              border: 0;
              border-radius: 8px;
              padding: 9px 12px;
              font-weight: 600;
              color: white;
              background: #0a84ff;
            }
            QPushButton:hover { background: #086fd4; }
            QPushButton:disabled { background: #94a3b8; }
            """
        )

    def _configure_tray_notifications(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.show()

    def _notify(self, title: str, body: str) -> None:
        if self._tray_icon:
            self._tray_icon.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 3000)

    def _set_status(self, message: str, status_type: str = "info") -> None:
        status_styles = {
            "info": ("#eaf3ff", "#c8ddfb", "#0a3b72"),
            "success": ("#e8f6ea", "#bad9c1", "#14532d"),
            "error": ("#fdecec", "#f5c2c7", "#7f1d1d"),
            "recording": ("#fff7e6", "#ffd08a", "#7a4a00"),
        }
        background, border, color = status_styles.get(status_type, status_styles["info"])
        self.status_label.setStyleSheet(
            f"background:{background};border:1px solid {border};color:{color};padding:10px 12px;border-radius:8px;"
        )
        self.status_label.setText(message)

    def _clear_output_action(self) -> None:
        self._latest_output_path = None
        self.open_output_button.setVisible(False)

    def _set_output_action(self, output_path: str) -> None:
        path = Path(output_path)
        self._latest_output_path = path
        folder = path.parent if path.suffix else path
        self.open_output_button.setToolTip(str(folder))
        self.open_output_button.setVisible(True)

    def _open_latest_output_folder(self) -> None:
        if not self._latest_output_path:
            self._set_status("No output file is available yet.", "error")
            self.open_output_button.setVisible(False)
            return

        folder = self._latest_output_path.parent if self._latest_output_path.suffix else self._latest_output_path
        if not folder.exists():
            self._set_status(f"Output folder not found: {folder}", "error")
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if not opened:
            self._set_status(f"Could not open folder: {folder}", "error")

    def _current_video_url(self) -> str | None:
        url = self.url_input.text().strip()
        if not url:
            self._set_status("Please enter a stream URL first.", "error")
            return None
        return url

    def _refresh_saved_urls(self, saved_urls: list[SavedUrl]) -> None:
        self.saved_urls_list.clear()
        if not saved_urls:
            empty_item = QListWidgetItem("No saved URLs yet. Preview a stream to save it.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.saved_urls_list.addItem(empty_item)
            return

        for entry in saved_urls:
            item = QListWidgetItem(entry["url"])
            item.setData(Qt.ItemDataRole.UserRole, entry["url"])
            self.saved_urls_list.addItem(item)

    def _mark_url_as_used(self, url: str) -> None:
        saved = self._url_store.mark_used(url, QDateTime.currentMSecsSinceEpoch())
        self._refresh_saved_urls(saved)

    def _start_task(
        self,
        task,
        on_success,
        on_failure,
    ) -> bool:
        if self._task_thread and self._task_thread.isRunning():
            self._set_status("Please wait for the current task to finish.", "error")
            return False

        thread = TaskThread(task, self)
        self._task_thread = thread
        thread.succeeded.connect(on_success)
        thread.failed.connect(on_failure)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_task_if_complete)
        thread.start()
        return True

    def _clear_task_if_complete(self) -> None:
        if self._task_thread and not self._task_thread.isRunning():
            self._task_thread = None

    def _handle_saved_url_click(self, item: QListWidgetItem) -> None:
        url = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(url, str) or not url:
            return
        self.url_input.setText(url)
        self._set_status("Loaded saved URL and updated preview.", "success")
        self._handle_preview()

    def _handle_preview(self) -> None:
        video_url = self._current_video_url()
        if not video_url:
            return

        self._clear_output_action()
        self._mark_url_as_used(video_url)
        self._set_status("Loading preview frame...")

        def on_success(preview: object) -> None:
            frame = preview
            if not isinstance(frame, PreviewFrame):
                self._set_status("Preview failed: invalid frame payload.", "error")
                return

            image = QImage(
                frame.rgb_bytes,
                frame.width,
                frame.height,
                frame.width * 3,
                QImage.Format.Format_RGB888,
            ).copy()
            self._preview_pixmap = QPixmap.fromImage(image)
            self._render_preview_pixmap()
            self._set_status("Preview updated.", "success")

        def on_failure(error_text: str) -> None:
            self._set_status(f"Preview failed: {error_text}", "error")

        self._start_task(lambda: capture_preview_frame(video_url), on_success, on_failure)

    def _render_preview_pixmap(self) -> None:
        if not self._preview_pixmap:
            return
        scaled = self._preview_pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _handle_snapshot(self) -> None:
        video_url = self._current_video_url()
        if not video_url:
            return

        self._clear_output_action()
        self._mark_url_as_used(video_url)
        self._set_status("Capturing snapshot...")

        output_dir = Path.cwd().parent

        def on_success(result: object) -> None:
            output_path = str(result)
            self._set_output_action(output_path)
            self._set_status(f"Snapshot saved: {output_path}", "success")
            self._notify("Snapshot complete", output_path)

        def on_failure(error_text: str) -> None:
            self._set_status(f"Snapshot failed: {error_text}", "error")
            self._notify("Snapshot failed", error_text)

        self._start_task(lambda: capture_snapshot(video_url, output_dir=output_dir), on_success, on_failure)

    def _handle_record(self) -> None:
        if self.record_button.text() == "Recording...":
            self._set_status("A recording is already in progress.", "error")
            return

        video_url = self._current_video_url()
        if not video_url:
            return

        self._clear_output_action()
        duration_seconds = int(self.duration_select.currentText())
        self._mark_url_as_used(video_url)
        self._set_recording_ui_state(True)
        self._recording_end_ms = QDateTime.currentMSecsSinceEpoch() + (duration_seconds * 1000)
        self._recording_timer.start()
        self._notify("Recording started", f"Recording clip for {duration_seconds} seconds.")

        output_dir = Path.cwd().parent

        def on_success(result: object) -> None:
            output_path = str(result)
            self._recording_timer.stop()
            self._set_recording_ui_state(False)
            self._set_output_action(output_path)
            self._set_status(f"Recording complete: {output_path}", "success")
            self._notify("Recording complete", output_path)

        def on_failure(error_text: str) -> None:
            self._recording_timer.stop()
            self._set_recording_ui_state(False)
            self._set_status(f"Recording failed: {error_text}", "error")
            self._notify("Recording failed", error_text)

        started = self._start_task(
            lambda: record_clip(video_url, clip_seconds=duration_seconds, output_dir=output_dir),
            on_success,
            on_failure,
        )
        if not started:
            self._recording_timer.stop()
            self._set_recording_ui_state(False)

    def _set_recording_ui_state(self, active: bool) -> None:
        self.record_button.setText("Recording..." if active else "Record Clip")
        self.record_button.setEnabled(not active)
        self.duration_select.setEnabled(not active)
        self.preview_button.setEnabled(not active)
        self.snapshot_button.setEnabled(not active)

    def _render_recording_status(self) -> None:
        remaining_ms = max(0, self._recording_end_ms - QDateTime.currentMSecsSinceEpoch())
        remaining_seconds = max(0, (remaining_ms + 999) // 1000)
        self._set_status(f"Recording in progress... {remaining_seconds}s remaining.", "recording")
        if remaining_ms <= 0:
            self._recording_timer.stop()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_pixmap()
