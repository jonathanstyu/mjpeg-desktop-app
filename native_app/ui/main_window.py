"""Main window for the native PySide6 migration shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from native_app.services.camera_service import (
    PreviewFrame,
    capture_preview_frame,
    capture_snapshot,
    record_clip,
)
from native_app.services.storage import SavedUrl, UrlStore, mask_url_credentials
from native_app.workers.task_thread import TaskThread


class MainWindow(QMainWindow):
    HISTORY_BLOCKED_MESSAGE = (
        "Saved URL list is full and all entries are pinned. "
        "Unpin or delete one to save new URLs."
    )

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
        self._output_dir: Path = self._url_store.default_output_dir()
        self._has_saved_urls = False
        self._active_recording_history_hint = ""

        self._recording_end_ms = 0
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(250)
        self._recording_timer.timeout.connect(self._render_recording_status)
        self._tray_icon: QSystemTrayIcon | None = None

        self._build_ui()
        self._configure_tray_notifications()
        self._sync_output_dir_from_store(show_status=False)
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

        output_label = QLabel("Output Folder")
        status_layout.addWidget(output_label)

        output_row = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setReadOnly(True)
        self.output_dir_input.setPlaceholderText("Select output folder")
        self.browse_output_button = QPushButton("Browse...")
        self.browse_output_button.clicked.connect(self._handle_browse_output_dir)
        self.reset_output_button = QPushButton("Reset")
        self.reset_output_button.clicked.connect(self._handle_reset_output_dir)
        output_row.addWidget(self.output_dir_input, stretch=1)
        output_row.addWidget(self.browse_output_button)
        output_row.addWidget(self.reset_output_button)
        status_layout.addLayout(output_row)

        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.clicked.connect(self._open_latest_output_folder)
        status_layout.addWidget(self.open_output_button, alignment=Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(status_group, 0, 1)

        saved_group = QGroupBox("Saved URLs (click one to load)")
        saved_layout = QVBoxLayout(saved_group)
        self.saved_urls_list = QListWidget()
        self.saved_urls_list.itemClicked.connect(self._handle_saved_url_click)
        self.saved_urls_list.itemSelectionChanged.connect(self._update_saved_url_controls)
        saved_layout.addWidget(self.saved_urls_list)

        saved_actions = QHBoxLayout()
        self.pin_button = QPushButton("Pin")
        self.pin_button.clicked.connect(self._handle_pin_toggle)
        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self._handle_rename)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._handle_delete)
        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.clicked.connect(self._handle_clear_all)

        saved_actions.addWidget(self.pin_button)
        saved_actions.addWidget(self.rename_button)
        saved_actions.addWidget(self.delete_button)
        saved_actions.addWidget(self.clear_all_button)
        saved_layout.addLayout(saved_actions)
        grid.addWidget(saved_group, 1, 1)

        notes_group = QGroupBox("Migration Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_layout.addWidget(QLabel("This shell keeps output behavior aligned with the Electron version."))
        notes_layout.addWidget(QLabel("Saved URL management now includes pin, rename, delete, and clear-all controls."))
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

    def _sync_output_dir_from_store(self, show_status: bool = True) -> bool:
        try:
            self._output_dir = self._url_store.get_output_dir()
        except (OSError, ValueError) as error:
            if show_status:
                self._set_status(f"Output folder error: {error}", "error")
            return False

        self._refresh_output_dir_ui()
        return True

    def _refresh_output_dir_ui(self) -> None:
        self.output_dir_input.setText(str(self._output_dir))
        self.output_dir_input.setToolTip(str(self._output_dir))

        if self._latest_output_path:
            folder = self._latest_output_path.parent if self._latest_output_path.suffix else self._latest_output_path
        else:
            folder = self._output_dir
        self.open_output_button.setToolTip(str(folder))

    def _handle_browse_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Output Folder", str(self._output_dir))
        if not selected:
            return

        try:
            self._output_dir = self._url_store.set_output_dir(Path(selected))
        except (OSError, ValueError) as error:
            self._set_status(f"Output folder error: {error}", "error")
            return

        self._refresh_output_dir_ui()
        self._set_status(f"Output folder updated: {self._output_dir}", "success")

    def _handle_reset_output_dir(self) -> None:
        default_dir = self._url_store.default_output_dir()
        try:
            self._output_dir = self._url_store.set_output_dir(default_dir)
        except (OSError, ValueError) as error:
            self._set_status(f"Output folder error: {error}", "error")
            return

        self._refresh_output_dir_ui()
        self._set_status(f"Output folder reset: {self._output_dir}", "success")

    def _clear_output_action(self) -> None:
        self._latest_output_path = None
        self._refresh_output_dir_ui()

    def _set_output_action(self, output_path: str) -> None:
        self._latest_output_path = Path(output_path)
        self._refresh_output_dir_ui()

    def _open_latest_output_folder(self) -> None:
        if self._latest_output_path:
            folder = self._latest_output_path.parent if self._latest_output_path.suffix else self._latest_output_path
        else:
            if not self._sync_output_dir_from_store(show_status=True):
                return
            folder = self._output_dir

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

    def _selected_saved_entry(self) -> SavedUrl | None:
        item = self.saved_urls_list.currentItem()
        if not item:
            return None

        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return None

        url = str(data.get("url", "")).strip()
        if not url:
            return None

        label = str(data.get("label", "")).strip()
        pinned = bool(data.get("pinned", False))
        last_used_at = int(data.get("last_used_at", 0) or 0)
        return {
            "url": url,
            "label": label,
            "pinned": pinned,
            "last_used_at": last_used_at,
        }

    def _refresh_saved_urls(self, saved_urls: list[SavedUrl], selected_url: str | None = None) -> None:
        self.saved_urls_list.clear()
        self._has_saved_urls = len(saved_urls) > 0

        if not saved_urls:
            empty_item = QListWidgetItem("No saved URLs yet. Preview a stream to save it.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.saved_urls_list.addItem(empty_item)
            self._update_saved_url_controls()
            return

        selected_item: QListWidgetItem | None = None
        for entry in saved_urls:
            display_name = entry["label"] or mask_url_credentials(entry["url"])
            if entry["pinned"]:
                display_name = f"[Pinned] {display_name}"

            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(mask_url_credentials(entry["url"]))
            self.saved_urls_list.addItem(item)

            if selected_url and entry["url"] == selected_url:
                selected_item = item

        if selected_item is not None:
            self.saved_urls_list.setCurrentItem(selected_item)

        self._update_saved_url_controls()

    def _update_saved_url_controls(self) -> None:
        selected = self._selected_saved_entry()
        has_selected = selected is not None

        self.pin_button.setEnabled(has_selected)
        self.pin_button.setText("Unpin" if has_selected and selected["pinned"] else "Pin")
        self.rename_button.setEnabled(has_selected)
        self.delete_button.setEnabled(has_selected)
        self.clear_all_button.setEnabled(self._has_saved_urls)

    def _mark_url_as_used(self, url: str) -> bool:
        saved, blocked = self._url_store.mark_used(url, QDateTime.currentMSecsSinceEpoch())
        self._refresh_saved_urls(saved, selected_url=url)
        if blocked:
            self._set_status(self.HISTORY_BLOCKED_MESSAGE, "error")
        return blocked

    def _history_hint_suffix(self, blocked: bool) -> str:
        if not blocked:
            return ""
        return " URL was not saved to history because all saved entries are pinned."

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
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return

        url = str(data.get("url", "")).strip()
        if not url:
            return

        self.url_input.setText(url)
        self._set_status("Loaded saved URL and updated preview.", "success")
        self._handle_preview()

    def _handle_pin_toggle(self) -> None:
        selected = self._selected_saved_entry()
        if not selected:
            return

        next_pinned = not selected["pinned"]
        saved = self._url_store.set_pinned(selected["url"], next_pinned)
        self._refresh_saved_urls(saved, selected_url=selected["url"])

        verb = "Pinned" if next_pinned else "Unpinned"
        display_url = mask_url_credentials(selected["url"])
        self._set_status(f"{verb} stream: {display_url}", "success")

    def _handle_rename(self) -> None:
        selected = self._selected_saved_entry()
        if not selected:
            return

        next_label, accepted = QInputDialog.getText(
            self,
            "Rename Stream",
            "Label:",
            text=selected["label"],
        )
        if not accepted:
            return

        saved = self._url_store.rename(selected["url"], next_label)
        self._refresh_saved_urls(saved, selected_url=selected["url"])

        normalized_label = next_label.strip()
        if normalized_label:
            self._set_status(f"Stream label updated: {normalized_label}", "success")
        else:
            self._set_status("Stream label cleared.", "success")

    def _handle_delete(self) -> None:
        selected = self._selected_saved_entry()
        if not selected:
            return

        saved = self._url_store.delete(selected["url"])
        self._refresh_saved_urls(saved)
        display_url = mask_url_credentials(selected["url"])
        self._set_status(f"Deleted saved stream: {display_url}", "success")

    def _handle_clear_all(self) -> None:
        if not self._has_saved_urls:
            return

        result = QMessageBox.question(
            self,
            "Clear Saved URLs",
            "Remove all saved stream URLs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        self._url_store.clear_all()
        self._refresh_saved_urls([])
        self._set_status("Cleared all saved stream URLs.", "success")

    def _current_output_dir(self) -> Path | None:
        if not self._sync_output_dir_from_store(show_status=True):
            return None
        return self._output_dir

    def _handle_preview(self) -> None:
        video_url = self._current_video_url()
        if not video_url:
            return

        self._clear_output_action()
        blocked = self._mark_url_as_used(video_url)
        history_hint = self._history_hint_suffix(blocked)
        self._set_status(f"Loading preview frame...{history_hint}")

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
            self._set_status(f"Preview updated.{history_hint}", "success")

        def on_failure(error_text: str) -> None:
            self._set_status(f"Preview failed: {error_text}{history_hint}", "error")

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

        output_dir = self._current_output_dir()
        if output_dir is None:
            return

        self._clear_output_action()
        blocked = self._mark_url_as_used(video_url)
        history_hint = self._history_hint_suffix(blocked)
        self._set_status(f"Capturing snapshot...{history_hint}")

        def on_success(result: object) -> None:
            output_path = str(result)
            self._set_output_action(output_path)
            self._set_status(f"Snapshot saved: {output_path}{history_hint}", "success")
            self._notify("Snapshot complete", output_path)

        def on_failure(error_text: str) -> None:
            self._set_status(f"Snapshot failed: {error_text}{history_hint}", "error")
            self._notify("Snapshot failed", error_text)

        self._start_task(lambda: capture_snapshot(video_url, output_dir=output_dir), on_success, on_failure)

    def _handle_record(self) -> None:
        if self.record_button.text() == "Recording...":
            self._set_status("A recording is already in progress.", "error")
            return

        video_url = self._current_video_url()
        if not video_url:
            return

        output_dir = self._current_output_dir()
        if output_dir is None:
            return

        self._clear_output_action()
        duration_seconds = int(self.duration_select.currentText())
        blocked = self._mark_url_as_used(video_url)
        self._active_recording_history_hint = self._history_hint_suffix(blocked)
        self._set_recording_ui_state(True)
        self._recording_end_ms = QDateTime.currentMSecsSinceEpoch() + (duration_seconds * 1000)
        self._recording_timer.start()
        self._notify("Recording started", f"Recording clip for {duration_seconds} seconds.")

        def on_success(result: object) -> None:
            output_path = str(result)
            self._recording_timer.stop()
            self._set_recording_ui_state(False)
            self._set_output_action(output_path)
            self._set_status(
                f"Recording complete: {output_path}{self._active_recording_history_hint}",
                "success",
            )
            self._active_recording_history_hint = ""
            self._notify("Recording complete", output_path)

        def on_failure(error_text: str) -> None:
            self._recording_timer.stop()
            self._set_recording_ui_state(False)
            self._set_status(
                f"Recording failed: {error_text}{self._active_recording_history_hint}",
                "error",
            )
            self._active_recording_history_hint = ""
            self._notify("Recording failed", error_text)

        started = self._start_task(
            lambda: record_clip(video_url, clip_seconds=duration_seconds, output_dir=output_dir),
            on_success,
            on_failure,
        )
        if not started:
            self._recording_timer.stop()
            self._set_recording_ui_state(False)
            self._active_recording_history_hint = ""

    def _set_recording_ui_state(self, active: bool) -> None:
        self.record_button.setText("Recording..." if active else "Record Clip")
        self.record_button.setEnabled(not active)
        self.duration_select.setEnabled(not active)
        self.preview_button.setEnabled(not active)
        self.snapshot_button.setEnabled(not active)

    def _render_recording_status(self) -> None:
        remaining_ms = max(0, self._recording_end_ms - QDateTime.currentMSecsSinceEpoch())
        remaining_seconds = max(0, (remaining_ms + 999) // 1000)
        self._set_status(
            f"Recording in progress... {remaining_seconds}s remaining.{self._active_recording_history_hint}",
            "recording",
        )
        if remaining_ms <= 0:
            self._recording_timer.stop()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._render_preview_pixmap()
