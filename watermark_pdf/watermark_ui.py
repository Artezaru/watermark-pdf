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
from .__version__ import __version__

import math
import os
import sys
import threading
import time
from collections import OrderedDict
from importlib import resources
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QLocale,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QUrl,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from reportlab.lib.pagesizes import A3, A4, A5, legal, letter

try:  # optional: renders the PDF pages behind the watermark ("show source")
    import pypdfium2 as pdfium
except Exception:  # not installed, or its native library failed to load
    pdfium = None

from .pages import PageSelectionError, parse_pages, to_page_indices
from .translation import TRANSLATIONS
from .watermark import (
    DEFAULT_FONT,
    DestinationExistsError,
    WatermarkCancelled,
    WatermarkStyle,
    available_fonts,
    batch_watermark_directory,
    count_pdf_pages,
    get_page_size,
    path_key,
    register_font,
    text_block_outline,
    watermark_files,
)


# ============================================================================
# Configuration
# ============================================================================

RELEASES_URL = "https://github.com/Artezaru/watermark-pdf/releases"

APP_NAME = "PDF Watermark"
ORG_NAME = "Artezaru"
VERSION = __version__

LANGUAGES = {
    "English": "en",
    "Français": "fr",
    "Español": "es",
    "Italiano": "it",
    "Deutsch": "de",
}

# Page sizes in points, portrait.
PAGE_SIZES = {
    "A3": A3,
    "A4": A4,
    "A5": A5,
    "Letter": letter,
    "Legal": legal,
}

PRESET_COLORS = ["#000000", "#6B7280", "#DC2626", "#2563EB", "#16A34A", "#EA580C"]

FORBIDDEN_SUFFIX_CHARS = '<>:"/\\|?*'

DEFAULTS = {
    "columns": 3,
    "rows": 6,
    "margin": 0.0,
    "opacity": 10,        # percent
    "angle": 45,          # degrees
    "color": "#000000",
    "font": DEFAULT_FONT,
    "size": 12.0,         # points
}

# ============================================================================
# Theme
# ============================================================================

THEMES = {
    "light": {
        "bg": "#F4F5F7",
        "surface": "#FFFFFF",
        "surface_alt": "#F9FAFB",
        "input": "#FFFFFF",
        "border": "#E4E7EC",
        "border_strong": "#CDD2DA",
        "text": "#1F2937",
        "muted": "#6B7280",
        "disabled": "#A3AAB5",
        "hover": "#F2F4F7",
        "pressed": "#E8EBF0",
        "accent": "#4F46E5",
        "accent_hover": "#4338CA",
        "accent_pressed": "#3730A3",
        "accent_soft": "#EEF2FF",
        "accent_disabled": "#A5B4FC",
        "success": "#15803D",
        "danger": "#DC2626",
        "canvas": "#E9ECF1",
        "scroll": "#CDD2DA",
        "log_bg": "#0F172A",
        "log_text": "#CBD5E1",
    },
    "dark": {
        "bg": "#0F1115",
        "surface": "#181B21",
        "surface_alt": "#1D2128",
        "input": "#12151A",
        "border": "#2A2F38",
        "border_strong": "#3A404B",
        "text": "#E6E8EC",
        "muted": "#9AA3AF",
        "disabled": "#5B6270",
        "hover": "#222630",
        "pressed": "#2A2F3A",
        "accent": "#6366F1",
        "accent_hover": "#7C7FF5",
        "accent_pressed": "#5558E3",
        "accent_soft": "#23264A",
        "accent_disabled": "#3B3E73",
        "success": "#4ADE80",
        "danger": "#F87171",
        "canvas": "#0B0D10",
        "scroll": "#3A404B",
        "log_bg": "#0B0D10",
        "log_text": "#CBD5E1",
    },
}

STYLESHEET = """
QWidget { color: %(text)s; font-size: 13px; }
QMainWindow, QWidget#root { background: %(bg)s; }

QLabel#appTitle { font-size: 20px; font-weight: 600; }
QLabel#appSubtitle { color: %(muted)s; }
QLabel#fieldLabel { color: %(muted)s; }
QLabel#hint { color: %(muted)s; font-size: 12px; }
QLabel#outputPath { color: %(muted)s; font-size: 12px; }
QLabel#outputPath[state="warn"] { color: %(danger)s; }
QLabel#status { color: %(muted)s; }
QLabel#status[state="ok"] { color: %(success)s; }
QLabel#status[state="error"] { color: %(danger)s; }

QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 12px; }
QLabel#cardTitle { color: %(muted)s; font-size: 11px; font-weight: 700; letter-spacing: 1px; }

QPlainTextEdit#textEdit, QLineEdit {
    background: %(input)s; border: 1px solid %(border)s; border-radius: 8px;
    padding: 6px 8px; selection-background-color: %(accent)s; selection-color: white;
}
QPlainTextEdit#textEdit { font-size: 15px; font-weight: 600; }
QPlainTextEdit#textEdit:focus, QLineEdit:focus { border: 1px solid %(accent)s; }

QComboBox {
    background: %(input)s; border: 1px solid %(border)s; border-radius: 8px;
    padding: 5px 10px; min-height: 22px;
}
QComboBox:hover { border-color: %(border_strong)s; }
QComboBox:focus { border-color: %(accent)s; }
QComboBox:disabled { color: %(disabled)s; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: url(%(arrow)s);
    width: 10px; height: 6px;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: %(surface)s; border: 1px solid %(border)s; padding: 4px; outline: 0;
    selection-background-color: %(accent_soft)s; selection-color: %(text)s;
}

QWidget#stepper { background: %(input)s; border: 1px solid %(border)s; border-radius: 8px; }
QAbstractSpinBox#stepSpin { background: transparent; border: none; padding: 5px 0; }
QToolButton#stepBtn {
    background: transparent; border: none; border-radius: 6px;
    color: %(muted)s; font-size: 16px; min-width: 28px; min-height: 26px;
}
QToolButton#stepBtn:hover { background: %(hover)s; color: %(accent)s; }
QToolButton#stepBtn:pressed { background: %(pressed)s; }

QSlider::groove:horizontal { height: 4px; background: %(border)s; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
QSlider::handle:horizontal {
    background: %(surface)s; border: 2px solid %(accent)s;
    width: 12px; height: 12px; margin: -6px 0; border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: %(accent_soft)s; }
QLabel#sliderValue { font-weight: 600; min-width: 42px; }

QPushButton {
    background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px;
    padding: 7px 14px; font-weight: 500;
}
QPushButton:hover { background: %(hover)s; border-color: %(border_strong)s; }
QPushButton:pressed { background: %(pressed)s; }
QPushButton:disabled { color: %(disabled)s; }

QPushButton#primary {
    background: %(accent)s; border: 1px solid %(accent)s; color: white;
    font-weight: 600; padding: 9px 26px;
}
QPushButton#primary:hover { background: %(accent_hover)s; border-color: %(accent_hover)s; }
QPushButton#primary:pressed { background: %(accent_pressed)s; }
QPushButton#primary:disabled {
    background: %(accent_disabled)s; border-color: %(accent_disabled)s; color: rgba(255,255,255,170);
}

QPushButton#ghost, QToolButton#ghost {
    background: transparent; border: none; border-radius: 8px; color: %(muted)s; padding: 6px 10px;
}
QPushButton#ghost:hover, QToolButton#ghost:hover { background: %(hover)s; color: %(text)s; }
QPushButton#ghost:checked { color: %(accent)s; }

QPushButton[seg="first"], QPushButton[seg="last"] { padding: 5px 12px; }
QPushButton[seg="first"] { border-top-right-radius: 0; border-bottom-right-radius: 0; }
QPushButton[seg="last"] { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none; }
QPushButton[seg="first"]:checked, QPushButton[seg="last"]:checked {
    background: %(accent_soft)s; color: %(accent)s; font-weight: 600;
}

QFrame#dropZone {
    background: %(surface_alt)s; border: 2px dashed %(border_strong)s; border-radius: 12px;
}
QFrame#dropZone[active="true"] { background: %(accent_soft)s; border-color: %(accent)s; }
QLabel#dropTitle { font-weight: 600; }

QFrame#selection { background: %(surface_alt)s; border: 1px solid %(border)s; border-radius: 10px; }
QLabel#badge {
    background: %(accent_soft)s; color: %(accent)s; border-radius: 8px;
    font-size: 11px; font-weight: 700; padding: 8px 6px;
}
QLabel#selName { font-weight: 600; }
QFrame#fileRow { background: %(surface_alt)s; border: 1px solid %(border)s; border-radius: 10px; }
QFrame#fileRow[current="true"] { border: 1px solid %(accent)s; }
QLabel#rowNumber { color: %(accent)s; font-weight: 700; min-width: 22px; }
QLabel#folderItem { color: %(muted)s; font-size: 12px; }
QLabel#folderItem[current="true"] { color: %(accent)s; font-weight: 600; }
QLineEdit#pagesEdit { padding: 3px 8px; border-radius: 6px; }
QLineEdit#pagesEdit[invalid="true"] { border: 1px solid %(danger)s; }
QLabel#selMeta { color: %(muted)s; font-size: 12px; }

QFrame#actionBar { background: %(surface)s; border-top: 1px solid %(border)s; }
QProgressBar { background: %(border)s; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: %(accent)s; border-radius: 2px; }

QPlainTextEdit#log {
    background: %(log_bg)s; color: %(log_text)s; border: 1px solid %(border)s; border-radius: 10px;
    padding: 6px; font-size: 12px;
    font-family: "JetBrains Mono", "Cascadia Mono", Consolas, Menlo, "DejaVu Sans Mono", monospace;
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget#scrollInner { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: %(scroll)s; border-radius: 3px; min-height: 32px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { height: 0; }

QSplitter::handle { background: transparent; }
QToolTip {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: 6px; padding: 4px 8px;
}
"""


def _make_app_icon() -> QIcon:
    """Application icon, read from the package resources (``resources/app.png``)."""
    data = (resources.files(__package__) / "resources" / "app.png").read_bytes()
    pixmap = QPixmap()
    pixmap.loadFromData(data, "PNG")
    return QIcon(pixmap)


