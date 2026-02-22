"""Entry point for the native PySide6 app shell."""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from native_app.ui.main_window import MainWindow


def _build_light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f3f6f9"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1f2a37"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1f2a37"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1f2a37"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#0a84ff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0a84ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    return palette


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MJPEG Capture Studio")
    app.setOrganizationName("mjpeg-desktop-app")
    app.setStyle("Fusion")
    app.setPalette(_build_light_palette())

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
