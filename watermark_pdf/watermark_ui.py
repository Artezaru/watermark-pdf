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
import threading
import time
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
    Qt,
    QThread,
    QUrl,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QConicalGradient,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QIcon,
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

from .translation import TRANSLATIONS
from .watermark import (
    LINE_SPACING,
    STANDARD_FONTS,
    WatermarkCancelled,
    WatermarkStyle,
    add_watermark,
    batch_watermark_directory,
    count_pdf_pages,
    get_page_size,
)


# ============================================================================
# Configuration
# ============================================================================

APP_NAME = "PDF Watermark"
ORG_NAME = "Artezaru"

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
    "font": "Helvetica",
    "size": 12.0,         # points
}

# PDF standard fonts -> installed look-alikes, for the on-screen preview.
FONT_SUBSTITUTES = {
    "Helvetica": ["Arial", "Liberation Sans", "Nimbus Sans", "Nimbus Sans L",
                  "TeX Gyre Heros", "DejaVu Sans"],
    "Times": ["Times New Roman", "Liberation Serif", "Nimbus Roman",
              "Nimbus Roman No9 L", "TeX Gyre Termes", "DejaVu Serif"],
    "Courier": ["Courier New", "Liberation Mono", "Nimbus Mono PS",
                "Nimbus Mono L", "TeX Gyre Cursor", "DejaVu Sans Mono"],
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
    width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid %(muted)s;
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

def qfont_for(pdf_font: str) -> QFont:
    """QFont that looks like a PDF standard font."""
    base, _, variant = pdf_font.partition("-")
    font = QFont(base)
    font.setBold("Bold" in variant)
    font.setItalic("Oblique" in variant or "Italic" in variant)
    font.setKerning(False)                      # ReportLab does not kern
    font.setHintingPreference(QFont.PreferNoHinting)
    font.setStyleStrategy(QFont.PreferOutline)
    return font


def font_display_name(pdf_font: str) -> str:
    base, _, variant = pdf_font.partition("-")
    variant = variant.replace("Roman", "").replace("BoldOblique", "Bold Oblique")
    variant = variant.replace("BoldItalic", "Bold Italic")
    return f"{base} {variant}".strip()


def draw_watermark(
    painter: QPainter,
    width: float,
    height: float,
    style: WatermarkStyle,
    guides_color: Optional[QColor] = None,
) -> None:
    """Draw the watermark in *page coordinates* (points, origin top-left).

    The caller is responsible for scaling points to pixels. Positions,
    rotation, line spacing and font size exactly match the PDF output.
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

    # A large reference size, scaled down per block: avoids integer font
    # sizes and screen-DPI conversions, so 1 font point == 1 page point.
    reference = 100.0
    font = qfont_for(style.font)
    font.setPixelSize(int(reference))
    metrics = QFontMetricsF(font)

    color = QColor(style.color)
    color.setAlphaF(style.opacity)
    painter.setPen(color)
    painter.setFont(font)

    lines = style.lines
    widths = [metrics.horizontalAdvance(line) for line in lines]
    scale = style.size / reference
    line_height = style.size * LINE_SPACING
    first_baseline = (len(lines) - 1) * line_height / 2

    for x, y in centers:
        painter.save()
        painter.translate(x, height - y)           # PDF y goes up, Qt y goes down
        painter.rotate(-style.angle)               # PDF angles are counter-clockwise
        painter.scale(scale, scale)
        baseline = first_baseline
        for line, line_width in zip(lines, widths):
            if line:
                painter.drawText(QPointF(-line_width / 2, -baseline / scale), line)
            baseline -= line_height
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


class PreviewCanvas(QWidget):
    """Draws a page and its watermark, scaled to fit, crisp at any size."""

    colors = {"canvas": QColor("#E9ECF1"), "muted": QColor("#6B7280"), "accent": QColor("#4F46E5")}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.page_size = A4
        self.caption = ""
        self.text = ""
        self.options: dict = {}
        self.guides = False
        self.empty_message = ""
        self.error_title = "Error"

    def set_config(self, page_size, caption: str, text: str, options: dict, guides: bool) -> None:
        self.page_size = page_size
        self.caption = caption
        self.text = text
        self.options = options
        self.guides = guides
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing
                         | QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), self.colors["canvas"])

        page_w, page_h = float(self.page_size[0]), float(self.page_size[1])
        pad, caption_h = 28.0, 26.0
        scale = min((self.width() - 2 * pad) / page_w,
                    (self.height() - 2 * pad - caption_h) / page_h)
        scale = max(scale, 0.05)
        w, h = page_w * scale, page_h * scale
        page = QRectF((self.width() - w) / 2, (self.height() - caption_h - h) / 2, w, h)

        # Soft shadow + paper.
        p.setPen(Qt.NoPen)
        for i in range(1, 9):
            p.setBrush(QColor(0, 0, 0, max(0, 14 - i * 2)))
            p.drawRoundedRect(page.adjusted(-i, -i + 3, i, i + 3), 3 + i, 3 + i)
        p.setBrush(QColor("white"))
        p.drawRect(page)

        # Caption under the page.
        p.setPen(self.colors["muted"])
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, self.font().pointSizeF() - 1))
        p.setFont(small)
        p.drawText(QRectF(0, page.bottom() + 8, self.width(), caption_h),
                   Qt.AlignHCenter | Qt.AlignTop, self.caption)

        if not self.text.strip():
            p.setPen(QColor("#9CA3AF"))
            p.drawText(page.adjusted(24, 24, -24, -24), Qt.AlignCenter | Qt.TextWordWrap,
                       self.empty_message)
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
            draw_watermark(p, page_w, page_h, style, guides)
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
    """Run the generation in a background thread."""

    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(str, object)  # status: "ok" | "cancelled" | "error", payload

    def __init__(self, kind: str, path: Path, text: str, suffix: str,
                 recursive: bool, options: dict, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.path = path
        self.text = text
        self.suffix = suffix
        self.recursive = recursive
        self.options = options
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
        try:
            if self.kind == "file":
                output = add_watermark(
                    self.path, self.text, suffix=self.suffix, verbose=False,
                    progress_callback=self._on_progress, cancel_event=self._cancel,
                    **self.options,
                )
                results = {str(self.path): output}
            else:
                results = batch_watermark_directory(
                    self.path, self.text, suffix=self.suffix, recursive=self.recursive,
                    verbose=False, progress_callback=self._on_progress,
                    cancel_event=self._cancel, **self.options,
                )
            self.completed.emit("ok", results)
        except WatermarkCancelled:
            self.completed.emit("cancelled", None)
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

        self.input_kind: Optional[str] = None       # None | "file" | "folder"
        self.input_path: Optional[Path] = None
        self.auto_page_size: Optional[tuple[float, float]] = None
        self.last_output_dir: Optional[Path] = None
        self.worker: Optional[WatermarkWorker] = None
        self._status_key = ("status_ready", {})
        self._browse_dir = str(Path.home())         # remembered for this session only

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
        self.setMinimumSize(1040, 680)
        self.resize(1280, 820)

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
        splitter.setSizes([400, 820])
        body_layout.addWidget(splitter, 1)

        self.log = QPlainTextEdit(objectName="log")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        self.log.setVisible(False)
        body_layout.addWidget(self.log)

        root_layout.addWidget(body, 1)
        root_layout.addWidget(self._build_action_bar())

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.start_generation)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.select_file)
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
        scroll.setMinimumWidth(370)
        scroll.setMaximumWidth(480)

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
        for name in STANDARD_FONTS:
            self.font_combo.addItem(font_display_name(name), name)
            preview_font = qfont_for(name)
            preview_font.setPointSize(10)
            self.font_combo.setItemData(self.font_combo.count() - 1, preview_font, Qt.FontRole)

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
            (self.font_label, self.font_combo),
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
        self.drop_zone.file_button.clicked.connect(self.select_file)
        self.drop_zone.folder_button.clicked.connect(self.select_folder)
        self.selection_chip = SelectionChip()
        self.selection_chip.cleared.connect(self.clear_selection)
        self.recursive_switch = ToggleSwitch()
        self.recursive_switch.toggled.connect(self._refresh_selection)

        suffix_row = QHBoxLayout()
        suffix_row.setSpacing(10)
        self.suffix_label = QLabel(objectName="fieldLabel")
        self.suffix_edit = QLineEdit()
        self.suffix_edit.textChanged.connect(self._update_output_label)
        suffix_row.addWidget(self.suffix_label)
        suffix_row.addWidget(self.suffix_edit, 1)

        self.output_label = QLabel(objectName="outputPath")
        self.output_label.setWordWrap(True)
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.files_card.body.addWidget(self.drop_zone)
        self.files_card.body.addWidget(self.selection_chip)
        self.files_card.body.addWidget(self.recursive_switch)
        self.files_card.body.addLayout(suffix_row)
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

    # ==================================================================
    # Theme & language
    # ==================================================================

    def _apply_theme(self) -> None:
        colors = THEMES[self.theme]
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
        self.theme_button.setToolTip(t("theme"))

        self.text_card.setTitle(t("text_card"))
        self.text_edit.setPlaceholderText(t("placeholder_text"))
        self.text_hint.setText(t("text_hint"))

        self.style_card.setTitle(t("style_card"))
        self.reset_button.setText(t("reset"))
        self.reset_button.setToolTip(t("reset_tip"))
        self.font_label.setText(t("font"))
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
        self.drop_zone.file_button.setText(t("browse_file"))
        self.drop_zone.folder_button.setText(t("browse_folder"))
        self.selection_chip.clear_button.setToolTip(t("clear_selection"))
        self.recursive_switch.setText(t("include_subfolders"))
        self.recursive_switch.updateGeometry()
        self.suffix_label.setText(t("suffix"))
        self.suffix_edit.setPlaceholderText(t("suffix_placeholder"))

        self.preview_card.setTitle(t("preview"))
        self.page_label.setText(t("page_size"))
        self.page_combo.setItemText(0, t("auto_size"))
        self.portrait_button.setText(t("portrait"))
        self.landscape_button.setText(t("landscape"))
        self.guides_switch.setText(t("guides"))
        self.guides_switch.updateGeometry()
        self.canvas.empty_message = t("preview_no_text")
        self.canvas.error_title = t("preview_error")

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

    def select_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self, self._t("select_pdf"), self._browse_dir, self._t("pdf_filter"))
        if file_name:
            self.set_input(Path(file_name))

    def select_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self._t("select_folder_dialog"), self._browse_dir)
        if directory:
            self.set_input(Path(directory))

    def set_input(self, path: Path) -> None:
        if path.is_dir():
            self.input_kind = "folder"
            self._browse_dir = str(path)
        elif path.is_file() and path.suffix.lower() == ".pdf":
            self.input_kind = "file"
            self._browse_dir = str(path.parent)
        else:
            return
        self.input_path = path
        self.last_output_dir = None
        self.open_button.setEnabled(False)
        self._refresh_selection()
        self._refresh_preview()

    def clear_selection(self) -> None:
        self.input_kind = None
        self.input_path = None
        self.auto_page_size = None
        self._refresh_selection()
        self._refresh_preview()

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
        """Update the selection chip, the auto page size and the output path."""
        has_input = self.input_path is not None
        self.selection_chip.setVisible(has_input)
        self.recursive_switch.setVisible(self.input_kind == "folder")
        self.auto_page_size = None

        if self.input_kind == "file" and self.input_path is not None:
            try:
                pages = count_pdf_pages(self.input_path)
                meta = self._t("pages_count", n=pages)
                self.auto_page_size = get_page_size(self.input_path)
            except Exception as exc:
                meta = f"⚠ {type(exc).__name__}"
            self.selection_chip.set_content("PDF", self.input_path.name, meta, str(self.input_path))

        elif self.input_kind == "folder" and self.input_path is not None:
            pdfs = self._folder_pdfs()
            meta = self._t("pdf_count", n=len(pdfs))
            for pdf in pdfs[:3]:          # first readable PDF gives the page size
                try:
                    self.auto_page_size = get_page_size(pdf)
                    break
                except Exception:
                    continue
            self.selection_chip.set_content("DIR", self.input_path.name + "/", meta,
                                            str(self.input_path))

        self._update_output_label()
        self._refresh_preview()

    def _output_location(self) -> Optional[Path]:
        suffix = self.suffix_edit.text().strip()
        if self.input_kind == "file" and self.input_path is not None:
            return self.input_path.with_name(f"{self.input_path.stem}{suffix}{self.input_path.suffix}")
        if self.input_kind == "folder" and self.input_path is not None:
            return self.input_path.with_name(f"{self.input_path.name}{suffix}")
        return None

    def _update_output_label(self, *_args) -> None:
        location = self._output_location()
        if location is None:
            self.output_label.setText(self._t("no_selection_yet"))
        else:
            shown = f"{location}{'/' if self.input_kind == 'folder' else ''}"
            # Zero-width spaces let long paths wrap after each separator.
            shown = shown.replace("/", "/\u200b").replace("\\", "\\\u200b")
            self.output_label.setText(f"{self._t('output_to')} → {shown}")

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    @staticmethod
    def _dropped_path(event) -> Optional[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_dir() or path.suffix.lower() == ".pdf":
                    return path
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_path(event) is not None and not self._is_running():
            event.acceptProposedAction()
            self.drop_zone.setActive(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.drop_zone.setActive(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.drop_zone.setActive(False)
        path = self._dropped_path(event)
        if path is not None:
            event.acceptProposedAction()
            self.set_input(path)

    # ==================================================================
    # Preview
    # ==================================================================

    def _page_combo_changed(self, *_args) -> None:
        is_auto = self.page_combo.currentData() == "auto"
        self.portrait_button.setEnabled(not is_auto)
        self.landscape_button.setEnabled(not is_auto)
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

    def _preview_page(self) -> tuple[tuple[float, float], str]:
        choice = self.page_combo.currentData()
        if choice == "auto":
            size = self.auto_page_size or A4
        else:
            short, long_ = sorted(PAGE_SIZES[choice])
            size = (long_, short) if self.landscape_button.isChecked() else (short, long_)

        name = ""
        for label, (a, b) in PAGE_SIZES.items():
            if {round(a), round(b)} == {round(size[0]), round(size[1])}:
                name = f"{label} · "
                break
        mm = f"{size[0] * 25.4 / 72:.0f} × {size[1] * 25.4 / 72:.0f} mm"
        return size, name + mm

    def _refresh_preview(self, *_args) -> None:
        if not hasattr(self, "canvas"):
            return
        page, caption = self._preview_page()
        self.canvas.set_config(
            page_size=page,
            caption=caption,
            text=self.text_edit.toPlainText(),
            options=self._get_options(),
            guides=self.guides_switch.isChecked(),
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
        if self.input_path is None:
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

        if self.input_kind == "file" and not self.input_path.is_file():
            self._warn("err_invalid_file")
            return
        if self.input_kind == "folder":
            if not self.input_path.is_dir():
                self._warn("err_invalid_folder")
                return
            if not self._folder_pdfs():
                self._warn("err_no_pdf")
                return

        options = self._get_options()
        try:
            WatermarkStyle(text=text, **options)
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, self._t("title"), str(exc))
            return

        if not suffix:
            reply = QMessageBox.question(
                self, self._t("title"), self._t("suffix_overwrite_warning"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        # --- Start -----------------------------------------------------
        self.log.clear()
        if self.input_kind == "file":
            self._log(self._t("log_start_file", name=self.input_path.name))
        else:
            self._log(self._t("log_start_folder", path=self.input_path))

        self.last_output_dir = None
        self.progress_bar.setRange(0, 0)   # indeterminate while counting pages
        self._set_status("status_running", {"done": 0, "total": "…", "name": self.input_path.name})
        self._set_running(True)

        self.worker = WatermarkWorker(
            kind=self.input_kind,
            path=self.input_path,
            text=text,
            suffix=suffix,
            recursive=self.recursive_switch.isChecked(),
            options=options,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.completed.connect(self._on_completed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

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
                self.last_output_dir = Path(created[0]).parent if self.input_kind == "file" \
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

    def open_output_folder(self) -> None:
        if self.last_output_dir is not None and self.last_output_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))

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
