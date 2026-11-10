"""A LibreOffice HTML export of a Word file, read in document order.

The Cámara publishes the LIGIE and its decrees as Word 97 files; `soffice --convert-to html`
keeps their tables. This reader yields the paragraphs outside tables and the rows of top-level
tables, in order, with the page header and footer left out. Inside a cell, each paragraph becomes
one line; whitespace inside a paragraph (the export wraps long lines) collapses to one space.
"""

from __future__ import annotations

import html.parser
import re
from dataclasses import dataclass
from pathlib import Path

_SPACES = re.compile(r"[ \t\r\f\v ]+")
_BLOCKS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "li"})


@dataclass(frozen=True)
class Para:
    text: str


@dataclass(frozen=True)
class Row:
    table: int
    cells: tuple[str, ...]


Item = Para | Row


def _clean(parts: list[str]) -> str:
    lines = (_SPACES.sub(" ", line).strip() for line in "".join(parts).split("\n"))
    return "\n".join(line for line in lines if line)


class _Reader(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[Item] = []
        self._tables: list[int] = []
        self._count = -1
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._para: list[str] | None = None
        self._skip = 0
        self._divs: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script", "head", "title"):
            self._skip += 1
        if tag == "div":
            marginal = dict(attrs).get("title") in ("header", "footer")
            self._divs.append(marginal)
            self._skip += int(marginal)
        if tag == "table":
            self._count += 1
            self._tables.append(self._count)
        elif tag == "tr" and len(self._tables) == 1:
            self._row = []
        elif tag in ("td", "th") and self._row is not None and len(self._tables) == 1:
            self._cell = []
        elif tag in _BLOCKS or tag == "br":
            if self._cell is not None:
                self._cell.append("\n")
            elif not self._tables:
                if tag == "br":
                    if self._para is not None:
                        self._para.append("\n")
                else:
                    self._flush()
                    self._para = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head", "title"):
            self._skip -= 1
        if tag == "div" and self._divs:
            self._skip -= int(self._divs.pop())
        if tag == "table":
            if self._tables:
                self._tables.pop()
        elif tag in ("td", "th") and self._cell is not None and len(self._tables) == 1:
            if self._row is not None:
                self._row.append(_clean(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None and len(self._tables) == 1:
            if not self._skip:
                self.items.append(Row(self._tables[-1], tuple(self._row)))
            self._row = None
        elif tag in _BLOCKS and not self._tables:
            self._flush()

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data)
        if self._cell is not None:
            self._cell.append(text)
        elif self._para is not None:
            self._para.append(text)

    def _flush(self) -> None:
        if self._para is not None:
            text = _clean(self._para)
            if text and not self._skip:
                self.items.append(Para(text))
        self._para = None

    def finish(self) -> list[Item]:
        self.close()
        self._flush()
        return self.items


def parse_items(markup: str) -> list[Item]:
    reader = _Reader()
    reader.feed(markup)
    return reader.finish()


def read_items(path: Path) -> list[Item]:
    return parse_items(path.read_text(encoding="utf-8"))


def one_line(text: str) -> str:
    """A cell or paragraph as one line (its paragraphs joined by spaces)."""
    return " ".join(text.split())