def _apply_palette(app: QApplication, colors: dict) -> None:
    """Fusion palette, so that native dialogs follow the theme too."""
    pal = QPalette()
    c = {k: QColor(v) for k, v in colors.items() if isinstance(v, str) and v.startswith("#")}
    pal.setColor(QPalette.Window, c["bg"])
    pal.setColor(QPalette.WindowText, c["text"])
    pal.setColor(QPalette.Base, c["input"])
    pal.setColor(QPalette.AlternateBase, c["surface_alt"])
    pal.setColor(QPalette.Text, c["text"])
    pal.setColor(QPalette.Button, c["surface"])
    pal.setColor(QPalette.ButtonText, c["text"])
    pal.setColor(QPalette.Highlight, c["accent"])
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ToolTipBase, c["surface"])
    pal.setColor(QPalette.ToolTipText, c["text"])
    pal.setColor(QPalette.Link, c["accent"])
    pal.setColor(QPalette.Mid, c["border_strong"])
    if hasattr(QPalette, "PlaceholderText"):
        pal.setColor(QPalette.PlaceholderText, c["muted"])
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c["disabled"])
    app.setPalette(pal)


# ============================================================================
# Preview drawing (Qt) -- same geometry as watermark._draw_watermark_grid
# ============================================================================

_OUTLINE_CACHE: dict = {}


def outline_path(style: WatermarkStyle) -> QPainterPath:
    """Text block of the watermark as a Qt path: the very same outlines as
    in the PDF (centered on the origin, points, y axis pointing *up*)."""
    key = (style.font, style.size, tuple(style.lines))
    path = _OUTLINE_CACHE.get(key)
    if path is None:
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        for operator, points in text_block_outline(style):
            if operator == "moveTo":
                path.moveTo(*points[0])
            elif operator == "lineTo":
                path.lineTo(*points[0])
            elif operator == "curveTo":
                path.cubicTo(*points[0], *points[1], *points[2])
            else:
                path.closeSubpath()
        if len(_OUTLINE_CACHE) > 32:
            _OUTLINE_CACHE.clear()
        _OUTLINE_CACHE[key] = path
    return path


def draw_watermark(
    painter: QPainter,
    width: float,
    height: float,
    style: WatermarkStyle,
    guides_color: Optional[QColor] = None,
) -> None:
    """Draw the watermark in *page coordinates* (points, origin top-left).

    The caller is responsible for scaling points to pixels. The glyph
    outlines come from the same font files as the PDF: the preview is exact.
    """
    centers = list(style.cell_centers(width, height))  # validates the margin

    if guides_color is not None:
        margin = style.margin_size
        pen = QPen(guides_color, 0, Qt.DashLine)       # cosmetic 1px
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        inner = QRectF(margin, margin, width - 2 * margin, height - 2 * margin)
        painter.drawRect(inner)
        step_x = inner.width() / style.horizontal_boxes
        step_y = inner.height() / style.vertical_boxes
        for i in range(1, style.horizontal_boxes):
            x = inner.left() + i * step_x
            painter.drawLine(QPointF(x, inner.top()), QPointF(x, inner.bottom()))
        for j in range(1, style.vertical_boxes):
            y = inner.top() + j * step_y
            painter.drawLine(QPointF(inner.left(), y), QPointF(inner.right(), y))

    color = QColor(style.color)
    color.setAlphaF(style.opacity)
    brush = QBrush(color)
    path = outline_path(style)

    painter.setPen(Qt.NoPen)
    for x, y in centers:
        painter.save()
        painter.translate(x, height - y)           # PDF y goes up, Qt y goes down
        painter.rotate(-style.angle)               # PDF angles are counter-clockwise
        painter.scale(1, -1)                       # the outline's y axis points up
        painter.fillPath(path, brush)
        painter.restore()


# ============================================================================
# Small widgets
# ============================================================================

class ToggleSwitch(QAbstractButton):
    """Animated on/off switch with an optional label on its right."""

    colors = {"on": QColor("#4F46E5"), "off": QColor("#CDD2DA"), "text": QColor("#1F2937")}

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = pyqtProperty(float, fget=_get_offset, fset=_set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt API)
        super().setChecked(checked)
        if not self.isVisible():
            self._anim.stop()
            self._set_offset(1.0 if checked else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        text_w = self.fontMetrics().horizontalAdvance(self.text()) if self.text() else 0
        return QSize(36 + (10 + text_w if text_w else 0), 22)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        track = QRectF(0, (self.height() - 20) / 2, 36, 20)
        on, off = self.colors["on"], self.colors["off"]
        t = self._offset
        mixed = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(mixed)
        p.drawRoundedRect(track, 10, 10)
        p.setBrush(QColor("white"))
        knob_x = track.left() + 2 + t * 16
        p.drawEllipse(QRectF(knob_x, track.top() + 2, 16, 16))
        if self.text():
            p.setPen(self.colors["text"])
            p.drawText(QRectF(46, 0, self.width() - 46, self.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class Stepper(QWidget):
    """[-] value [+] control wrapping a QSpinBox / QDoubleSpinBox."""

    def __init__(self, spin: QAbstractSpinBox, parent=None):
        super().__init__(parent)
        self.setObjectName("stepper")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.spin = spin
        spin.setObjectName("stepSpin")
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignCenter)
        spin.setKeyboardTracking(False)

        minus = QToolButton(text="−", objectName="stepBtn")
        plus = QToolButton(text="+", objectName="stepBtn")
        for button in (minus, plus):
            button.setAutoRepeat(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
        minus.clicked.connect(spin.stepDown)
        plus.clicked.connect(spin.stepUp)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        layout.addWidget(minus)
        layout.addWidget(spin, 1)
        layout.addWidget(plus)


class ValueSlider(QWidget):
    """Horizontal slider with its formatted value on the right."""

    valueChanged = pyqtSignal(int)

    def __init__(self, minimum: int, maximum: int, fmt: str, page_step: int = 5, parent=None):
        super().__init__(parent)
        self._fmt = fmt
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setPageStep(page_step)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.label = QLabel(objectName="sliderValue")
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)

        self.slider.valueChanged.connect(self._changed)
        self._changed(self.slider.value())

    def _changed(self, value: int) -> None:
        self.label.setText(self._fmt.format(value))
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:  # noqa: N802
        self.slider.setValue(int(value))


class SwatchButton(QAbstractButton):
    """Round color chip. ``color=None`` draws the 'custom color' chip."""

    ring = QColor("#1F2937")

    def __init__(self, color: Optional[str], parent=None):
        super().__init__(parent)
        self.color = color
        self.custom_color: Optional[str] = None
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(28, 28)
        if color:
            self.setToolTip(color.upper())

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        inner = QRectF(5, 5, 18, 18)
        if self.color is None:
            if self.custom_color and self.isChecked():
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(self.custom_color))
                p.drawEllipse(inner)
            else:
                gradient = QConicalGradient(inner.center(), 90)
                for i, hue in enumerate(range(0, 361, 60)):
                    gradient.setColorAt(i / 6, QColor.fromHsv(hue % 360, 190, 235))
                p.setPen(Qt.NoPen)
                p.setBrush(gradient)
                p.drawEllipse(inner)
        else:
            p.setPen(QPen(QColor(0, 0, 0, 40), 1))
            p.setBrush(QColor(self.color))
            p.drawEllipse(inner)
        if self.isChecked() or self.underMouse():
            ring = QColor(self.ring)
            if not self.isChecked():
                ring.setAlpha(80)
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(1.5, 1.5, 25, 25))
        p.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)


class ColorPicker(QWidget):
    """Row of preset color chips plus a custom color chip."""

    colorChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = DEFAULTS["color"]
        self.custom_title = "Custom color"
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._presets: list[SwatchButton] = []
        for hex_color in PRESET_COLORS:
            chip = SwatchButton(hex_color)
            chip.clicked.connect(lambda _=False, c=hex_color: self.setColor(c, emit=True))
            self._group.addButton(chip)
            self._presets.append(chip)
            layout.addWidget(chip)
        self._custom = SwatchButton(None)
        self._custom.clicked.connect(self._pick_custom)
        self._group.addButton(self._custom)
        layout.addWidget(self._custom)
        layout.addStretch()
        self.setColor(self._color)

    def color(self) -> str:
        return self._color

    def setColor(self, hex_color: str, emit: bool = False) -> None:  # noqa: N802
        qcolor = QColor(hex_color)
        if not qcolor.isValid():
            return
        self._color = qcolor.name().upper()
        for chip in self._presets:
            if chip.color.upper() == self._color:
                chip.setChecked(True)
                break
        else:
            self._custom.custom_color = self._color
            self._custom.setToolTip(self._color)
            self._custom.setChecked(True)
        for chip in self._presets + [self._custom]:
            chip.update()
        if emit:
            self.colorChanged.emit(self._color)

    def _pick_custom(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, self.custom_title)
        if color.isValid():
            self.setColor(color.name(), emit=True)
        else:
            self.setColor(self._color)  # restore the checked chip


