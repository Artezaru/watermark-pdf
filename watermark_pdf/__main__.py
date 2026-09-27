"""
watermark-pdf - Qt-GUI python based to add watermark on PDFs.
Copyright (C) 2026 Artezaru, artezaru.github@proton.me

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication
from watermark_pdf.watermark_ui import WatermarkWindow, FONT_SUBSTITUTES, APP_NAME, ORG_NAME

def main() -> None:
    """
    Application entry point.

    Runs via ``python -m watermark`` (this module is ``bippass``'s
    ``__main__.py``) as well as any console-script entry point
    declared for the package (e.g. in ``pyproject.toml``, so a
    PyInstaller build's launcher can import and call this directly).
    """
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")

    for family, substitutes in FONT_SUBSTITUTES.items():
        QFont.insertSubstitutions(family, substitutes)

    window = WatermarkWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()