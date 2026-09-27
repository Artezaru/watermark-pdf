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

The watermark is a grid of (optionally multi-line, rotated) text blocks drawn
with ReportLab and merged on top of every page with pypdf.

Public API
----------
- :func:`add_watermark`              -- watermark one PDF file
- :func:`batch_watermark_directory`  -- watermark every PDF of a folder
- :func:`create_watermark_template`  -- blank page containing the watermark
- :func:`count_pdf_pages`            -- number of pages of a PDF
- :class:`WatermarkCancelled`        -- raised when a cancellation is requested

Long operations accept two optional hooks, which make them easy to drive
from a GUI thread:

``progress_callback(done_pages, total_pages, current_file)``
    Called after every processed page.
``cancel_event``
    Any object with an ``is_set()`` method (e.g. :class:`threading.Event`).
    It is checked before every page; when set, the operation stops, no
    partial output file is left behind, and :class:`WatermarkCancelled`
    is raised.
"""

import contextlib
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional, Protocol, Union

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as pdfcanvas

try:  # tqdm is optional: only used for console progress bars.
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


__all__ = [
    "STANDARD_FONTS",
    "DEFAULT_MARGIN",
    "LINE_SPACING",
    "WatermarkCancelled",
    "WatermarkStyle",
    "add_watermark",
    "batch_watermark_directory",
    "count_pdf_pages",
    "create_watermark_template",
    "get_page_size",
]

PathLike = Union[str, os.PathLike]
ProgressCallback = Callable[[int, int, str], None]

#: The 12 text fonts every PDF reader must provide (no embedding needed).
STANDARD_FONTS = (
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
)

#: Margin (in points) used when ``margin=True`` is passed.
DEFAULT_MARGIN = 10.0

#: Distance between two baselines, as a multiple of the font size.
#: (Same value as ReportLab's default leading.)
LINE_SPACING = 1.2


class WatermarkCancelled(Exception):
    """Raised when the operation is cancelled through ``cancel_event``."""


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
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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
        ReportLab font name (one of :data:`STANDARD_FONTS`, or any font
        previously registered with ``pdfmetrics.registerFont``).
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
    font: str = "Helvetica"
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

        if isinstance(self.margin, bool):
            pass
        elif _is_number(self.margin):
            if self.margin < 0:
                raise ValueError("margin must be positive or zero.")
        else:
            raise TypeError(
                f"margin must be a bool or a number, got {type(self.margin).__name__}"
            )

        for name in ("opacity", "angle", "size"):
            value = getattr(self, name)
            if not _is_number(value):
                raise TypeError(f"{name} must be a number, got {type(value).__name__}")

        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity must be between 0 and 1.")
        if self.size <= 0:
            raise ValueError("Font size must be positive.")

        _rgb_from_hex(self.color)

        if not isinstance(self.font, str):
            raise TypeError(f"font must be a str, got {type(self.font).__name__}")
        try:
            pdfmetrics.getFont(self.font)
        except Exception as exc:
            raise ValueError(
                f"Unknown font {self.font!r}. Use one of: {', '.join(STANDARD_FONTS)}."
            ) from exc

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

def _draw_watermark_grid(can, width: float, height: float, style: WatermarkStyle) -> None:
    """Draw the watermark grid on a ReportLab canvas."""
    r, g, b = style.rgb
    can.setFillColorRGB(r, g, b, alpha=style.opacity)
    can.setFont(style.font, style.size)

    lines = style.lines
    line_height = style.size * LINE_SPACING
    first_baseline = (len(lines) - 1) * line_height / 2

    for x, y in style.cell_centers(width, height):
        can.saveState()
        can.translate(x, y)
        can.rotate(style.angle)
        baseline = first_baseline
        for line in lines:
            if line:
                can.drawCentredString(0, baseline, line)
            baseline -= line_height
        can.restoreState()


def _create_watermark_overlay(width: float, height: float, style: WatermarkStyle) -> BytesIO:
    """Return an in-memory one-page PDF containing only the watermark."""
    packet = BytesIO()
    can = pdfcanvas.Canvas(packet, pagesize=(width, height))
    _draw_watermark_grid(can, width, height, style)
    can.showPage()
    can.save()
    packet.seek(0)
    return packet


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

def _open_pdf(path: Path) -> PdfReader:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        # Many "protected" PDFs only have an owner password.
        if not reader.decrypt(""):
            raise PermissionError(f"The PDF is password-protected: {path.name}")
    return reader


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


def _write_atomically(writer: PdfWriter, destination: Path) -> None:
    """Write to a temporary file then rename it.

    The destination is never left half-written, and the input file can
    safely be overwritten (empty suffix).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as file:
            writer.write(file)
        os.replace(tmp_name, destination)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def _default_output(input_file: Path, suffix: str) -> Path:
    return input_file.with_name(f"{input_file.stem}{suffix}{input_file.suffix}")


