"""Simple QThread wrapper for running blocking callables."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class TaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, task: Callable[[], object], parent=None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            result = self._task()
        except Exception as error:  # noqa: BLE001 - surfaced as user-visible status.
            self.failed.emit(str(error))
            return
        self.succeeded.emit(result)

