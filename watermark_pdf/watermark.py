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

"""Add a repeated text watermark to PDF files.

The watermark is a grid of (optionally multi-line, rotated) text blocks merged
on top of every page with pypdf. The text is drawn as vector outlines (not as
text): it cannot be selected, copied, searched or extracted, and it is marked
as a pagination artifact, so tagged PDFs and screen readers ignore it.

Fonts
-----
Fonts are referred to by name. The 12 Liberation fonts (SIL Open Font
License) are bundled, see :data:`BUNDLED_FONTS`; they have the same metrics
as Helvetica/Arial, Times and Courier. Any TrueType or OpenType font file can
be added with :func:`register_font`.

Public API
----------
- :func:`add_watermark`              -- watermark one PDF file
- :func:`watermark_files`            -- watermark several PDF files
- :func:`batch_watermark_directory`  -- watermark every PDF of a folder
- :func:`register_font`              -- make a font file usable by name
- :func:`available_fonts`            -- names of the usable fonts
- :func:`count_pdf_pages`            -- number of pages of a PDF
- :func:`get_page_size`              -- displayed size of a page
- :func:`text_block_outline`         -- outline of the text, for previews
- :class:`WatermarkStyle`            -- validated watermark settings
- :class:`WatermarkCancelled`        -- raised when a cancellation is requested
- :class:`DestinationExistsError`    -- an output exists and overwrite is off

Existing outputs are never replaced unless ``overwrite=True``; with several
files, every destination is checked before anything is written.

Long operations accept two optional hooks, which make them easy to drive
from a GUI thread:

``progress_callback(done_pages, total_pages, current_file)``
    Called after every processed page.
``cancel_event``
    Any object with an ``is_set()`` method (e.g. :class:`threading.Event`).
    It is checked before every page; when set, the operation stops, no
    partial output file is left behind, and :class:`WatermarkCancelled`
    is raised.

Limitations
-----------
Text is laid out glyph by glyph, left to right, without kerning: right-to-left
and complex scripts (Arabic, Hebrew, Devanagari, Thai...) render incorrectly.
"""

import contextlib
import functools
import math
import numbers
import os
import secrets
import shutil
import stat
import threading
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Protocol, Union

from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, TTLibError
from pypdf import PageObject, PasswordType, PdfReader, PdfWriter, Transformation
from pypdf.generic import DecodedStreamObject
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfgen.canvas import FILL_NON_ZERO

try:  # tqdm is optional: only used for console progress bars.
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


__all__ = [
    "BUNDLED_FONTS",
    "DEFAULT_FONT",
    "DEFAULT_MARGIN",
    "FONTS_DIR",
    "LINE_SPACING",
    "DestinationExistsError",
    "WatermarkCancelled",
    "WatermarkStyle",
    "add_watermark",
    "available_fonts",
    "batch_watermark_directory",
    "count_pdf_pages",
    "get_page_size",
    "path_key",
    "register_font",
    "safe_resolve",
    "text_block_outline",
    "watermark_files",
]

PathLike = Union[str, os.PathLike]
ProgressCallback = Callable[[int, int, str], None]
PageSelection = Union[None, int, Iterable[int]]

def safe_resolve(path: PathLike) -> Path:
    """Absolute, normalized path; symbolic links resolved when possible.

    :meth:`Path.resolve` can raise :class:`OSError` on Windows (redirected
    "Documents" folders, OneDrive, network shares: WinError 59, 53...).
    In that case the absolute path is returned without resolving links.
    """
    path = Path(path).expanduser()
    try:
        return path.resolve()
    except OSError:
        return Path(os.path.abspath(path))


def path_key(path: PathLike) -> str:
    """Key telling whether two paths are the same file (case-insensitive on
    Windows). Never raises on unreachable network paths."""
    return os.path.normcase(str(safe_resolve(path)))


#: Folder of the bundled font files.
FONTS_DIR = safe_resolve(__file__).parent / "resources" / "fonts"

#: Fonts shipped with the package (files ``FONTS_DIR / f"{name}.ttf"``).
BUNDLED_FONTS = tuple(
    f"Liberation{family}-{style}"
    for family in ("Sans", "Serif", "Mono")
    for style in ("Regular", "Bold", "Italic", "BoldItalic")
)

#: Font used when none is given.
DEFAULT_FONT = "LiberationSans-Regular"

#: File extensions accepted by :func:`register_font`.
FONT_FILE_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc")

#: Margin (in points) used when ``margin=True`` is passed.
DEFAULT_MARGIN = 10.0

#: Distance between two baselines, as a multiple of the font size.
LINE_SPACING = 1.2


class WatermarkCancelled(Exception):
    """Raised when the operation is cancelled through ``cancel_event``."""


class DestinationExistsError(FileExistsError):
    """Raised, before anything is written, when an output file or folder
    already exists and ``overwrite`` is false. ``paths`` lists them."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self.paths = [Path(p) for p in paths]
        shown = "\n".join(f"  {p}" for p in self.paths[:10])
        more = f"\n  ... and {len(self.paths) - 10} more" if len(self.paths) > 10 else ""
        super().__init__(
            f"{len(self.paths)} destination(s) already exist "
            f"(use overwrite=True to replace them):\n{shown}{more}"
        )


class _EventLike(Protocol):
    def is_set(self) -> bool: ...


# ============================================================================
# Validation
# ============================================================================

def _rgb_from_hex(hex_color: str) -> tuple[float, float, float]:
    """Convert ``#RRGGBB`` (or ``RRGGBB``) to RGB components in ``[0, 1]``."""
    if not isinstance(hex_color, str):
        raise TypeError(f"color must be a str, got {type(hex_color).__name__}")

    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(
            f"Invalid color {hex_color!r}: expected 6 hexadecimal digits (#RRGGBB)."
        )
    try:
        r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"Invalid hexadecimal color: {hex_color!r}") from exc
    return r, g, b