# ============================================================================
# Public API
# ============================================================================

def add_watermark(
    input_path: PathLike,
    text: str,
    *,
    output_path: Optional[PathLike] = None,
    suffix: str = "_watermarked",
    horizontal_boxes: int = 3,
    vertical_boxes: int = 6,
    margin: Union[bool, float] = False,
    opacity: float = 0.1,
    angle: float = 45,
    color: str = "#000000",
    font: str = "Helvetica",
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
        It may be equal to ``input_path`` (the file is replaced safely).
    suffix : str, default "_watermarked"
        Suffix used when ``output_path`` is omitted. An empty suffix
        overwrites the input file.
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

    _check_cancel(cancel_event)
    reader = _open_pdf(input_file)
    writer = PdfWriter(clone_from=reader)  # keeps outline, metadata, links...
    n_pages = len(writer.pages)
    total = _total_pages if _total_pages is not None else n_pages

    # One overlay per distinct displayed page size.
    overlays: dict[tuple[float, float], object] = {}

    bar = None
    if verbose and tqdm is not None and progress_callback is None:
        bar = tqdm(total=n_pages, desc=f"Watermarking {input_file.name}", unit="page", leave=False)

    try:
        for index, page in enumerate(writer.pages, start=1):
            _check_cancel(cancel_event)

            width, height, trsf = _display_geometry(page)
            key = (round(width, 2), round(height, 2))
            if key not in overlays:
                overlays[key] = PdfReader(_create_watermark_overlay(width, height, style)).pages[0]

            page.merge_transformed_page(overlays[key], trsf)

            if bar is not None:
                bar.update(1)
            if progress_callback is not None:
                progress_callback(_page_offset + index, total, input_file.name)

        _check_cancel(cancel_event)
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
        With an empty suffix, files are overwritten in place.
    suffix : str, default "_watermarked"
        Appended to every output file name (and to the default folder name).
    pattern : str, default "*.pdf"
        Glob pattern of the files to process.
    recursive : bool, default False
        Also process sub-folders. The folder structure is reproduced in
        ``output_dir``.
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
    """
    if not isinstance(directory_path, (str, os.PathLike)):
        raise TypeError(
            f"directory_path must be a str or Path, got {type(directory_path).__name__}"
        )
    input_dir = Path(directory_path)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Directory not found: {input_dir}")

    if not isinstance(suffix, str):
        raise TypeError(f"suffix must be a str, got {type(suffix).__name__}")
    if output_dir is not None and not isinstance(output_dir, (str, os.PathLike)):
        raise TypeError(f"output_dir must be a str, Path or None, got {type(output_dir).__name__}")
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("pattern must be a non-empty str.")
    if not isinstance(recursive, bool):
        raise TypeError(f"recursive must be a bool, got {type(recursive).__name__}")

    # Validate the style once, before touching any file.
    _style_from_kwargs(text, watermark_kwargs)

    output_root = (
        Path(output_dir) if output_dir is not None
        else input_dir.with_name(f"{input_dir.name}{suffix}")
    )

    pdf_files = [
        path for path in _iter_pdf_files(input_dir, pattern, recursive, output_root)
        # skip outputs of a previous run (e.g. "report_watermarked.pdf")
        if not (suffix and path.stem.endswith(suffix))
    ]
    results: dict[str, str] = {}
    if not pdf_files:
        return results

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


def create_watermark_template(
    output_path: PathLike,
    text: str,
    *,
    page_width: float = 595.27,
    page_height: float = 841.89,
    **watermark_kwargs,
) -> str:
    """Create a blank PDF page containing only the watermark grid.

    Parameters
    ----------
    output_path : str or Path
        Output PDF.
    text : str
        Watermark text.
    page_width, page_height : float
        Page size in points (default: A4 portrait).
    **watermark_kwargs
        Style options (see :class:`WatermarkStyle`).

    Returns
    -------
    str
        Path of the generated PDF.
    """
    if not _is_number(page_width) or not _is_number(page_height):
        raise TypeError("Page dimensions must be numbers.")
    if page_width <= 0 or page_height <= 0:
        raise ValueError("Page dimensions must be positive.")

    style = _style_from_kwargs(text, watermark_kwargs)
    overlay = _create_watermark_overlay(page_width, page_height, style)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(overlay.getvalue())
    return str(output_file)