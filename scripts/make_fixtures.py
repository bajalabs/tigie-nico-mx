"""Cut the unit-test fixtures (tests/fixtures/tariff/) out of a real tariff capture.

    python3 scripts/make_fixtures.py <capture> tests/fixtures/tariff

Every source of `tigie_nico_mx/sources.json` becomes a small HTML file at the same relative path:
the operative paragraphs (no considerandos), the rows of the fracciones in FRACCIONES (and, in the
two Tarifa texts, the partidas, subpartidas and uncoded groups above them, with the first notes of
their chapters). The text is copied verbatim; only the markup is rewritten, plainly.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # run from a clone, no install

from tigie_nico_mx.html import Item, Para, Row, one_line, read_items
from tigie_nico_mx.sources import SOURCES
from tigie_nico_mx.tigie import FRACCION, HEADING, SUBHEADING, digits

FRACCIONES = [
    "0102.29.99",
    "0302.89.01",
    "0302.89.02",
    "0901.21.99",
    "0904.21.02",
    "1005.90.04",
    "1701.12.05",
    "1905.40.01",
    "3002.41.06",
    "3102.21.01",
    "5212.11.01",
    "5212.12.01",
    "7104.10.01",
    "7208.10.03",
    "7210.70.02",
    "7310.29.99",
    "8414.51.01",
    "8471.30.01",
    "8471.41.01",
    "8702.40.01",
    "9803.00.01",
]
WANTED = {digits(c) for c in FRACCIONES}
CHAPTERS = {c[:2] for c in WANTED}
NOTE_LINES = 3


def _keep_tree(items: list[Item]) -> list[Item]:
    out: list[Item] = []
    chapter: str | None = None
    notes = 0
    pending_group: Item | None = None
    in_tarifa = False
    section: list[Item] = []  # a section's heading, title and notes, kept once a chapter is
    for item in items:
        if isinstance(item, Para):
            text = one_line(item.text)
            if text == "TARIFA":
                in_tarifa = True
                out.append(item)
                continue
            if not in_tarifa:
                if len(out) < 3:
                    out.append(item)
                continue
            if text.startswith("Artículo 2o"):
                out.append(item)
                break
            if text.startswith("Sección "):
                chapter, notes, section = None, 0, [item]
                continue
            if text.startswith("Capítulo "):
                chapter = text.split()[1][:2]
                notes = 0
                if chapter in CHAPTERS:
                    out.extend(section)  # the section's own lines, before its first kept chapter
                    section = []
                    out.append(item)
                continue
            if notes < NOTE_LINES + 1:  # the title plus the first note lines
                if chapter is None:
                    section.append(item)
                    notes += 1
                elif chapter in CHAPTERS:
                    out.append(item)
                    notes += 1
            continue
        if chapter not in CHAPTERS or len(item.cells) != 6:
            continue
        code, dash = item.cells[0].strip(), item.cells[1].strip()
        if not code:
            if dash == "-":
                pending_group = item
            continue
        d = digits(code)
        if FRACCION.match(code):
            if d in WANTED:
                out.append(item)
        elif HEADING.match(code) or SUBHEADING.match(code):
            if any(w.startswith(d) for w in WANTED):
                if dash == "--" and pending_group is not None:
                    out.append(pending_group)
                    pending_group = None  # one group row before its first kept child
                out.append(item)
            if dash != "--":
                pending_group = None
    return out


def _keep_decree(items: list[Item]) -> list[Item]:
    out: list[Item] = []
    for item in items:
        if isinstance(item, Para):
            text = one_line(item.text)
            if text.startswith(("Que ", "CONSIDERANDO")) or len(text) > 3000:
                continue
            out.append(item)
        elif (
            item.cells and digits(item.cells[0]) in WANTED and FRACCION.match(item.cells[0].strip())
        ):
            out.append(item)
    return out


def _render(items: list[Item], origin: str) -> str:
    parts = [f"<!-- {origin} -->", "<html><body>"]
    table: int | None = None
    for item in items:
        if isinstance(item, Row):
            if table != item.table:
                if table is not None:
                    parts.append("</table>")
                parts.append("<table>")
                table = item.table
            cells = "".join(
                "<td>"
                + "".join(f"<p>{html.escape(line)}</p>" for line in cell.split("\n"))
                + "</td>"
                for cell in item.cells
            )
            parts.append(f"<tr>{cells}</tr>")
        else:
            if table is not None:
                parts.append("</table>")
                table = None
            parts.append(
                "<p>" + "<br>".join(html.escape(x) for x in item.text.split("\n")) + "</p>"
            )
    if table is not None:
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def main(capture: Path, out: Path) -> None:
    for source in SOURCES.values():
        items = read_items(capture / source.html)
        tree = source.key in ("ligie", "orig")
        kept = _keep_tree(items) if tree else _keep_decree(items)
        origin = (
            f"Cut from {source.url} ({source.authority}; sha256 {source.sha256[:16]}…) by "
            "scripts/make_fixtures.py; text verbatim, markup rewritten"
        )
        target = out / source.html
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render(kept, origin), encoding="utf-8")
        print(f"{source.html}: {len(kept)} items")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