def _is_number(value) -> bool:
    """Real number (int, float, numpy scalars...), excluding bool, NaN and inf."""
    return (
        isinstance(value, numbers.Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_int(value) -> bool:
    """Integer (int, numpy integers...), excluding bool."""
    return isinstance(value, numbers.Integral) and not isinstance(value, bool)


# ============================================================================
# Fonts
# ============================================================================

#: name -> (font file, index of the font in a .ttc/.otc collection)
_FONT_REGISTRY: dict[str, tuple[Path, int]] = {
    name: (FONTS_DIR / f"{name}.ttf", 0) for name in BUNDLED_FONTS
}
_REGISTRY_LOCK = threading.Lock()


class _OutlineFont:
    """Glyph outlines and metrics of a font file (TrueType or CFF outlines)."""

    def __init__(self, path: Path, font_number: int) -> None:
        is_collection = path.suffix.lower() in (".ttc", ".otc")
        try:
            font = TTFont(str(path), fontNumber=font_number if is_collection else -1, lazy=True)
            self.units_per_em = font["head"].unitsPerEm
            self.cmap = font.getBestCmap() or {}
            self.glyph_set = font.getGlyphSet()
            self.advances = font["hmtx"].metrics
        except (OSError, TTLibError, KeyError, IndexError, AssertionError) as exc:
            raise ValueError(f"Cannot read font file {path.name}: {exc}") from exc
        if not self.cmap:
            raise ValueError(f"Font file {path.name} has no Unicode character map.")
        self._lock = threading.Lock()  # lazy fontTools tables are not thread-safe

    def missing_characters(self, text: str) -> list[str]:
        """Printable characters of ``text`` without a glyph in the font."""
        return sorted({
            c for c in text
            if c.isprintable() and not c.isspace() and ord(c) not in self.cmap
        })

    def _glyph_names(self, line: str) -> list[str]:
        return [self.cmap.get(ord(c), ".notdef") for c in line if c.isprintable()]

    def _advance(self, glyph_name: str) -> float:
        if glyph_name in self.advances:
            return self.advances[glyph_name][0]
        return self.units_per_em / 4  # whitespace missing from the font

    def line_width(self, line: str, size: float) -> float:
        with self._lock:
            units = sum(self._advance(g) for g in self._glyph_names(line))
        return units * size / self.units_per_em

    def draw_line(self, pen, line: str, x: float, y: float, size: float) -> None:
        """Draw the outlines of ``line`` into a fontTools pen, in points,
        the baseline starting at ``(x, y)``."""
        scale = size / self.units_per_em
        with self._lock:
            for glyph_name in self._glyph_names(line):
                if glyph_name in self.glyph_set:
                    self.glyph_set[glyph_name].draw(
                        TransformPen(pen, (scale, 0, 0, scale, x, y))
                    )
                x += self._advance(glyph_name) * scale


class _OutlineRecorder(BasePen):
    """fontTools pen recording outlines as ``(operator, points)`` tuples.
    Components are decomposed and quadratic curves (TrueType) converted to
    cubic ones by :class:`BasePen`."""

    def __init__(self, glyph_set) -> None:
        super().__init__(glyph_set)
        self.operations: list[tuple[str, tuple]] = []

    def _moveTo(self, pt):
        self.operations.append(("moveTo", (pt,)))

    def _lineTo(self, pt):
        self.operations.append(("lineTo", (pt,)))

    def _curveToOne(self, pt1, pt2, pt3):
        self.operations.append(("curveTo", (pt1, pt2, pt3)))

    def _closePath(self):
        self.operations.append(("closePath", ()))

    def _endPath(self):
        self.operations.append(("closePath", ()))


@functools.lru_cache(maxsize=None)
def _load_font_file(path: Path, font_number: int) -> _OutlineFont:
    return _OutlineFont(path, font_number)


def _get_font(name: str) -> _OutlineFont:
    """Outline font registered under ``name``."""
    with _REGISTRY_LOCK:
        entry = _FONT_REGISTRY.get(name)
    if entry is None:
        raise ValueError(
            f"Unknown font {name!r}. Available fonts: {', '.join(available_fonts())}. "
            "Use register_font() to add a font file."
        )
    path, font_number = entry
    if not path.is_file():
        raise ValueError(f"Font file of {name!r} not found: {path}")
    return _load_font_file(path, font_number)


def available_fonts() -> list[str]:
    """Names usable as ``font``: the bundled fonts, then the registered ones
    (in registration order)."""
    with _REGISTRY_LOCK:
        return list(_FONT_REGISTRY)


def register_font(path: PathLike, name: Optional[str] = None, *, font_number: int = 0) -> str:
    """Make a font file usable as ``font``.

    Parameters
    ----------
    path : str or Path
        TrueType or OpenType font file (``.ttf``, ``.otf``, ``.ttc``, ``.otc``).
    name : str, optional
        Name to use as ``font``. Default: the file name without extension.
    font_number : int, default 0
        Index of the font inside a ``.ttc``/``.otc`` collection.

    Returns
    -------
    str
        The registered name.

    Raises
    ------
    ValueError
        Unreadable file, or ``name`` already used by another font.
        Registering the same file again under the same name does nothing.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError(f"path must be a str or Path, got {type(path).__name__}")
    file = safe_resolve(path)
    if file.suffix.lower() not in FONT_FILE_EXTENSIONS:
        raise ValueError(
            f"Unsupported font file {file.name}: expected one of "
            f"{', '.join(FONT_FILE_EXTENSIONS)}."
        )
    if not file.is_file():
        raise FileNotFoundError(f"Font file not found: {file}")
    if not _is_int(font_number) or font_number < 0:
        raise ValueError("font_number must be an int >= 0.")

    if name is None:
        name = file.stem
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Font name must be a non-empty str.")

    _load_font_file(file, int(font_number))  # validate before registering

    entry = (file, int(font_number))
    with _REGISTRY_LOCK:
        existing = _FONT_REGISTRY.get(name)
        if existing is not None and existing != entry:
            raise ValueError(f"Font name {name!r} is already used by {existing[0].name}.")
        _FONT_REGISTRY[name] = entry
    return name


@dataclass(frozen=True)
class WatermarkStyle:
    """Validated watermark settings.

    Parameters
    ----------
    text : str
        Watermark text. ``\\n`` starts a new line.
    horizontal_boxes, vertical_boxes : int
        Number of columns and rows of the grid.
    margin : bool or float
        Blank border around the grid, in points. ``True`` means
        :data:`DEFAULT_MARGIN`, ``False`` means no margin.
    opacity : float
        Opacity in ``[0, 1]``.
    angle : float
        Counter-clockwise rotation, in degrees.
    color : str
        ``#RRGGBB`` color.
    font : str
        Font name: one of :data:`BUNDLED_FONTS` or a name added with
        :func:`register_font` (see :func:`available_fonts`). Characters the
        font cannot draw raise :class:`ValueError`.
    size : float
        Font size, in points.
    """

    text: str
    horizontal_boxes: int = 3
    vertical_boxes: int = 6
    margin: Union[bool, float] = False
    opacity: float = 0.1
    angle: float = 45.0
    color: str = "#000000"
    font: str = DEFAULT_FONT
    size: float = 12.0

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError(f"text must be a str, got {type(self.text).__name__}")
        if not self.text.strip():
            raise ValueError("Watermark text must not be empty.")

        for name in ("horizontal_boxes", "vertical_boxes"):
            value = getattr(self, name)
            if not _is_int(value):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}")
            if value < 1:
                raise ValueError(f"{name} must be at least 1.")
            object.__setattr__(self, name, int(value))  # numpy int -> int

        if isinstance(self.margin, bool):
            pass
        elif isinstance(self.margin, numbers.Real):
            if not _is_number(self.margin):
                raise ValueError("margin must be a finite number.")
            if self.margin < 0:
                raise ValueError("margin must be positive or zero.")
            object.__setattr__(self, "margin", float(self.margin))
        else:
            raise TypeError(
                f"margin must be a bool or a number, got {type(self.margin).__name__}"
            )

        for name in ("opacity", "angle", "size"):
            value = getattr(self, name)
            if not isinstance(value, numbers.Real) or isinstance(value, bool):
                raise TypeError(f"{name} must be a number, got {type(value).__name__}")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number, got {value!r}.")
            object.__setattr__(self, name, float(value))

        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity must be between 0 and 1.")
        if self.size <= 0:
            raise ValueError("Font size must be positive.")

        _rgb_from_hex(self.color)

        if not isinstance(self.font, str):
            raise TypeError(f"font must be a str, got {type(self.font).__name__}")
        missing = _get_font(self.font).missing_characters("".join(self.lines))
        if missing:
            raise ValueError(
                f"Font {self.font!r} cannot draw: {' '.join(missing)}. "
                "Choose (or register) a font covering these characters."
            )

    # ------------------------------------------------------------------
    @property
    def margin_size(self) -> float:
        """Margin in points."""
        if isinstance(self.margin, bool):
            return DEFAULT_MARGIN if self.margin else 0.0
        return float(self.margin)

    @property
    def lines(self) -> list[str]:
        """Text lines, stripped (leading/trailing blank lines removed)."""
        return [line.strip() for line in self.text.strip("\n").split("\n")]

    @property
    def rgb(self) -> tuple[float, float, float]:
        return _rgb_from_hex(self.color)

    def cell_centers(self, width: float, height: float):
        """Yield the ``(x, y)`` center of each grid cell (PDF coordinates,
        origin at the bottom-left corner)."""
        margin = self.margin_size
        available_w = width - 2 * margin
        available_h = height - 2 * margin
        if available_w <= 0 or available_h <= 0:
            raise ValueError(
                f"Margin ({margin:g} pt) too large for the page "
                f"({width:g} x {height:g} pt)."
            )
        step_x = available_w / self.horizontal_boxes
        step_y = available_h / self.vertical_boxes
        for row in range(self.vertical_boxes):
            for column in range(self.horizontal_boxes):
                yield (
                    margin + (column + 0.5) * step_x,
                    margin + (row + 0.5) * step_y,
                )


def _style_from_kwargs(text: str, kwargs: dict) -> WatermarkStyle:
    unknown = set(kwargs) - set(WatermarkStyle.__dataclass_fields__)
    if unknown:
        raise TypeError(f"Unexpected watermark option(s): {', '.join(sorted(unknown))}")
    return WatermarkStyle(text=text, **kwargs)


# ============================================================================
# Drawing
# ============================================================================

@functools.lru_cache(maxsize=64)
def _text_block_outline(font_name: str, size: float, lines: tuple[str, ...]) -> tuple:
    font = _get_font(font_name)
    recorder = _OutlineRecorder(font.glyph_set)
    line_height = size * LINE_SPACING
    baseline = (len(lines) - 1) * line_height / 2
    for line in lines:
        if line:
            font.draw_line(recorder, line, -font.line_width(line, size) / 2, baseline, size)
        baseline -= line_height
    return tuple(recorder.operations)


def text_block_outline(style: WatermarkStyle) -> tuple[tuple[str, tuple], ...]:
    """Outline of one watermark text block, exactly as drawn in the PDF.

    The block (all lines) is centered on the origin, in points, with the
    y axis pointing up and no rotation. Each item is ``(operator, points)``
    with ``operator`` in ``"moveTo"``, ``"lineTo"`` (one point),
    ``"curveTo"`` (three points: cubic Bezier) and ``"closePath"`` (none).
    The outline must be filled with the non-zero winding rule.

    Useful to draw an exact preview with another toolkit (e.g. Qt).
    """
    return _text_block_outline(style.font, style.size, tuple(style.lines))


def _draw_text_block(can, style: WatermarkStyle) -> None:
    """Draw the text block as filled outlines, using the current fill color."""
    path = can.beginPath()
    for operator, points in text_block_outline(style):
        if operator == "moveTo":
            path.moveTo(*points[0])
        elif operator == "lineTo":
            path.lineTo(*points[0])
        elif operator == "curveTo":
            path.curveTo(*points[0], *points[1], *points[2])
        else:
            path.close()
    can.drawPath(path, stroke=0, fill=1, fillMode=FILL_NON_ZERO)


def _draw_watermark_grid(can, width: float, height: float, style: WatermarkStyle) -> None:
    """Draw the watermark grid on a ReportLab canvas.

    The text block is drawn once into a form XObject, then placed in every
    cell: the outlines are stored only once per page size.
    """
    font = _get_font(style.font)
    lines = style.lines
    half_w = max(font.line_width(line, style.size) for line in lines) / 2 + style.size
    half_h = len(lines) * style.size * LINE_SPACING / 2 + style.size

    can.beginForm("watermark", -half_w, -half_h, half_w, half_h)
    _draw_text_block(can, style)
    can.endForm()

    r, g, b = style.rgb
    can.setFillColorRGB(r, g, b, alpha=style.opacity)
    for x, y in style.cell_centers(width, height):
        can.saveState()
        can.translate(x, y)
        can.rotate(style.angle)
        can.doForm("watermark")
        can.restoreState()


#: Marked-content wrapper declaring the watermark as a pagination artifact
#: (ISO 32000, 14.8.2.2): compliant readers leave it out of text selection,
#: copy, search and screen readers, and tagged PDFs stay valid.
_ARTIFACT_BEGIN = b"/Artifact <</Type /Pagination /Subtype /Watermark>> BDC\n"
_ARTIFACT_END = b"\nEMC\n"


def _create_watermark_overlay(width: float, height: float, style: WatermarkStyle) -> PageObject:
    """Return a one-page PDF page containing only the watermark, wrapped
    in an ``/Artifact`` marked-content sequence."""
    packet = BytesIO()
    can = pdfcanvas.Canvas(packet, pagesize=(width, height))
    _draw_watermark_grid(can, width, height, style)
    can.showPage()
    can.save()
    packet.seek(0)

    page = PdfWriter(clone_from=PdfReader(packet)).pages[0]

    # ReportLab always declares Helvetica; the watermark uses no font at all
    # (outlines only), so drop it rather than adding it to every page.
    resources = page["/Resources"].get_object()
    forms = [xobject.get_object() for xobject in resources.get("/XObject", {}).values()]
    for dictionary in [resources] + [form["/Resources"].get_object() for form in forms]:
        for key in ("/Font", "/ProcSet"):
            dictionary.pop(key, None)

    stream = DecodedStreamObject()
    stream.set_data(_ARTIFACT_BEGIN + page.get_contents().get_data() + _ARTIFACT_END)
    page.replace_contents(stream)
    return page


def _display_geometry(page) -> tuple[float, float, Transformation]:
    """Return the size of the page *as displayed* and the transformation that
    maps displayed coordinates onto the page's own coordinate system.

    Takes the crop box offset and the ``/Rotate`` attribute into account, so
    the watermark is always upright and centered on the visible area.
    Annotations (links, form fields) are left untouched.
    """
    box = page.cropbox
    x0, y0 = float(box.left), float(box.bottom)
    w, h = float(box.width), float(box.height)
    rotation = (page.get("/Rotate", 0) or 0) % 360

    if rotation in (90, 270):
        display_w, display_h = h, w
    else:
        display_w, display_h = w, h

    trsf = Transformation().rotate(rotation)
    corners = [
        trsf.apply_on(p) for p in ((0, 0), (display_w, 0), (0, display_h), (display_w, display_h))
    ]
    min_x = min(p[0] for p in corners)
    min_y = min(p[1] for p in corners)
    trsf = trsf.translate(x0 - min_x, y0 - min_y)
    return display_w, display_h, trsf


# ============================================================================
# Helpers
# ============================================================================

def _open_pdf(path: Path, owner_password: Optional[str] = None) -> PdfReader:
    """Open a PDF, decrypting it if needed.

    Only PDFs without an opening (user) password are supported; many
    "protected" PDFs only have an owner password restricting printing,
    copying... If ``owner_password`` is given and the PDF is encrypted, it
    must be the owner password of the PDF. It is ignored for unencrypted PDFs.
    """
    reader = PdfReader(str(path))
    if not reader.is_encrypted:
        return reader
    if not reader.decrypt(""):
        raise PermissionError(
            f"The PDF requires a password to be opened (not supported): {path.name}"
        )
    if owner_password is not None:
        if reader.decrypt(owner_password) != PasswordType.OWNER_PASSWORD:
            raise PermissionError(f"Incorrect owner password for {path.name}")
    return reader


def _encryption_algorithm(reader: PdfReader) -> str:
    """pypdf algorithm name matching the encryption of ``reader``."""
    encrypt = reader.trailer["/Encrypt"]
    v = int(encrypt.get("/V", 0))
    r = int(encrypt.get("/R", 0))
    if v >= 5:
        return "AES-256" if r >= 6 else "AES-256-R5"
    if v == 4:
        filters = encrypt.get("/CF", {})
        stream_filter = filters.get(encrypt.get("/StmF", "/StdCF"), {})
        return "AES-128" if stream_filter.get("/CFM") == "/AESV2" else "RC4-128"
    if v in (2, 3) or r >= 3:
        return "RC4-128"
    return "RC4-40"


def _copy_encryption(
    reader: PdfReader, writer: PdfWriter, owner_password: Optional[str] = None
) -> None:
    """Re-apply the encryption of ``reader`` (algorithm and permissions) to
    ``writer``.

    Only PDFs with an empty user password can be opened here, so the output
    keeps an empty user password. The owner password of the output is
    ``owner_password`` (already checked by :func:`_open_pdf`); when it is not
    given, the original one is unknown and a random one is used: the
    restrictions (printing, copying...) stay in place, but nobody, including
    the original owner, can lift them on the output with a compliant reader.
    """
    if not reader.is_encrypted:
        return
    writer.encrypt(
        user_password="",
        owner_password=(
            owner_password if owner_password is not None else secrets.token_urlsafe(32)
        ),
        permissions_flag=reader.user_access_permissions,
        algorithm=_encryption_algorithm(reader),
    )


def _as_page_list(pages: PageSelection) -> Optional[list[int]]:
    """Check a page selection without the PDF: ``None`` or a list of ints."""
    if pages is None:
        return None
    if _is_int(pages):
        return [int(pages)]
    if isinstance(pages, (str, bytes)):
        raise TypeError("pages must be None, an int or a list of ints, got str")
    try:
        pages = list(pages)
    except TypeError:
        raise TypeError(
            f"pages must be None, an int or a list of ints, got {type(pages).__name__}"
        ) from None
    if not pages:
        raise ValueError("pages must not be empty (use None for all pages).")
    for page in pages:
        if not _is_int(page):
            raise TypeError(f"Page indices must be ints, got {type(page).__name__}")
    return [int(page) for page in pages]


def _is_page_selected(index: int, n_pages: int, pages: Optional[frozenset[int]]) -> bool:
    """Whether the 0-based page ``index`` of a PDF of ``n_pages`` pages is
    selected. ``pages`` may contain negative indices (``-1`` = last page);
    indices that do not exist in this PDF are simply ignored."""
    return pages is None or index in pages or index - n_pages in pages


def count_pdf_pages(path: PathLike) -> int:
    """Return the number of pages of a PDF."""
    return len(_open_pdf(Path(path)).pages)


def get_page_size(path: PathLike, page_index: int = 0) -> tuple[float, float]:
    """Return the size ``(width, height)`` in points of a page *as displayed*
    (crop box and ``/Rotate`` taken into account)."""
    reader = _open_pdf(Path(path))
    width, height, _ = _display_geometry(reader.pages[page_index])
    return width, height


def _check_cancel(cancel_event: Optional[_EventLike]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise WatermarkCancelled("Operation cancelled.")


def _create_temp_file(directory: Path, stem: str) -> tuple[int, str]:
    """Create a new empty file in ``directory`` with the default permissions
    of a regular file (``0o666`` minus the umask), unlike
    :func:`tempfile.mkstemp` which always uses ``0o600``."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    while True:
        name = os.path.join(directory, f".{stem}.{secrets.token_hex(6)}.tmp")
        try:
            return os.open(name, flags, 0o666), name
        except FileExistsError:
            continue


def _write_atomically(writer: PdfWriter, destination: Path) -> None:
    """Write to a temporary file then rename it.

    The destination is never left half-written, and the input file can
    safely be overwritten (empty suffix). A new file gets the default
    permissions; an overwritten file keeps its own permissions.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = _create_temp_file(destination.parent, destination.stem)
    try:
        with os.fdopen(fd, "wb") as file:
            writer.write(file)
        with contextlib.suppress(FileNotFoundError):
            os.chmod(tmp_name, stat.S_IMODE(destination.stat().st_mode))
        os.replace(tmp_name, destination)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def _default_output(input_file: Path, suffix: str) -> Path:
    return input_file.with_name(f"{input_file.stem}{suffix}{input_file.suffix}")


def _check_destinations(destinations: Iterable[Path], overwrite: bool) -> None:
    """Raise :class:`DestinationExistsError` if one of them exists and
    ``overwrite`` is false."""
    if overwrite:
        return
    existing = [path for path in destinations if os.path.lexists(path)]
    if existing:
        raise DestinationExistsError(existing)


def _check_common_options(suffix, owner_password, overwrite) -> None:
    if not isinstance(suffix, str):
        raise TypeError(f"suffix must be a str, got {type(suffix).__name__}")
    if owner_password is not None and not isinstance(owner_password, str):
        raise TypeError(
            f"owner_password must be a str, got {type(owner_password).__name__}"
        )
    if not isinstance(overwrite, bool):
        raise TypeError(f"overwrite must be a bool, got {type(overwrite).__name__}")


def _run_jobs(
    jobs: list[tuple[Path, Path, Optional[list[int]]]],
    text: str,
    style_kwargs: dict,
    *,
    overwrite: bool,
    owner_password: Optional[str],
    verbose: bool,
    progress_callback: Optional[ProgressCallback],
    cancel_event: Optional[_EventLike],
) -> dict[str, str]:
    """Watermark ``(input, output, pages)`` jobs one after the other, with a
    progress reported over the total number of pages."""
    results: dict[str, str] = {}

    page_counts: dict[Path, int] = {}
    for input_file, _, _ in jobs:
        _check_cancel(cancel_event)
        try:
            page_counts[input_file] = count_pdf_pages(input_file)
        except Exception as exc:
            results[str(input_file)] = f"ERROR: {type(exc).__name__}: {exc}"

    total_pages = sum(page_counts.values())
    done_pages = 0

    bar = None
    if verbose and tqdm is not None and progress_callback is None:
        bar = tqdm(total=total_pages, desc="Watermarking", unit="page", leave=False,
                   dynamic_ncols=True)

    def forward(done: int, total: int, name: str) -> None:
        if bar is not None:
            bar.n = done
            bar.refresh()
        if progress_callback is not None:
            progress_callback(done, total, name)

    runnable = [job for job in jobs if job[0] in page_counts]
    try:
        for index, (input_file, destination, pages) in enumerate(runnable, start=1):
            if bar is not None:
                bar.set_description(f"[{index}/{len(runnable)}] {input_file.name[:40]}")
            try:
                results[str(input_file)] = add_watermark(
                    input_file,
                    text,
                    output_path=destination,
                    pages=pages,
                    overwrite=overwrite,
                    owner_password=owner_password,
                    verbose=False,
                    progress_callback=forward,
                    cancel_event=cancel_event,
                    _page_offset=done_pages,
                    _total_pages=total_pages,
                    **style_kwargs,
                )
            except WatermarkCancelled:
                raise
            except Exception as exc:
                results[str(input_file)] = f"ERROR: {type(exc).__name__}: {exc}"
            done_pages += page_counts[input_file]
            forward(done_pages, total_pages, input_file.name)
    finally:
        if bar is not None:
            bar.close()

    # Same order as the jobs.
    return {str(job[0]): results[str(job[0])] for job in jobs}


# ============================================================================
# Public API
# ============================================================================

def add_watermark(
    input_path: PathLike,
    text: str,
    *,
    output_path: Optional[PathLike] = None,
    suffix: str = "_watermarked",
    pages: PageSelection = None,
    overwrite: bool = False,
    owner_password: Optional[str] = None,
    horizontal_boxes: int = 3,
    vertical_boxes: int = 6,
    margin: Union[bool, float] = False,
    opacity: float = 0.1,
    angle: float = 45,
    color: str = "#000000",
    font: str = DEFAULT_FONT,
    size: float = 12,
    verbose: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event: Optional[_EventLike] = None,
    _page_offset: int = 0,
    _total_pages: Optional[int] = None,
) -> str:
    """Add a watermark grid to every page of a PDF.

    Parameters
    ----------
    input_path : str or Path
        Input PDF.
    text : str
        Watermark text (``\\n`` for multiple lines).
    output_path : str or Path, optional
        Output PDF. Default: ``<input stem><suffix>.pdf`` next to the input.
        It may be equal to ``input_path`` (the file is replaced safely,
        ``overwrite=True`` needed).
    suffix : str, default "_watermarked"
        Suffix used when ``output_path`` is omitted. An empty suffix
        replaces the input file (``overwrite=True`` needed).
    pages : None, int or list of int, default None
        Pages to watermark, as 0-based indices (negative indices count from
        the end, ``-1`` is the last page). ``None`` means every page.
        Indices that do not exist in the PDF are ignored. The other pages
        are copied unchanged.
    overwrite : bool, default False
        Replace the output file if it already exists. Otherwise
        :class:`DestinationExistsError` is raised and nothing is written.
    owner_password : str, optional
        Owner password of an encrypted input. It is checked
        (:class:`PermissionError` if wrong) and set as the owner password of
        the output, so the owner keeps control of the watermarked copy.
        Without it, a random owner password is used. Ignored for
        unencrypted inputs.
    horizontal_boxes, vertical_boxes, margin, opacity, angle, color, font, size
        See :class:`WatermarkStyle`.
    verbose : bool, default True
        Display a tqdm progress bar in the console (if tqdm is installed).
    progress_callback : callable, optional
        ``progress_callback(done_pages, total_pages, file_name)``.
    cancel_event : threading.Event, optional
        Stops the processing when set (raises :class:`WatermarkCancelled`).

    Returns
    -------
    str
        Path of the generated PDF.

    Notes
    -----
    Bookmarks, metadata, links and form fields of the input are preserved.
    An encrypted input (owner password only) gives an output encrypted with
    the same algorithm and permissions; see ``owner_password``. PDFs that
    require a password to be opened are not supported.
    """
    style = WatermarkStyle(
        text=text,
        horizontal_boxes=horizontal_boxes,
        vertical_boxes=vertical_boxes,
        margin=margin,
        opacity=opacity,
        angle=angle,
        color=color,
        font=font,
        size=size,
    )

    if not isinstance(input_path, (str, os.PathLike)):
        raise TypeError(f"input_path must be a str or Path, got {type(input_path).__name__}")
    input_file = Path(input_path)
    if not input_file.is_file():
        raise FileNotFoundError(f"Input PDF file not found: {input_file}")

    if not isinstance(suffix, str):
        raise TypeError(f"suffix must be a str, got {type(suffix).__name__}")
    if output_path is not None and not isinstance(output_path, (str, os.PathLike)):
        raise TypeError(f"output_path must be a str or Path, got {type(output_path).__name__}")

    output_file = Path(output_path) if output_path is not None else _default_output(input_file, suffix)
    if not isinstance(overwrite, bool):
        raise TypeError(f"overwrite must be a bool, got {type(overwrite).__name__}")
    _check_destinations([output_file], overwrite)
    pages = _as_page_list(pages)
    if owner_password is not None and not isinstance(owner_password, str):
        raise TypeError(
            f"owner_password must be a str, got {type(owner_password).__name__}"
        )

    _check_cancel(cancel_event)
    reader = _open_pdf(input_file, owner_password)
    writer = PdfWriter(clone_from=reader)  # keeps outline, metadata, links...
    n_pages = len(writer.pages)
    selected = frozenset(pages) if pages is not None else None
    total = _total_pages if _total_pages is not None else n_pages

    # One overlay per distinct displayed page size.
    overlays: dict[tuple[float, float], object] = {}

    bar = None
    if verbose and tqdm is not None and progress_callback is None:
        bar = tqdm(total=n_pages, desc=f"Watermarking {input_file.name}", unit="page", leave=False)

    try:
        for index, page in enumerate(writer.pages, start=1):
            _check_cancel(cancel_event)

            if _is_page_selected(index - 1, n_pages, selected):
                width, height, trsf = _display_geometry(page)
                key = (round(width, 2), round(height, 2))
                if key not in overlays:
                    overlays[key] = _create_watermark_overlay(width, height, style)
                page.merge_transformed_page(overlays[key], trsf)

            if bar is not None:
                bar.update(1)
            if progress_callback is not None:
                progress_callback(_page_offset + index, total, input_file.name)

        _check_cancel(cancel_event)
        _copy_encryption(reader, writer, owner_password)
        _check_destinations([output_file], overwrite)  # created meanwhile?
        _write_atomically(writer, output_file)
    finally:
        if bar is not None:
            bar.close()

    return str(output_file)


def _iter_pdf_files(input_dir: Path, pattern: str, recursive: bool, exclude: Optional[Path]):
    candidates = input_dir.rglob(pattern) if recursive else input_dir.glob(pattern)
    for path in sorted(candidates):
        if not path.is_file() or path.name.startswith("."):
            continue
        if exclude is not None and exclude != input_dir and exclude in path.parents:
            continue  # never re-process our own output folder
        yield path


def batch_watermark_directory(
    directory_path: PathLike,
    text: str,
    *,
    output_dir: Optional[PathLike] = None,
    suffix: str = "_watermarked",
    pattern: str = "*.pdf",
    recursive: bool = False,
    pages: PageSelection = None,
    overwrite: bool = False,
    owner_password: Optional[str] = None,
    verbose: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event: Optional[_EventLike] = None,
    **watermark_kwargs,
) -> dict[str, str]:
    """Add a watermark to every PDF of a directory.

    Parameters
    ----------
    directory_path : str or Path
        Folder containing the PDFs.
    text : str
        Watermark text.
    output_dir : str or Path, optional
        Destination folder. Default: sibling folder ``<folder name><suffix>``.
        With an empty suffix, files are replaced in place
        (``overwrite=True`` needed).
    suffix : str, default "_watermarked"
        Appended to every output file name (and to the default folder name).
    pattern : str, default "*.pdf"
        Glob pattern of the files to process.
    recursive : bool, default False
        Also process sub-folders. The folder structure is reproduced in
        ``output_dir``.
    pages : None, int or list of int, default None
        Pages to watermark in every file (see :func:`add_watermark`).
        Pages missing from a shorter file are ignored.
    overwrite : bool, default False
        If the destination folder already exists, it is **deleted and
        replaced** by the new one. Otherwise :class:`DestinationExistsError`
        is raised and nothing is written. The new folder is first built
        under a temporary name: the old one is only deleted once the
        generation succeeded (it is kept if it is cancelled or if no file
        could be watermarked). Exception: when the destination is the input
        folder itself (empty suffix), files are replaced in place and
        nothing is deleted.
    owner_password : str, optional
        Owner password used for every encrypted file (see
        :func:`add_watermark`). An encrypted file with another owner
        password is reported as an error.
    verbose : bool, default True
        Display a tqdm progress bar in the console (if tqdm is installed).
    progress_callback, cancel_event
        See :func:`add_watermark`. Progress is reported over the total
        number of pages of all files.
    **watermark_kwargs
        Style options passed to :func:`add_watermark`.

    Returns
    -------
    dict[str, str]
        ``{input path: output path}``, or ``"ERROR: ..."`` for files that failed.
        A failing file does not stop the batch; a cancellation does.

    Raises
    ------
    ValueError
        The destination folder contains the input folder (deleting it would
        delete the inputs).
    DestinationExistsError
        See ``overwrite``.
    """
    if not isinstance(directory_path, (str, os.PathLike)):
        raise TypeError(
            f"directory_path must be a str or Path, got {type(directory_path).__name__}"
        )
    input_dir = Path(directory_path)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Directory not found: {input_dir}")

    _check_common_options(suffix, owner_password, overwrite)
    if output_dir is not None and not isinstance(output_dir, (str, os.PathLike)):
        raise TypeError(f"output_dir must be a str, Path or None, got {type(output_dir).__name__}")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("pattern must be a non-empty str.")
    if not isinstance(recursive, bool):
        raise TypeError(f"recursive must be a bool, got {type(recursive).__name__}")

    # Validate everything before touching any file.
    _style_from_kwargs(text, watermark_kwargs)
    pages = _as_page_list(pages)

    output_root = (
        Path(output_dir) if output_dir is not None
        else input_dir.with_name(f"{input_dir.name}{suffix}")
    )
    in_place = path_key(output_root) == path_key(input_dir)
    if not in_place and path_key(output_root) in {
        path_key(parent) for parent in safe_resolve(input_dir).parents
    }:
        raise ValueError(
            f"The destination folder {output_root} contains the input folder."
        )
    _check_destinations([output_root], overwrite)

    pdf_files = [
        path for path in _iter_pdf_files(input_dir, pattern, recursive, output_root)
        # skip outputs of a previous run (e.g. "report_watermarked.pdf")
        if not (suffix and path.stem.endswith(suffix))
    ]

    # Replacing an existing folder: build the new one aside, swap at the end.
    replace = overwrite and not in_place and os.path.lexists(output_root)
    work_root = (
        output_root.with_name(f".{output_root.name}.{secrets.token_hex(4)}.tmp")
        if replace else output_root
    )

    jobs = [
        (path, work_root / path.relative_to(input_dir).parent
         / f"{path.stem}{suffix}{path.suffix}", pages)
        for path in pdf_files
    ]
    try:
        results = _run_jobs(
            jobs, text, watermark_kwargs,
            overwrite=overwrite, owner_password=owner_password, verbose=verbose,
            progress_callback=progress_callback, cancel_event=cancel_event,
        )
    except BaseException:
        if replace:
            _remove_path(work_root)
        raise

    if replace:
        if any(not value.startswith("ERROR") for value in results.values()):
            _remove_path(output_root)
            os.replace(work_root, output_root)
            results = {
                key: value if value.startswith("ERROR")
                else str(output_root / Path(value).relative_to(work_root))
                for key, value in results.items()
            }
        else:  # nothing generated: keep the previous folder
            _remove_path(work_root)
    return results


def _remove_path(path: Path) -> None:
    """Delete a file, a link or a whole folder (no error if missing)."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def watermark_files(
    files: Union[Iterable[PathLike], Mapping[PathLike, PageSelection]],
    text: str,
    *,
    suffix: str = "_watermarked",
    pages: PageSelection = None,
    overwrite: bool = False,
    owner_password: Optional[str] = None,
    verbose: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event: Optional[_EventLike] = None,
    **watermark_kwargs,
) -> dict[str, str]:
    """Add a watermark to several PDF files, each output next to its input.

    Parameters
    ----------
    files : iterable of paths, or mapping ``{path: pages}``
        Input PDFs. With a mapping, each file gets its own page selection
        (see :func:`add_watermark`); ``None`` uses ``pages``.
    text : str
        Watermark text.
    suffix : str, default "_watermarked"
        Output of ``dir/name.pdf`` is ``dir/name<suffix>.pdf``. An empty
        suffix replaces the inputs (``overwrite=True`` needed).
    pages : None, int or list of int, default None
        Default page selection (0-based indices, ``None`` = every page).
    overwrite : bool, default False
        Replace existing outputs. Otherwise, if any output already exists,
        :class:`DestinationExistsError` is raised and nothing is written.
    owner_password, verbose, progress_callback, cancel_event
        See :func:`batch_watermark_directory`.
    **watermark_kwargs
        Style options (see :class:`WatermarkStyle`).

    Returns
    -------
    dict[str, str]
        ``{input path: output path}`` in the input order, or ``"ERROR: ..."``
        for files that failed. A failing file does not stop the others;
        a cancellation does.

    Raises
    ------
    FileNotFoundError
        An input file does not exist.
    ValueError
        The same file is given twice, or an output would replace another
        input.
    DestinationExistsError
        See ``overwrite``.
    """
    _check_common_options(suffix, owner_password, overwrite)
    _style_from_kwargs(text, watermark_kwargs)
    default_pages = _as_page_list(pages)

    if isinstance(files, (str, bytes, os.PathLike)):
        raise TypeError("files must be a collection of paths, not a single path.")
    items = list(files.items()) if isinstance(files, Mapping) else [(f, None) for f in files]
    if not items:
        raise ValueError("No input file given.")

    jobs: list[tuple[Path, Path, Optional[list[int]]]] = []
    seen: dict[str, Path] = {}
    for path, file_pages in items:
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError(f"File paths must be str or Path, got {type(path).__name__}")
        input_file = Path(path)
        if not input_file.is_file():
            raise FileNotFoundError(f"Input PDF file not found: {input_file}")
        key = path_key(input_file)
        if key in seen:
            raise ValueError(f"File given twice: {input_file}")
        seen[key] = input_file
        file_pages = _as_page_list(file_pages) if file_pages is not None else default_pages
        jobs.append((input_file, _default_output(input_file, suffix), file_pages))

    for input_file, destination, _ in jobs:
        target = path_key(destination)
        if target in seen and seen[target] != input_file:
            raise ValueError(
                f"The output of {input_file.name} would replace another input: {destination}"
            )
    _check_destinations([destination for _, destination, _ in jobs], overwrite)

    return _run_jobs(
        jobs, text, watermark_kwargs,
        overwrite=overwrite, owner_password=owner_password, verbose=verbose,
        progress_callback=progress_callback, cancel_event=cancel_event,
    )

    # Count pages first, to report a global progress.
    page_counts: dict[Path, int] = {}
    for input_file in pdf_files:
        _check_cancel(cancel_event)
        try:
            page_counts[input_file] = count_pdf_pages(input_file)
        except Exception as exc:
            results[str(input_file)] = f"ERROR: {type(exc).__name__}: {exc}"

    total_pages = sum(page_counts.values())
    done_pages = 0

    bar = None
    if verbose and tqdm is not None and progress_callback is None:
        bar = tqdm(total=total_pages, desc="Watermarking", unit="page", leave=False,
                   dynamic_ncols=True)

    def forward(done: int, total: int, name: str) -> None:
        if bar is not None:
            bar.n = done
            bar.refresh()
        if progress_callback is not None:
            progress_callback(done, total, name)

    try:
        for index, (input_file, n_pages) in enumerate(page_counts.items(), start=1):
            relative = input_file.relative_to(input_dir)
            destination = output_root / relative.parent / (
                f"{input_file.stem}{suffix}{input_file.suffix}"
            )
            if bar is not None:
                bar.set_description(f"[{index}/{len(page_counts)}] {input_file.name[:40]}")
            try:
                results[str(input_file)] = add_watermark(
                    input_file,
                    text,
                    output_path=destination,
                    pages=pages,
                    owner_password=owner_password,
                    verbose=False,
                    progress_callback=forward,
                    cancel_event=cancel_event,
                    _page_offset=done_pages,
                    _total_pages=total_pages,
                    **watermark_kwargs,
                )
            except WatermarkCancelled:
                raise
            except Exception as exc:
                results[str(input_file)] = f"ERROR: {type(exc).__name__}: {exc}"
            done_pages += n_pages
            forward(done_pages, total_pages, input_file.name)
    finally:
        if bar is not None:
            bar.close()

    return results
