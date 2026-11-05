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

"""Page selections typed by the user, such as ``"1;5-9,12"``.

Syntax
------
- Page numbers start at 1 (as shown by PDF readers).
- Items are separated by ``;`` or ``,``; spaces around items and around
  ``-`` are ignored (but ``"1 2"`` is invalid, not page 12).
- ``a-b`` is the range of pages ``a`` to ``b``, both included (``a <= b``).
- An empty text means *every page*.

Example: ``"1, 5-9; 12"`` -> pages 1, 5, 6, 7, 8, 9 and 12.
"""

import re
from typing import Iterable, Optional

__all__ = [
    "MAX_PAGE_NUMBER",
    "PageSelectionError",
    "format_pages",
    "parse_pages",
    "to_page_indices",
]

#: Largest accepted page number (protects against "1-999999999").
MAX_PAGE_NUMBER = 100_000

_SEPARATORS = re.compile(r"[;,]")
_ITEM = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")


class PageSelectionError(ValueError):
    """Invalid page selection.

    ``code`` identifies the problem, ``details`` holds the values needed to
    build a (translated) message:

    ===============  ================================  =====================
    code             meaning                           details
    ===============  ================================  =====================
    ``syntax``       item is not ``n`` nor ``a-b``     ``token``
    ``zero``         page 0 (numbers start at 1)       ``token``
    ``reversed``     range ``a-b`` with ``a > b``      ``token``
    ``too_large``    number above MAX_PAGE_NUMBER      ``token``
    ``out_of_range`` page above the page count         ``page``, ``count``
    ===============  ================================  =====================
    """

    _MESSAGES = {
        "syntax": "{token!r} is not a page number or a range (e.g. 5-9).",
        "zero": "Page numbers start at 1 ({token!r}).",
        "reversed": "In {token!r}, the start of the range is greater than its end.",
        "too_large": "Page number too large in {token!r}.",
        "out_of_range": "Page {page} does not exist (the PDF has {count} page(s)).",
    }

    def __init__(self, code: str, **details) -> None:
        self.code = code
        self.details = details
        super().__init__(self._MESSAGES[code].format(**details))


def parse_pages(text: str, page_count: Optional[int] = None) -> Optional[list[int]]:
    """Parse a page selection.

    Parameters
    ----------
    text : str
        Selection typed by the user, e.g. ``"1;5-9,12"``.
    page_count : int, optional
        Number of pages of the PDF. When given, pages above it are rejected.

    Returns
    -------
    list of int or None
        Sorted unique 1-based page numbers, or ``None`` when ``text`` is
        empty (meaning every page).

    Raises
    ------
    PageSelectionError
        Invalid selection (see its ``code``).
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")

    pages: set[int] = set()
    for raw in _SEPARATORS.split(text):
        token = raw.strip()
        if not token:
            continue                          # "1;;2" or a trailing ";"
        match = _ITEM.match(token)
        if match is None:
            raise PageSelectionError("syntax", token=token)
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if start == 0 or end == 0:
            raise PageSelectionError("zero", token=token)
        if start > end:
            raise PageSelectionError("reversed", token=token)
        if end > MAX_PAGE_NUMBER:
            raise PageSelectionError("too_large", token=token)
        if page_count is not None and end > page_count:
            raise PageSelectionError("out_of_range", page=end, count=page_count)
        pages.update(range(start, end + 1))

    return sorted(pages) if pages else None   # nothing typed: every page


def to_page_indices(pages: Optional[Iterable[int]]) -> Optional[list[int]]:
    """1-based page numbers -> 0-based indices (``None`` stays ``None``)."""
    if pages is None:
        return None
    return [page - 1 for page in pages]


def format_pages(pages: Optional[Iterable[int]]) -> str:
    """Compact text of 1-based page numbers: ``[1, 5, 6, 7, 12]`` ->
    ``"1, 5-7, 12"``. ``None`` gives an empty text (every page)."""
    if pages is None:
        return ""
    numbers = sorted(set(pages))
    parts: list[str] = []
    i = 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        parts.append(str(numbers[i]) if i == j else f"{numbers[i]}-{numbers[j]}")
        i = j + 1
    return ", ".join(parts)