class Card(QFrame):
    """Rounded panel with a small uppercase title."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 18, 18)
        self.body.setSpacing(12)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.title = QLabel(objectName="cardTitle")
        self.header.addWidget(self.title)
        self.header.addStretch()
        self.body.addLayout(self.header)

    def setTitle(self, text: str) -> None:  # noqa: N802
        self.title.setText(text.upper())


class DropIcon(QWidget):
    """Tray-with-arrow icon of the drop zone."""

    color = QColor("#4F46E5")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self.color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        tray = QPainterPath(QPointF(5, 20))
        tray.lineTo(5, 28)
        tray.lineTo(29, 28)
        tray.lineTo(29, 20)
        p.drawPath(tray)
        p.drawLine(QPointF(17, 5), QPointF(17, 21))
        arrow = QPainterPath(QPointF(11, 15))
        arrow.lineTo(17, 21)
        arrow.lineTo(23, 15)
        p.drawPath(arrow)
        p.end()


class DropZone(QFrame):
    """Dashed area accepting a dropped PDF / folder, with browse buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setProperty("active", False)

        self.icon = DropIcon()
        self.title = QLabel(objectName="dropTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.or_label = QLabel(objectName="hint")
        self.or_label.setAlignment(Qt.AlignCenter)
        self.file_button = QPushButton()
        self.folder_button = QPushButton()
        for button in (self.file_button, self.folder_button):
            button.setCursor(Qt.PointingHandCursor)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.file_button, 1)
        buttons.addWidget(self.folder_button, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addWidget(self.icon, 0, Qt.AlignHCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.or_label)
        layout.addSpacing(2)
        layout.addLayout(buttons)

    def setActive(self, active: bool) -> None:  # noqa: N802
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class SelectionChip(QFrame):
    """Shows the selected file / folder with a clear button."""

    cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("selection")
        self.badge = QLabel(objectName="badge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setFixedWidth(44)
        self.name = QLabel(objectName="selName")
        self.name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.name.setMinimumWidth(40)
        self.meta = QLabel(objectName="selMeta")
        self.clear_button = QToolButton(text="✕", objectName="ghost")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.cleared.emit)
        self._full_name = ""

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(self.name)
        texts.addWidget(self.meta)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        layout.setSpacing(10)
        layout.addWidget(self.badge)
        layout.addLayout(texts, 1)
        layout.addWidget(self.clear_button, 0, Qt.AlignTop)

    def set_content(self, badge: str, name: str, meta: str, tooltip: str) -> None:
        self.badge.setText(badge)
        self._full_name = name
        self.meta.setText(meta)
        self.setToolTip(tooltip)
        self._elide()

    def _elide(self) -> None:
        width = max(60, self.name.width())
        self.name.setText(self.name.fontMetrics().elidedText(self._full_name, Qt.ElideMiddle, width))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()


def repolish(widget: QWidget) -> None:
    """Re-apply the style sheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_flag(widget: QWidget, name: str, value: bool) -> None:
    """Set a boolean dynamic property used by the style sheet."""
    if widget.property(name) != value:
        widget.setProperty(name, value)
        repolish(widget)


class SourceRenderer:
    """Renders PDF pages as images (pypdfium2), with a small cache.

    The resolution is rounded up to a power of two, so zooming in re-renders
    only from time to time, and capped to keep memory reasonable.
    """

    MAX_SIDE = 4096
    CACHE_SIZE = 8
    _FORMATS = {
        "RGB": QImage.Format_RGB888,
        "RGBA": QImage.Format_RGBA8888,
        "RGBX": QImage.Format_RGBX8888,
        "L": QImage.Format_Grayscale8,
    }

    def __init__(self):
        self._cache: "OrderedDict[tuple, QImage]" = OrderedDict()

    @staticmethod
    def available() -> bool:
        return pdfium is not None

    def render(self, path: Path, index: int, long_side_px: float) -> QImage:
        """Page ``index`` (0-based) of ``path`` as displayed by PDF readers
        (crop box and rotation applied), about ``long_side_px`` pixels long."""
        if pdfium is None:
            raise RuntimeError("pypdfium2 is not installed")
        target = min(self.MAX_SIDE, 2 ** math.ceil(math.log2(max(256.0, long_side_px))))
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = 0
        key = (path_key(path), index, mtime, target)
        image = self._cache.get(key)
        if image is not None:
            self._cache.move_to_end(key)
            return image

        document = pdfium.PdfDocument(str(path))
        try:
            page = document[index]
            width, height = page.get_size()
            bitmap = page.render(scale=target / max(width, height), rev_byteorder=True)
            image_format = self._FORMATS[bitmap.mode]
            image = QImage(bytes(bitmap.buffer), bitmap.width, bitmap.height,
                           bitmap.stride, image_format).copy()   # own the pixels
        finally:
            document.close()

        self._cache[key] = image
        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)
        return image


def set_invalid(edit: QLineEdit, message: Optional[str], tooltip: str) -> None:
    """Red border + error tooltip on a line edit (``message=None``: valid)."""
    invalid = message is not None
    if edit.property("invalid") != invalid:
        edit.setProperty("invalid", invalid)
        edit.style().unpolish(edit)
        edit.style().polish(edit)
    edit.setToolTip(message if invalid else tooltip)


class ElidedLabel(QLabel):
    """Label shortening its text with "…" in the middle when too narrow."""

    def __init__(self, parent=None, objectName: str = ""):  # noqa: N803 (Qt style)
        super().__init__(parent, objectName=objectName)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(40)
        self._full_text = ""

    def setFullText(self, text: str) -> None:  # noqa: N802
        self._full_text = text
        self._elide()

    def _elide(self) -> None:
        width = max(60, self.width())
        self.setText(self.fontMetrics().elidedText(self._full_text, Qt.ElideMiddle, width))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()


class FileRow(QFrame):
    """One selected PDF: name, page count, page selection, remove button."""

    removed = pyqtSignal(object)
    changed = pyqtSignal()

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("fileRow")
        self.path = path
        self.page_count: Optional[int] = None
        self.page_size: Optional[tuple[float, float]] = None
        self.read_error: Optional[str] = None
        try:
            self.page_count = count_pdf_pages(path)
            self.page_size = get_page_size(path)
        except Exception as exc:  # unreadable / password-protected PDF
            self.read_error = f"{type(exc).__name__}: {exc}"

        self.number = QLabel(objectName="rowNumber")
        self.name = ElidedLabel(objectName="selName")
        self.name.setFullText(path.name)
        self.meta = QLabel(objectName="selMeta")
        self.pages_label = QLabel(objectName="selMeta")
        self.pages_edit = QLineEdit(objectName="pagesEdit")
        self.pages_edit.setMinimumWidth(130)
        self.pages_edit.textChanged.connect(lambda _text: self.changed.emit())
        self.remove_button = QToolButton(text="✕", objectName="ghost")
        self.remove_button.setCursor(Qt.PointingHandCursor)
        self.remove_button.clicked.connect(lambda: self.removed.emit(self))
        # Full path on hover (the name, number and row itself).
        for widget in (self, self.number, self.name):
            widget.setToolTip(str(path))

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(self.number)
        top.addWidget(self.name, 1)
        top.addWidget(self.remove_button)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.addWidget(self.meta)
        bottom.addStretch()
        bottom.addWidget(self.pages_label)
        bottom.addWidget(self.pages_edit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 8)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addLayout(bottom)

    def set_number(self, number: int) -> None:
        self.number.setText(f"{number}.")

    def page_selection(self) -> Optional[list[int]]:
        """1-based pages typed by the user (``None`` = all); raises
        :class:`PageSelectionError`. Pages beyond the end of the PDF are
        allowed: they are simply ignored."""
        return parse_pages(self.pages_edit.text())

    def retranslate(self, t) -> None:
        if self.page_count is not None:
            self.meta.setText(t("pages_count", n=self.page_count))
        else:
            self.meta.setText("⚠ " + t("unreadable_pdf"))
        self.meta.setToolTip(f"{self.path}\n{self.read_error}" if self.read_error else str(self.path))
        self.pages_label.setText(t("pages"))
        self.pages_edit.setPlaceholderText(t("pages_placeholder"))
        self.remove_button.setToolTip(t("remove_file"))


class PreviewCanvas(QWidget):
    """Draws a page and its watermark, scaled to fit, crisp at any size."""

    colors = {"canvas": QColor("#E9ECF1"), "muted": QColor("#6B7280"), "accent": QColor("#4F46E5")}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.page_size: Optional[tuple[float, float]] = A4
        self.caption = ""
        self.text = ""
        self.options: dict = {}
        self.guides = False
        self.source = None            # callable(long_side_px) -> QImage, or None
        self.watermarked = True       # False: page outside the page selection
        self.empty_message = ""
        self.no_page_message = ""
        self.error_title = "Error"
        self.source_error_title = "Error"
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self._drag_origin = None
        self.setCursor(Qt.OpenHandCursor)

    def set_config(self, page_size, caption: str, text: str, options: dict, guides: bool,
                   source=None, watermarked: bool = True) -> None:
        """``page_size=None`` shows no page at all (Auto mode without PDF)."""
        self.page_size = page_size
        self.caption = caption
        self.text = text
        self.options = options
        self.guides = guides
        self.source = source
        self.watermarked = watermarked
        self.update()

    def _view_center(self) -> QPointF:
        return QPointF(self.width() / 2, (self.height() - 26.0) / 2)

    def reset_view(self) -> None:
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        steps = event.angleDelta().y() / 120
        new_zoom = min(20.0, max(1.0, self.zoom * 1.15 ** steps))
        if new_zoom == 1.0:
            self.reset_view()
            return
        # Keep the point under the cursor fixed.
        cursor = QPointF(event.pos())
        center = self._view_center() + self.pan
        k = new_zoom / self.zoom
        self.pan = cursor - (cursor - center) * k - self._view_center()
        self.zoom = new_zoom
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.zoom > 1.0:
            self._drag_origin = (QPointF(event.pos()), QPointF(self.pan))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None:
            start, pan = self._drag_origin
            self.pan = pan + QPointF(event.pos()) - start
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_origin = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.reset_view()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing
                         | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), self.colors["canvas"])

        if self.page_size is None:            # nothing to preview yet
            p.setPen(self.colors["muted"])
            p.drawText(QRectF(self.rect()).adjusted(40, 40, -40, -40),
                       Qt.AlignCenter | Qt.TextWordWrap, self.no_page_message)
            p.end()
            return

        page_w, page_h = float(self.page_size[0]), float(self.page_size[1])
        pad, caption_h = 28.0, 26.0
        scale = min((self.width() - 2 * pad) / page_w,
                    (self.height() - 2 * pad - caption_h) / page_h)
        scale = max(scale, 0.05) * self.zoom
        w, h = page_w * scale, page_h * scale
        page = QRectF((self.width() - w) / 2 + self.pan.x(),
                      (self.height() - caption_h - h) / 2 + self.pan.y(), w, h)
        
        # Soft shadow + paper.
        p.setPen(Qt.NoPen)
        for i in range(1, 9):
            p.setBrush(QColor(0, 0, 0, max(0, 14 - i * 2)))
            p.drawRoundedRect(page.adjusted(-i, -i + 3, i, i + 3), 3 + i, 3 + i)
        p.setBrush(QColor("white"))
        p.drawRect(page)

        # Content of the PDF page ("show source").
        source_error = None
        if self.source is not None:
            try:
                ratio = self.devicePixelRatioF()
                image = self.source(max(page.width(), page.height()) * ratio)
                p.drawImage(page, image)
            except Exception as exc:  # unreadable page, password, missing library...
                source_error = f"{type(exc).__name__}: {exc}"

        # Caption under the page.
        p.setPen(self.colors["muted"])
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, self.font().pointSizeF() - 1))
        p.setFont(small)
        p.drawText(QRectF(0, page.bottom() + 8, self.width(), caption_h),
                   Qt.AlignHCenter | Qt.AlignTop, self.caption)

        if source_error:
            p.setPen(QColor("#DC2626"))
            p.drawText(page.adjusted(24, 24, -24, -24), Qt.AlignTop | Qt.AlignHCenter
                       | Qt.TextWordWrap, f"{self.source_error_title}\n{source_error}")

        if not self.text.strip():
            if self.source is None:
                p.setPen(QColor("#9CA3AF"))
                p.drawText(page.adjusted(24, 24, -24, -24), Qt.AlignCenter | Qt.TextWordWrap,
                           self.empty_message)
            p.end()
            return
        if not self.watermarked and not self.guides:
            p.end()
            return

        p.save()
        p.setClipRect(page)
        p.translate(page.topLeft())
        p.scale(scale, scale)
        try:
            style = WatermarkStyle(text=self.text, **self.options)
            guides = QColor(self.colors["accent"]) if self.guides else None
            if guides is not None:
                guides.setAlpha(110)
            if self.watermarked:
                draw_watermark(p, page_w, page_h, style, guides)
            elif guides is not None:     # page not watermarked: grid only
                draw_watermark(p, page_w, page_h, style.__class__(
                    text=style.text, **{**self.options, "opacity": 0.0}), guides)
            error = None
        except Exception as exc:  # invalid settings: show the reason on the page
            error = str(exc)
        p.restore()

        if error:
            p.setPen(QColor("#DC2626"))
            p.setFont(self.font())
            p.drawText(page.adjusted(24, 24, -24, -24), Qt.AlignCenter | Qt.TextWordWrap,
                       f"{self.error_title}\n\n{error}")
        p.end()


# ============================================================================
# Worker
# ============================================================================

class WatermarkWorker(QThread):
    """Run the generation in a background thread.

    ``kind="files"``: ``files`` maps each PDF to its 0-based page indices
    (``None`` = all). ``kind="folder"``: every PDF of ``folder`` gets
    ``pages``.
    """

    progress = pyqtSignal(int, int, str)
    # status: "ok" | "exists" | "cancelled" | "error", payload
    completed = pyqtSignal(str, object)

    def __init__(self, kind: str, text: str, suffix: str, overwrite: bool, options: dict,
                 files: Optional[dict] = None, folder: Optional[Path] = None,
                 pages: Optional[list[int]] = None, recursive: bool = False, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.text = text
        self.suffix = suffix
        self.overwrite = overwrite
        self.options = options
        self.files = files or {}
        self.folder = folder
        self.pages = pages
        self.recursive = recursive
        self._cancel = threading.Event()
        self._last_emit = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    def _on_progress(self, done: int, total: int, name: str) -> None:
        now = time.monotonic()
        if done >= total or now - self._last_emit > 0.03:   # max ~30 updates/s
            self._last_emit = now
            self.progress.emit(done, total, name)

    def run(self) -> None:
        common = dict(
            suffix=self.suffix, overwrite=self.overwrite, verbose=False,
            progress_callback=self._on_progress, cancel_event=self._cancel,
            **self.options,
        )
        try:
            if self.kind == "files":
                results = watermark_files(self.files, self.text, **common)
            else:
                results = batch_watermark_directory(
                    self.folder, self.text, recursive=self.recursive, pages=self.pages,
                    **common,
                )
            self.completed.emit("ok", results)
        except WatermarkCancelled:
            self.completed.emit("cancelled", None)
        except DestinationExistsError as exc:   # created after the check
            self.completed.emit("exists", exc.paths)
        except Exception as exc:
            self.completed.emit("error", f"{type(exc).__name__}: {exc}")


# ============================================================================
# Main window
# ============================================================================

class WatermarkWindow(QMainWindow):
    """Main PDF watermark application."""

    def __init__(self):
        super().__init__()
        # Nothing is ever written to disk: every run starts from the defaults
        # (language = system language, falling back to English).
        self.language = self._initial_language()
        self.theme = "light"

        self.input_kind: Optional[str] = None       # None | "files" | "folder"
        self.input_path: Optional[Path] = None      # folder mode only
        self.file_rows: list[FileRow] = []          # files mode only
        self.folder_files: list[Path] = []          # folder mode only

        # Preview (Auto mode): the previewed PDF is tracked by its path key, so
        # it stays the same when other PDFs are added or removed.
        self.renderer = SourceRenderer()
        self.preview_key: Optional[str] = None
        self._preview_page_key: Optional[str] = None   # PDF the page spin refers to
        self._doc_cache: dict = {}                     # (key, mtime) -> page count
        self._size_cache: dict = {}                    # (key, mtime, index) -> size
        self._syncing = False
        self.last_output_dir: Optional[Path] = None
        self.worker: Optional[WatermarkWorker] = None
        self._status_key = ("status_ready", {})
        self._browse_dir = str(Path.home())         # remembered for this session only
        self._font_dir = self._default_font_dir()

        self.setWindowIcon(_make_app_icon())
        self.setAcceptDrops(True)
        self._build_ui()
        self._load_defaults()
        self._apply_theme()
        self._retranslate_ui()
        self._connect_live_preview()
        self._refresh_selection()
        self._refresh_preview()

    # ==================================================================
    # Translation
    # ==================================================================

    def _t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS.get(self.language, {}).get(key) or TRANSLATIONS["en"].get(key, key)
        return text.format(**kwargs) if kwargs else text

    @staticmethod
    def _initial_language() -> str:
        """System language if translated, English otherwise (nothing is saved)."""
        system = QLocale.system().name()[:2]
        return system if system in TRANSLATIONS else "en"

    # ==================================================================
    # UI construction
    # ==================================================================

    def _build_ui(self) -> None:
        self.setMinimumSize(1045, 650)
        self.resize(1100, 700)

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 4, 24, 16)
        body_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(16)
        splitter.addWidget(self._build_settings_panel())
        splitter.addWidget(self._build_preview_card())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([450, 820])
        body_layout.addWidget(splitter, 1)

        self.log = QPlainTextEdit(objectName="log")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        self.log.setVisible(False)
        body_layout.addWidget(self.log)

        root_layout.addWidget(body, 1)
        root_layout.addWidget(self._build_action_bar())

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.start_generation)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.select_files)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.cancel_generation)

    # ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(40, 40))
        layout.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_label = QLabel(objectName="appTitle")
        self.subtitle_label = QLabel(objectName="appSubtitle")
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        layout.addLayout(titles)
        layout.addStretch()

        # The updates button (text length depends on the language) is on the
        # left of the language list, so the list does not move when switching.
        self.update_button = QPushButton(objectName="ghost")
        self.update_button.setCursor(Qt.PointingHandCursor)
        self.update_button.clicked.connect(self.show_updates)
        layout.addWidget(self.update_button)

        self.language_combo = QComboBox()
        for label, code in LANGUAGES.items():
            self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.language)))
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        layout.addWidget(self.language_combo)

        self.theme_button = QToolButton(objectName="ghost")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setFixedSize(36, 34)
        self.theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_button)
        return header

    # ------------------------------------------------------------------
    def _build_settings_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(420)
        scroll.setMaximumWidth(530)

        inner = QWidget(objectName="scrollInner")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        # --- Text ------------------------------------------------------
        self.text_card = Card()
        self.text_edit = QPlainTextEdit(objectName="textEdit")
        self.text_edit.setFixedHeight(78)
        self.text_edit.setTabChangesFocus(True)
        self.text_hint = QLabel(objectName="hint")
        self.text_hint.setWordWrap(True)
        self.text_card.body.addWidget(self.text_edit)
        self.text_card.body.addWidget(self.text_hint)
        layout.addWidget(self.text_card)

        # --- Style -----------------------------------------------------
        self.style_card = Card()
        self.reset_button = QPushButton(objectName="ghost")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.clicked.connect(self._reset_style)
        self.style_card.header.addWidget(self.reset_button)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        self.font_combo = QComboBox()
        self.font_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.font_combo.setMinimumContentsLength(12)
        self._populate_fonts()
        self.add_font_button = QPushButton("+")
        self.add_font_button.setFixedWidth(36)
        self.add_font_button.setCursor(Qt.PointingHandCursor)
        self.add_font_button.clicked.connect(self.add_font)
        self.font_box = QWidget()
        font_layout = QHBoxLayout(self.font_box)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.setSpacing(6)
        font_layout.addWidget(self.font_combo, 1)
        font_layout.addWidget(self.add_font_button)

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(4, 300)
        self.size_spin.setDecimals(1)
        self.size_spin.setSingleStep(1)
        self.size_spin.setSuffix(" pt")
        self.size_stepper = Stepper(self.size_spin)

        self.color_picker = ColorPicker()
        self.opacity_slider = ValueSlider(0, 100, "{} %", page_step=5)
        self.angle_slider = ValueSlider(-180, 180, "{}°", page_step=15)

        self.font_label = QLabel(objectName="fieldLabel")
        self.size_label = QLabel(objectName="fieldLabel")
        self.color_label = QLabel(objectName="fieldLabel")
        self.opacity_label = QLabel(objectName="fieldLabel")
        self.angle_label = QLabel(objectName="fieldLabel")

        rows = [
            (self.font_label, self.font_box),
            (self.size_label, self.size_stepper),
            (self.color_label, self.color_picker),
            (self.opacity_label, self.opacity_slider),
            (self.angle_label, self.angle_slider),
        ]
        for row, (label, widget) in enumerate(rows):
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
        self.style_card.body.addLayout(grid)
        layout.addWidget(self.style_card)

        # --- Layout ----------------------------------------------------
        self.layout_card = Card()
        layout_grid = QGridLayout()
        layout_grid.setHorizontalSpacing(12)
        layout_grid.setVerticalSpacing(6)

        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 30)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 30)
        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(0, 200)
        self.margin_spin.setDecimals(0)
        self.margin_spin.setSingleStep(5)
        self.margin_spin.setSuffix(" pt")

        self.columns_label = QLabel(objectName="fieldLabel")
        self.rows_label = QLabel(objectName="fieldLabel")
        self.margin_label = QLabel(objectName="fieldLabel")
        for column, (label, spin) in enumerate(
            [(self.columns_label, self.columns_spin),
             (self.rows_label, self.rows_spin),
             (self.margin_label, self.margin_spin)]
        ):
            layout_grid.addWidget(label, 0, column)
            layout_grid.addWidget(Stepper(spin), 1, column)
            layout_grid.setColumnStretch(column, 1)
        self.layout_card.body.addLayout(layout_grid)
        layout.addWidget(self.layout_card)

        # --- Files -----------------------------------------------------
        self.files_card = Card()
        self.drop_zone = DropZone()
        self.drop_zone.file_button.clicked.connect(self.select_files)
        self.drop_zone.folder_button.clicked.connect(self.select_folder)

        # Files mode: one row per PDF, each with its own page selection.
        self.file_list = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list)
        self.file_list_layout.setContentsMargins(0, 0, 0, 0)
        self.file_list_layout.setSpacing(6)

        # Folder mode: one folder, one page selection for every PDF.
        self.selection_chip = SelectionChip()
        self.selection_chip.cleared.connect(self.clear_selection)
        self.folder_list = QWidget()
        self.folder_list_layout = QVBoxLayout(self.folder_list)
        self.folder_list_layout.setContentsMargins(10, 0, 4, 0)
        self.folder_list_layout.setSpacing(2)
        self.folder_pages = QWidget()
        folder_pages_layout = QGridLayout(self.folder_pages)
        folder_pages_layout.setContentsMargins(0, 0, 0, 0)
        folder_pages_layout.setHorizontalSpacing(10)
        folder_pages_layout.setVerticalSpacing(2)
        self.folder_pages_label = QLabel(objectName="fieldLabel")
        self.folder_pages_edit = QLineEdit(objectName="pagesEdit")
        self.folder_pages_edit.textChanged.connect(self._pages_changed)
        self.folder_pages_hint = QLabel(objectName="hint")
        self.folder_pages_hint.setWordWrap(True)
        folder_pages_layout.addWidget(self.folder_pages_label, 0, 0)
        folder_pages_layout.addWidget(self.folder_pages_edit, 0, 1)
        folder_pages_layout.addWidget(self.folder_pages_hint, 1, 1)
        folder_pages_layout.setColumnStretch(1, 1)
        self.recursive_switch = ToggleSwitch()
        self.recursive_switch.toggled.connect(self._refresh_selection)

        suffix_row = QHBoxLayout()
        suffix_row.setSpacing(10)
        self.suffix_label = QLabel(objectName="fieldLabel")
        self.suffix_edit = QLineEdit()
        self.suffix_edit.textChanged.connect(self._suffix_changed)
        suffix_row.addWidget(self.suffix_label)
        suffix_row.addWidget(self.suffix_edit, 1)

        self.overwrite_switch = ToggleSwitch()
        self.overwrite_switch.toggled.connect(self._update_output_label)

        self.output_label = QLabel(objectName="outputPath")
        self.output_label.setWordWrap(True)
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.files_card.body.addWidget(self.drop_zone)
        self.files_card.body.addWidget(self.file_list)
        self.files_card.body.addWidget(self.selection_chip)
        self.files_card.body.addWidget(self.folder_list)
        self.files_card.body.addWidget(self.folder_pages)
        self.files_card.body.addWidget(self.recursive_switch)
        self.files_card.body.addLayout(suffix_row)
        self.files_card.body.addWidget(self.overwrite_switch)
        self.files_card.body.addWidget(self.output_label)
        layout.addWidget(self.files_card)

        layout.addStretch()
        scroll.setWidget(inner)
        self.settings_panel = inner
        return scroll

    # ------------------------------------------------------------------
    def _build_preview_card(self) -> QWidget:
        self.preview_card = Card()
        self.preview_card.body.setContentsMargins(18, 14, 18, 18)

        self.page_combo = QComboBox()
        self.page_combo.addItem("", "auto")
        for name in PAGE_SIZES:
            self.page_combo.addItem(name, name)
        self.page_combo.currentIndexChanged.connect(self._page_combo_changed)

        self.portrait_button = QPushButton()
        self.landscape_button = QPushButton()
        self.portrait_button.setProperty("seg", "first")
        self.landscape_button.setProperty("seg", "last")
        self.orientation_group = QButtonGroup(self)
        for button in (self.portrait_button, self.landscape_button):
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.orientation_group.addButton(button)
        self.portrait_button.setChecked(True)
        orientation = QHBoxLayout()
        orientation.setSpacing(0)
        orientation.addWidget(self.portrait_button)
        orientation.addWidget(self.landscape_button)

        self.guides_switch = ToggleSwitch()

        self.page_label = QLabel(objectName="fieldLabel")
        header = self.preview_card.header
        header.addWidget(self.page_label)
        header.addWidget(self.page_combo)
        header.addSpacing(4)
        header.addLayout(orientation)
        header.addSpacing(10)
        header.addWidget(self.guides_switch)

        # Auto mode only: which PDF / page, and its content behind the watermark.
        self.preview_doc_label = QLabel(objectName="fieldLabel")
        self.preview_doc_spin = QSpinBox()
        self.preview_doc_stepper = Stepper(self.preview_doc_spin)
        self.preview_doc_stepper.setFixedWidth(120)
        self.source_switch = ToggleSwitch()
        self.preview_page_label = QLabel(objectName="fieldLabel")
        self.preview_page_spin = QSpinBox()
        self.preview_page_stepper = Stepper(self.preview_page_spin)
        self.preview_page_stepper.setFixedWidth(120)
        self.auto_controls = QWidget()
        auto_layout = QHBoxLayout(self.auto_controls)
        auto_layout.setContentsMargins(0, 0, 0, 0)
        auto_layout.setSpacing(8)
        auto_layout.addWidget(self.preview_doc_label)
        auto_layout.addWidget(self.preview_doc_stepper)
        auto_layout.addSpacing(14)
        auto_layout.addWidget(self.source_switch)
        auto_layout.addSpacing(14)
        auto_layout.addWidget(self.preview_page_label)
        auto_layout.addWidget(self.preview_page_stepper)
        auto_layout.addStretch()
        self.preview_card.body.addWidget(self.auto_controls)

        self.canvas = PreviewCanvas()
        canvas_frame = QFrame()
        canvas_frame.setObjectName("canvasFrame")
        frame_layout = QVBoxLayout(canvas_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self.canvas)
        self.preview_card.body.addWidget(canvas_frame, 1)
        return self.preview_card

    # ------------------------------------------------------------------
    def _build_action_bar(self) -> QWidget:
        bar = QFrame(objectName="actionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(10)

        status_box = QVBoxLayout()
        status_box.setSpacing(6)
        self.status_label = QLabel(objectName="status")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(320)
        status_box.addWidget(self.status_label)
        status_box.addWidget(self.progress_bar)
        layout.addLayout(status_box)
        layout.addStretch()

        self.log_button = QPushButton(objectName="ghost")
        self.log_button.setCheckable(True)
        self.log_button.setCursor(Qt.PointingHandCursor)
        self.log_button.toggled.connect(self.log.setVisible)

        self.open_button = QPushButton()
        self.open_button.setEnabled(False)
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self.open_output_folder)

        self.cancel_button = QPushButton()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.cancel_generation)

        self.generate_button = QPushButton(objectName="primary")
        self.generate_button.setCursor(Qt.PointingHandCursor)
        self.generate_button.setMinimumWidth(150)
        self.generate_button.clicked.connect(self.start_generation)

        for widget in (self.log_button, self.open_button, self.cancel_button, self.generate_button):
            layout.addWidget(widget)
        return bar

    def _connect_live_preview(self) -> None:
        self.text_edit.textChanged.connect(self._refresh_preview)
        self.font_combo.currentIndexChanged.connect(self._refresh_preview)
        self.size_spin.valueChanged.connect(self._refresh_preview)
        self.color_picker.colorChanged.connect(self._refresh_preview)
        self.opacity_slider.valueChanged.connect(self._refresh_preview)
        self.angle_slider.valueChanged.connect(self._refresh_preview)
        self.columns_spin.valueChanged.connect(self._refresh_preview)
        self.rows_spin.valueChanged.connect(self._refresh_preview)
        self.margin_spin.valueChanged.connect(self._refresh_preview)
        self.orientation_group.buttonClicked.connect(self._refresh_preview)
        self.guides_switch.toggled.connect(self._refresh_preview)
        self.preview_doc_spin.valueChanged.connect(self._preview_doc_changed)
        self.preview_page_spin.valueChanged.connect(self._preview_page_changed)
        self.source_switch.toggled.connect(self._source_toggled)

    # ==================================================================
    # Theme & language
    # ==================================================================

    def _apply_theme(self) -> None:
        colors = dict(THEMES[self.theme])
        arrow = resources.files(__package__) / "resources" / f"arrow_down_{self.theme}.svg"
        colors["arrow"] = Path(str(arrow)).as_posix()
        _apply_palette(QApplication.instance(), colors)
        self.setStyleSheet(STYLESHEET % colors)

        ToggleSwitch.colors = {
            "on": QColor(colors["accent"]),
            "off": QColor(colors["border_strong"]),
            "text": QColor(colors["text"]),
        }
        SwatchButton.ring = QColor(colors["text"])
        DropIcon.color = QColor(colors["accent"])
        PreviewCanvas.colors = {
            "canvas": QColor(colors["canvas"]),
            "muted": QColor(colors["muted"]),
            "accent": QColor(colors["accent"]),
        }
        self.theme_button.setText("☾" if self.theme == "light" else "☀")
        for widget in self.findChildren(QWidget):
            if isinstance(widget, (ToggleSwitch, SwatchButton, DropIcon, PreviewCanvas)):
                widget.update()

    def _toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
        self._apply_theme()

    def _language_changed(self, index: int) -> None:
        self.language = self.language_combo.itemData(index)
        if self.suffix_edit.text() in self._all_default_suffixes():
            self.suffix_edit.setText(self._t("default_suffix"))
        self._retranslate_ui()

    @staticmethod
    def _all_default_suffixes() -> set:
        return {lang["default_suffix"] for lang in TRANSLATIONS.values()}

    def _retranslate_ui(self) -> None:
        t = self._t
        self.setWindowTitle(t("title"))
        self.title_label.setText(t("title"))
        self.subtitle_label.setText(t("subtitle"))
        self.language_combo.setToolTip(t("language"))
        self.update_button.setText(t("updates"))
        self.theme_button.setToolTip(t("theme"))

        self.text_card.setTitle(t("text_card"))
        self.text_edit.setPlaceholderText(t("placeholder_text"))
        self.text_hint.setText(t("text_hint"))

        self.style_card.setTitle(t("style_card"))
        self.reset_button.setText(t("reset"))
        self.reset_button.setToolTip(t("reset_tip"))
        self.font_label.setText(t("font"))
        self.add_font_button.setToolTip(t("add_font"))
        self.size_label.setText(t("font_size"))
        self.color_label.setText(t("color"))
        self.color_picker.custom_title = t("custom_color")
        self.color_picker._custom.setToolTip(t("custom_color"))
        self.opacity_label.setText(t("opacity"))
        self.angle_label.setText(t("angle"))

        self.layout_card.setTitle(t("layout_card"))
        self.columns_label.setText(t("columns"))
        self.rows_label.setText(t("rows"))
        self.margin_label.setText(t("margin"))

        self.files_card.setTitle(t("files_card"))
        self.drop_zone.title.setText(t("drop_title"))
        self.drop_zone.or_label.setText(t("drop_or"))
        self.drop_zone.file_button.setText(t("browse_files"))
        self.drop_zone.folder_button.setText(t("browse_folder"))
        self.selection_chip.clear_button.setToolTip(t("clear_selection"))
        for row in self.file_rows:
            row.retranslate(t)
        self.folder_pages_label.setText(t("pages"))
        self.folder_pages_edit.setPlaceholderText(t("pages_placeholder"))
        self.folder_pages_hint.setText(t("folder_pages_hint"))
        self.recursive_switch.setText(t("include_subfolders"))
        self.recursive_switch.updateGeometry()
        self.suffix_label.setText(t("suffix"))
        self.suffix_edit.setPlaceholderText(t("suffix_placeholder"))
        self.overwrite_switch.setText(t("overwrite"))
        self.overwrite_switch.setToolTip(t("overwrite_tip"))
        self.overwrite_switch.updateGeometry()

        self.preview_card.setTitle(t("preview"))
        self.page_label.setText(t("page_size"))
        self.page_combo.setItemText(0, t("auto_size"))
        self.portrait_button.setText(t("portrait"))
        self.landscape_button.setText(t("landscape"))
        self.guides_switch.setText(t("guides"))
        self.guides_switch.updateGeometry()
        self.preview_doc_label.setText(t("preview_pdf"))
        self.source_switch.setText(t("show_source"))
        self.source_switch.updateGeometry()
        self.source_switch.setToolTip("" if SourceRenderer.available() else t("source_missing"))
        self.preview_page_label.setText(t("preview_page"))
        self.canvas.empty_message = t("preview_no_text")
        self.canvas.no_page_message = t("preview_no_pdf")
        self.canvas.error_title = t("preview_error")
        self.canvas.source_error_title = t("source_error")

        self.log_button.setText(t("log_show"))
        self.open_button.setText(t("open_output"))
        self.cancel_button.setText(t("cancel"))
        self.generate_button.setText(t("generate"))
        self.generate_button.setToolTip("Ctrl+Enter")

        self._refresh_selection()
        self._set_status(*self._status_key)
        self._refresh_preview()

    # ==================================================================
    # Defaults
    # ==================================================================

    def _load_defaults(self) -> None:
        """Initial state of the controls (no settings are saved between runs)."""
        self._reset_style()
        self.suffix_edit.setText(self._t("default_suffix"))
        self.overwrite_switch.setChecked(False)
        self.page_combo.setCurrentIndex(max(0, self.page_combo.findData("auto")))
        self.portrait_button.setChecked(True)
        self._page_combo_changed()

    def _reset_style(self) -> None:
        self.font_combo.setCurrentIndex(max(0, self.font_combo.findData(DEFAULTS["font"])))
        self.size_spin.setValue(DEFAULTS["size"])
        self.color_picker.setColor(DEFAULTS["color"], emit=True)
        self.opacity_slider.setValue(DEFAULTS["opacity"])
        self.angle_slider.setValue(DEFAULTS["angle"])
        self.columns_spin.setValue(DEFAULTS["columns"])
        self.rows_spin.setValue(DEFAULTS["rows"])
        self.margin_spin.setValue(DEFAULTS["margin"])

    # ==================================================================
    # Input selection
    # ==================================================================

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------

    def _populate_fonts(self, select: Optional[str] = None) -> None:
        """Fill the font list (bundled fonts, then the ones added)."""
        current = select or self.font_combo.currentData() or DEFAULTS["font"]
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        for name in available_fonts():
            self.font_combo.addItem(name, name)
        self.font_combo.setCurrentIndex(max(0, self.font_combo.findData(current)))
        self.font_combo.blockSignals(False)

    @staticmethod
    def _default_font_dir() -> str:
        """First existing fonts folder of the system, else the home folder."""
        for location in QStandardPaths.standardLocations(QStandardPaths.FontsLocation):
            if location and Path(location).is_dir():
                return location
        return str(Path.home())

    @staticmethod
    def _register_font(path: Path) -> str:
        """Register a font file under its file name, "<name> (2)"... when a
        different font already uses that name. Nothing is saved: added fonts
        are available until the application is closed."""
        base = path.stem
        for name in [base] + [f"{base} ({i})" for i in range(2, 100)]:
            try:
                return register_font(path, name)
            except ValueError:
                if name in available_fonts():
                    continue        # name used by another font file
                raise               # unreadable font
        raise ValueError(f"Too many fonts named {base!r}.")

    def add_font(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self, self._t("select_font"), self._font_dir, self._t("font_filter"))
        if not file_name:
            return
        path = Path(file_name)
        self._font_dir = str(path.parent)
        try:
            name = self._register_font(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, self._t("title"), self._t("err_font", error=str(exc)))
            return
        self._populate_fonts(select=name)
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Files / folder
    # ------------------------------------------------------------------

    def select_files(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(
            self, self._t("select_pdf"), self._browse_dir, self._t("pdf_filter"))
        if file_names:
            self.add_files([Path(name) for name in file_names])

    def select_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self._t("select_folder_dialog"), self._browse_dir)
        if directory:
            self.set_folder(Path(directory))

    def add_files(self, paths: list[Path]) -> None:
        """Add PDFs to the list (switches to files mode; duplicates ignored)."""
        pdfs = [p for p in paths if p.is_file() and p.suffix.lower() == ".pdf"]
        if not pdfs or self._is_running():
            return
        if self.input_kind == "folder":
            self._clear_inputs()
        known = {path_key(row.path) for row in self.file_rows}
        for path in pdfs:
            key = path_key(path)
            if key in known:
                continue
            known.add(key)
            row = FileRow(path)
            row.retranslate(self._t)
            row.removed.connect(self.remove_file)
            row.changed.connect(self._pages_changed)
            self.file_rows.append(row)
            self.file_list_layout.addWidget(row)
        self.input_kind = "files"
        self._browse_dir = str(pdfs[-1].parent)
        self._inputs_changed()

    def set_folder(self, path: Path) -> None:
        """Select a folder (replaces the current selection)."""
        if not path.is_dir() or self._is_running():
            return
        self._clear_inputs()
        self.input_kind = "folder"
        self.input_path = path
        self._browse_dir = str(path)
        self._inputs_changed()

    def remove_file(self, row: "FileRow") -> None:
        if row in self.file_rows and not self._is_running():
            self.file_rows.remove(row)
            self.file_list_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
            if not self.file_rows:
                self.input_kind = None
            self._inputs_changed()

    def clear_selection(self) -> None:
        self._clear_inputs()
        self._inputs_changed()

    def _clear_inputs(self) -> None:
        for row in self.file_rows:
            self.file_list_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.file_rows = []
        self.input_kind = None
        self.input_path = None

    def _inputs_changed(self) -> None:
        self.last_output_dir = None
        self.open_button.setEnabled(False)
        self.canvas.reset_view()
        self._refresh_selection()

    def _folder_pdfs(self) -> list[Path]:
        if self.input_kind != "folder" or self.input_path is None:
            return []
        pattern = "**/*.pdf" if self.recursive_switch.isChecked() else "*.pdf"
        try:
            suffix = self.suffix_edit.text().strip()
            return sorted(
                p for p in self.input_path.glob(pattern)
                if p.is_file() and not p.name.startswith(".")
                and not (suffix and p.stem.endswith(suffix))
            )
        except OSError:
            return []

    def _refresh_selection(self, *_args) -> None:
        """Update the visible widgets, the auto page size and the output path."""
        kind = self.input_kind
        self.file_list.setVisible(kind == "files")
        self.selection_chip.setVisible(kind == "folder")
        self.folder_list.setVisible(kind == "folder")
        self.folder_pages.setVisible(kind == "folder")
        self.recursive_switch.setVisible(kind == "folder")

        for number, row in enumerate(self.file_rows, start=1):
            row.set_number(number)

        self.folder_files = self._folder_pdfs() if kind == "folder" else []
        if kind == "folder" and self.input_path is not None:
            meta = self._t("pdf_count", n=len(self.folder_files))
            self.selection_chip.set_content("DIR", self.input_path.name + "/", meta,
                                            str(self.input_path))
        self._rebuild_folder_list()

        self._validate_pages()
        self._update_output_label()
        self._sync_preview_controls()
        self._refresh_preview()

    FOLDER_LIST_MAX = 300

    def _rebuild_folder_list(self) -> None:
        """Numbered list of the PDFs of the folder (full path on hover)."""
        while self.folder_list_layout.count():
            item = self.folder_list_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._folder_labels: list[QLabel] = []
        base = self.input_path
        for number, pdf in enumerate(self.folder_files[:self.FOLDER_LIST_MAX], start=1):
            try:
                shown = str(pdf.relative_to(base)) if base is not None else pdf.name
            except ValueError:
                shown = pdf.name
            line = QWidget()
            layout = QHBoxLayout(line)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            number_label = QLabel(f"{number}.", objectName="rowNumber")
            name = ElidedLabel(objectName="folderItem")
            name.setFullText(shown)
            for widget in (line, number_label, name):
                widget.setToolTip(str(pdf))
            layout.addWidget(number_label)
            layout.addWidget(name, 1)
            self.folder_list_layout.addWidget(line)
            self._folder_labels.append(name)
        hidden = len(self.folder_files) - self.FOLDER_LIST_MAX
        if hidden > 0:
            more = QLabel(self._t("folder_more", n=hidden), objectName="hint")
            self.folder_list_layout.addWidget(more)

    def _suffix_changed(self, *_args) -> None:
        # In folder mode the suffix filters out the outputs of a previous run.
        if self.input_kind == "folder":
            self._refresh_selection()
        else:
            self._update_output_label()

    def _pages_changed(self, *_args) -> None:
        self._validate_pages()
        self._refresh_preview()       # the previewed page may (no longer) be selected

    # ------------------------------------------------------------------
    # Page selections
    # ------------------------------------------------------------------

    def _page_error(self, exc: PageSelectionError) -> str:
        return self._t(f"page_err_{exc.code}", **exc.details)

    def _validate_pages(self, *_args) -> list[tuple[str, str]]:
        """Check every page selection, flag the invalid fields and return
        ``[(file or folder name, error message), ...]``."""
        errors = []
        tip = self._t("pages_tip")
        if self.input_kind == "files":
            for row in self.file_rows:
                try:
                    row.page_selection()
                    set_invalid(row.pages_edit, None, tip)
                except PageSelectionError as exc:
                    message = self._page_error(exc)
                    set_invalid(row.pages_edit, message, tip)
                    errors.append((row.path.name, message))
        elif self.input_kind == "folder" and self.input_path is not None:
            try:
                parse_pages(self.folder_pages_edit.text())
                set_invalid(self.folder_pages_edit, None, tip)
            except PageSelectionError as exc:
                message = self._page_error(exc)
                set_invalid(self.folder_pages_edit, message, tip)
                errors.append((self.input_path.name + "/", message))
        return errors

    # ------------------------------------------------------------------
    # Destinations
    # ------------------------------------------------------------------

    def _destinations(self) -> list[Path]:
        """Output files (files mode) or output folder (folder mode)."""
        suffix = self.suffix_edit.text().strip()
        if self.input_kind == "files":
            return [row.path.with_name(f"{row.path.stem}{suffix}{row.path.suffix}")
                    for row in self.file_rows]
        if self.input_kind == "folder" and self.input_path is not None:
            return [self.input_path.with_name(f"{self.input_path.name}{suffix}")]
        return []

    def _existing_destinations(self) -> list[Path]:
        return [path for path in self._destinations() if os.path.lexists(path)]

    def _output_location(self) -> Optional[Path]:
        """Output folder in folder mode."""
        if self.input_kind == "folder":
            destinations = self._destinations()
            return destinations[0] if destinations else None
        return None

    def _update_output_label(self, *_args) -> None:
        destinations = self._destinations()
        state = ""
        if not destinations:
            text = self._t("no_selection_yet")
        else:
            if self.input_kind == "folder":
                shown = f"{destinations[0]}/"
            elif len(destinations) == 1:
                shown = str(destinations[0])
            else:
                shown = self._t("output_many", n=len(destinations),
                                suffix=self.suffix_edit.text().strip())
            # Zero-width spaces let long paths wrap after each separator.
            shown = shown.replace("/", "/\u200b").replace("\\", "\\\u200b")
            text = f"{self._t('output_to')} → {shown}"
            existing = self._existing_destinations()
            replaced_folder = (self.input_kind == "folder"
                               and existing and existing[0] != self.input_path)
            if existing and self.overwrite_switch.isChecked():
                text += "\n" + (self._t("output_folder_replaced") if replaced_folder
                                else self._t("output_will_overwrite", n=len(existing)))
            elif existing:
                text += "\n⚠ " + self._t("output_exists", n=len(existing))
                state = "warn"
        self.output_label.setText(text)
        if self.output_label.property("state") != state:
            self.output_label.setProperty("state", state)
            self.output_label.style().unpolish(self.output_label)
            self.output_label.style().polish(self.output_label)

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    @staticmethod
    def _dropped_paths(event) -> tuple[list[Path], list[Path]]:
        """``(pdf files, folders)`` dropped."""
        files, folders = [], []
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.is_dir():
                        folders.append(path)
                    elif path.suffix.lower() == ".pdf":
                        files.append(path)
        return files, folders

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        files, folders = self._dropped_paths(event)
        if (files or folders) and not self._is_running():
            event.acceptProposedAction()
            self.drop_zone.setActive(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.drop_zone.setActive(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.drop_zone.setActive(False)
        files, folders = self._dropped_paths(event)
        if files:                       # PDFs win over folders in a mixed drop
            event.acceptProposedAction()
            self.add_files(files)
        elif folders:                   # a single folder at a time
            event.acceptProposedAction()
            self.set_folder(folders[0])

    # ==================================================================
    # Preview
    # ==================================================================

    def _page_combo_changed(self, *_args) -> None:
        is_auto = self.page_combo.currentData() == "auto"
        self.portrait_button.setEnabled(not is_auto)
        self.landscape_button.setEnabled(not is_auto)
        self.auto_controls.setVisible(is_auto)
        self.canvas.reset_view()
        self._sync_preview_controls()
        self._refresh_preview()

    def _get_options(self) -> dict:
        return {
            "horizontal_boxes": self.columns_spin.value(),
            "vertical_boxes": self.rows_spin.value(),
            "margin": float(self.margin_spin.value()),
            "opacity": self.opacity_slider.value() / 100.0,
            "angle": float(self.angle_slider.value()),
            "color": self.color_picker.color(),
            "font": self.font_combo.currentData(),
            "size": float(self.size_spin.value()),
        }

    # ------------------------------------------------------------------
    # Previewed PDF and page (Auto mode)
    # ------------------------------------------------------------------

    def _preview_documents(self) -> list[Path]:
        """PDFs that can be previewed, numbered from 1 as in the Files card."""
        if self.input_kind == "files":
            return [row.path for row in self.file_rows]
        if self.input_kind == "folder":
            return list(self.folder_files)
        return []

    def _preview_document(self) -> tuple[Optional[int], Optional[Path]]:
        """``(number, path)`` of the previewed PDF, ``(None, None)`` if none."""
        documents = self._preview_documents()
        for number, path in enumerate(documents, start=1):
            if path_key(path) == self.preview_key:
                return number, path
        return None, None

    @staticmethod
    def _mtime(path: Path) -> int:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return 0

    def _page_count(self, path: Path) -> Optional[int]:
        """Number of pages, ``None`` if the PDF cannot be read (cached)."""
        for row in self.file_rows:
            if row.path == path:
                return row.page_count
        key = (path_key(path), self._mtime(path))
        if key not in self._doc_cache:
            try:
                self._doc_cache[key] = count_pdf_pages(path)
            except Exception:
                self._doc_cache[key] = None
        return self._doc_cache[key]

    def _page_size(self, path: Path, index: int) -> Optional[tuple[float, float]]:
        """Displayed size of a page, ``None`` if unreadable (cached)."""
        key = (path_key(path), self._mtime(path), index)
        if key not in self._size_cache:
            try:
                self._size_cache[key] = get_page_size(path, index)
            except Exception:
                self._size_cache[key] = None
        return self._size_cache[key]

    def _page_selection_of(self, path: Path) -> Optional[list[int]]:
        """1-based page selection that applies to ``path`` (``None`` = all,
        also used while the typed selection is invalid)."""
        try:
            if self.input_kind == "files":
                for row in self.file_rows:
                    if row.path == path:
                        return row.page_selection()
            elif self.input_kind == "folder":
                return parse_pages(self.folder_pages_edit.text())
        except PageSelectionError:
            pass
        return None

    def _source_shown(self) -> bool:
        return (self.page_combo.currentData() == "auto"
                and self.source_switch.isChecked()
                and self.preview_page_spin.isEnabled())

    @staticmethod
    def _set_spin(spin: QSpinBox, stepper: QWidget, maximum: Optional[int], value: int) -> None:
        """``maximum=None``: empty and disabled; otherwise range 1..maximum."""
        if maximum is None:
            spin.setSpecialValueText(" ")          # shown for the minimum: blank
            spin.setRange(0, 0)
            spin.setValue(0)
            stepper.setEnabled(False)
        else:
            spin.setSpecialValueText("")
            spin.setRange(1, maximum)
            spin.setValue(min(max(1, value), maximum))
            stepper.setEnabled(True)

    def _sync_preview_controls(self) -> None:
        """Keep the PDF / page numbers consistent with the current selection:
        the same PDF stays previewed when others are added or removed; if it
        was removed, the first PDF is used; without PDF, both are empty."""
        if not hasattr(self, "preview_doc_spin"):
            return
        self._syncing = True
        try:
            documents = self._preview_documents()
            keys = [path_key(path) for path in documents]
            if not documents:
                self.preview_key = None
                self._set_spin(self.preview_doc_spin, self.preview_doc_stepper, None, 0)
            else:
                if self.preview_key not in keys:
                    self.preview_key = keys[0]
                number = keys.index(self.preview_key) + 1
                self._set_spin(self.preview_doc_spin, self.preview_doc_stepper,
                               len(documents), number)

            self.source_switch.setEnabled(bool(documents) and SourceRenderer.available())

            count = None
            if documents and self.source_switch.isChecked() and SourceRenderer.available():
                count = self._page_count(documents[keys.index(self.preview_key)])
            if count:
                page = self.preview_page_spin.value()
                if self._preview_page_key != self.preview_key:
                    page = 1                       # another PDF: back to page 1
                self._set_spin(self.preview_page_spin, self.preview_page_stepper, count, page)
                self._preview_page_key = self.preview_key
            else:
                self._set_spin(self.preview_page_spin, self.preview_page_stepper, None, 0)
                self._preview_page_key = None

            # Highlight the previewed PDF in the Files card.
            for row, key in zip(self.file_rows, keys if self.input_kind == "files" else []):
                set_flag(row, "current", key == self.preview_key)
            for label, key in zip(getattr(self, "_folder_labels", []),
                                  keys if self.input_kind == "folder" else []):
                set_flag(label, "current", key == self.preview_key)
        finally:
            self._syncing = False

    def _preview_doc_changed(self, value: int) -> None:
        if self._syncing:
            return
        documents = self._preview_documents()
        if 1 <= value <= len(documents):
            self.preview_key = path_key(documents[value - 1])
            self.canvas.reset_view()
        self._sync_preview_controls()
        self._refresh_preview()

    def _preview_page_changed(self, _value: int) -> None:
        if not self._syncing:
            self._refresh_preview()

    def _source_toggled(self, _checked: bool) -> None:
        self._sync_preview_controls()
        self._refresh_preview()

    # ------------------------------------------------------------------

    def _preview_page(self):
        """``(page size or None, caption, source, watermarked)``."""
        choice = self.page_combo.currentData()
        source = None
        watermarked = True
        prefix = ""

        if choice == "auto":
            number, path = self._preview_document()
            if path is None:
                return None, "", None, True          # Auto without PDF: no preview
            prefix = f"{number}. {path.name} · "
            if self._source_shown():
                page = self.preview_page_spin.value()
                count = self._page_count(path)
                size = self._page_size(path, page - 1)
                renderer = self.renderer
                source = lambda px, p=path, i=page - 1: renderer.render(p, i, px)  # noqa: E731
                prefix += self._t("preview_page_of", page=page, count=count) + " · "
                selection = self._page_selection_of(path)
                watermarked = selection is None or page in selection
            else:
                size = self._page_size(path, 0)
            if size is None:
                return A4, prefix + "⚠ " + self._t("unreadable_pdf"), None, True
        else:
            short, long_ = sorted(PAGE_SIZES[choice])
            size = (long_, short) if self.landscape_button.isChecked() else (short, long_)

        name = ""
        for label, (a, b) in PAGE_SIZES.items():
            if {round(a), round(b)} == {round(size[0]), round(size[1])}:
                name = f"{label} · "
                break
        mm = f"{size[0] * 25.4 / 72:.0f} × {size[1] * 25.4 / 72:.0f} mm"
        caption = prefix + name + mm
        if not watermarked:
            caption += " · " + self._t("preview_not_watermarked")
        return size, caption, source, watermarked

    def _refresh_preview(self, *_args) -> None:
        if not hasattr(self, "canvas"):
            return
        size, caption, source, watermarked = self._preview_page()
        self.canvas.set_config(
            page_size=size,
            caption=caption,
            text=self.text_edit.toPlainText(),
            options=self._get_options(),
            guides=self.guides_switch.isChecked(),
            source=source,
            watermarked=watermarked,
        )

    # ==================================================================
    # Generation
    # ==================================================================

    def _is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def _warn(self, key: str, **kwargs) -> None:
        QMessageBox.warning(self, self._t("title"), self._t(key, **kwargs))

    def start_generation(self) -> None:
        if self._is_running():
            return
        if self.input_kind is None:
            self._warn("err_no_input")
            return

        text = self.text_edit.toPlainText()
        if not text.strip():
            self._warn("err_no_text")
            self.text_edit.setFocus()
            return

        suffix = self.suffix_edit.text().strip()
        bad = sorted({c for c in suffix if c in FORBIDDEN_SUFFIX_CHARS or ord(c) < 32})
        if bad:
            self._warn("err_suffix_chars", chars=" ".join(bad))
            return

        if self.input_kind == "files":
            missing = [row.path for row in self.file_rows if not row.path.is_file()]
            if missing:
                self._warn("err_invalid_file", name=missing[0].name)
                return
        else:
            if not self.input_path.is_dir():
                self._warn("err_invalid_folder")
                return
            if not self._folder_pdfs():
                self._warn("err_no_pdf")
                return

        page_errors = self._validate_pages()
        if page_errors:
            details = "\n".join(f"• {name}: {message}" for name, message in page_errors[:10])
            self._warn("err_pages", details=details)
            return

        options = self._get_options()
        try:
            WatermarkStyle(text=text, **options)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, self._t("title"), str(exc))
            return

        overwrite = self.overwrite_switch.isChecked()
        existing = self._existing_destinations()
        if existing and not overwrite:
            self._show_existing(existing)
            return

        if not suffix:
            reply = QMessageBox.question(
                self, self._t("title"), self._t("suffix_overwrite_warning"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        # --- Start -----------------------------------------------------
        self.log.clear()
        if self.input_kind == "files":
            jobs = {row.path: to_page_indices(row.page_selection()) for row in self.file_rows}
            first_name = self.file_rows[0].path.name
            self._log(self._t("log_start_files", n=len(jobs)))
            self.worker = WatermarkWorker(
                kind="files", text=text, suffix=suffix, overwrite=overwrite,
                options=options, files=jobs, parent=self,
            )
        else:
            pages = to_page_indices(parse_pages(self.folder_pages_edit.text()))
            first_name = self.input_path.name
            self._log(self._t("log_start_folder", path=self.input_path))
            self.worker = WatermarkWorker(
                kind="folder", text=text, suffix=suffix, overwrite=overwrite,
                options=options, folder=self.input_path, pages=pages,
                recursive=self.recursive_switch.isChecked(), parent=self,
            )

        self.last_output_dir = None
        self.progress_bar.setRange(0, 0)   # indeterminate while counting pages
        self._set_status("status_running", {"done": 0, "total": "…", "name": first_name})
        self._set_running(True)

        self.worker.progress.connect(self._on_progress)
        self.worker.completed.connect(self._on_completed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _show_existing(self, paths: list[Path]) -> None:
        shown = "\n".join(f"• {path}" for path in paths[:10])
        if len(paths) > 10:
            shown += "\n…"
        self._warn("err_exists", paths=shown)

    def cancel_generation(self) -> None:
        if self._is_running():
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self._set_status("status_cancelling", {})

    def _set_running(self, running: bool) -> None:
        self.settings_panel.setEnabled(not running)
        self.language_combo.setEnabled(not running)
        self.generate_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.open_button.setEnabled(not running and self.last_output_dir is not None)

    def _on_progress(self, done: int, total: int, name: str) -> None:
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(done)
        if self.cancel_button.isEnabled():
            self._set_status("status_running", {"done": done, "total": total, "name": name})

    def _on_completed(self, status: str, payload) -> None:
        self.progress_bar.setRange(0, 1)

        if status == "ok":
            results: dict = payload or {}
            errors = {k: v for k, v in results.items() if v.startswith("ERROR")}
            created = [v for v in results.values() if not v.startswith("ERROR")]
            for output in created:
                self._log(f"✓ {output}")
            for source, message in errors.items():
                self._log(f"✗ {source} — {message[len('ERROR: '):]}")

            if created:
                self.last_output_dir = Path(created[0]).parent if self.input_kind == "files" \
                    else self._output_location()
            self.progress_bar.setValue(1)
            if errors:
                self._set_status("status_done_errors", {"ok": len(created), "err": len(errors)}, "error")
                details = "\n".join(
                    f"• {Path(k).name}: {v[len('ERROR: '):]}" for k, v in list(errors.items())[:10])
                if len(errors) > 10:
                    details += "\n…"
                QMessageBox.warning(self, self._t("errors_title"), details)
            else:
                self._set_status("status_done", {"ok": len(created)}, "ok")

        elif status == "exists":
            self.progress_bar.setValue(0)
            self._set_status("status_failed", {}, "error")
            self._show_existing(list(payload))

        elif status == "cancelled":
            self.progress_bar.setValue(0)
            self._log(self._t("log_cancelled"))
            self._set_status("status_cancelled", {})

        else:
            self.progress_bar.setValue(0)
            self._log(f"✗ {payload}")
            self._set_status("status_failed", {}, "error")
            QMessageBox.critical(self, self._t("generation_error"), str(payload))

        self._set_running(False)
        self.worker = None
        self._update_output_label()      # outputs now exist

    def open_output_folder(self) -> None:
        if self.last_output_dir is not None and self.last_output_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))

    def show_updates(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(self._t("updates"))
        box.setTextFormat(Qt.RichText)
        box.setText(self._t("updates_text", version=VERSION, url=RELEASES_URL))
        box.exec_()

    # ==================================================================
    # Status & log
    # ==================================================================

    def _set_status(self, key: str, values: dict, state: str = "") -> None:
        self._status_key = (key, values)
        self.status_label.setText(self._t(key, **values))
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # ==================================================================
    # Close
    # ==================================================================

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._is_running():
            reply = QMessageBox.question(
                self, self._t("title"), self._t("confirm_quit"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait()
        event.accept()