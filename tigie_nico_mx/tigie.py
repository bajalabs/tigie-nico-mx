"""The Tarifa of LIGIE art. 1, from the Cámara's Word file (consolidated or as first published).

Between the paragraph "TARIFA" and "Artículo 2o.-" the law reads: "Sección I" + its title + its
notes; "Capítulo 01" + its title + its notes (paragraphs, sometimes small tables); then one table
per chapter whose rows are `[código, guiones, descripción, unidad, imp., exp.]`:

- `01.01` a partida (heading), `0101.21` a subpartida (one dash `-`, two dashes `--`, or none for a
  partida without subdivisions, coded `xxxx.00`), `0101.21.01` a fracción with its unit and the
  import and export cuotas;
- a row without a code and with one dash is a one-dash subpartida that the Tarifa leaves uncoded
  ("-Las demás máquinas…:"): its two-dash children share their first five digits, which become its
  navigation code (`84714`);
- "SUBCAPÍTULO I" + a title row group the partidas of chapters 28, 29 and others.

The 22 sections (I–XXII) are kept apart (`Tarifa.sections`: title, notes, chapters), since node
codes are digits only.

In the consolidated text the Cámara appends its own notes to a fracción's description cell
("Arancel modificado con vigencia temporal DOF 18-11-2022 (antes Imp. 15)", "Fracción adicionada DOF
21-07-2025"); they are split off as `annotations` and never become part of the description.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from tigie_nico_mx.html import Item, Para, Row, one_line
from tigie_nico_mx.rates import Rate, parse_rate

FRACCION = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
SUBHEADING = re.compile(r"^\d{4}\.\d{2}$")
HEADING = re.compile(r"^\d{2}\.\d{2}$")
_SECTION = re.compile(r"^Secci[oó]n ([IVXL]+)$")
_CHAPTER = re.compile(r"^Cap[ií]tulo (\d{2})\b\s*(.*)$")
_SUBCHAPTER = re.compile(r"^SUBCAP[IÍ]TULO\s+([IVXL]+)$")
_DASHES = frozenset({"", "-", "--", "---"})
# a paragraph of the Cámara's own notes inside a description cell
_ANNOTATION = re.compile(
    r"^(Arancel|Fracci[oó]n|Modificaci[oó]n|Descripci[oó]n|C[oó]digo|Nota|DOF\s|\(antes|\(se |"
    r"\(mantiene|antes Imp)"
)
_DOF_DATE = re.compile(r"DOF\s*\d{2}-\d{2}-\d{4}")


def digits(code: str) -> str:
    return re.sub(r"\D", "", code)


@dataclass
class Node:
    code: str  # digits only
    level: str  # chapter | heading | subheading | fraccion
    description: str
    parent: str | None
    sort: int
    unit: str | None = None
    imp: Rate | None = None
    exp: Rate | None = None
    annotations: list[str] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)
    uncoded: bool = False  # a one-dash group the Tarifa prints without a code

    @property
    def dotted(self) -> str:
        c = self.code
        if self.level == "fraccion":
            return f"{c[:4]}.{c[4:6]}.{c[6:]}"
        if self.level == "subheading":
            return f"{c[:4]}.{c[4:]}"
        if self.level == "heading":
            return f"{c[:2]}.{c[2:]}"
        return c


@dataclass
class Section:
    code: str  # I … XXII
    sort: int
    title: str
    notes: list[str] = field(default_factory=list)
    chapters: list[str] = field(default_factory=list)


@dataclass
class Tarifa:
    nodes: dict[str, Node]
    order: list[str]
    warnings: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    def by_level(self, level: str) -> list[Node]:
        return [self.nodes[c] for c in self.order if self.nodes[c].level == level]

    def fracciones(self) -> dict[str, Node]:
        return {n.code: n for n in self.by_level("fraccion")}


def split_description(cell: str) -> tuple[str, list[str]]:
    """The description cell → (description, the Cámara's annotations, one string per note)."""
    lines = [line for line in cell.split("\n") if line.strip()]
    first = next(
        (i for i, line in enumerate(lines) if i > 0 and _ANNOTATION.match(line.strip())),
        None,
    )
    if first is None:
        # an annotation can also start in the first paragraph's continuation lines
        first = next(
            (i for i, line in enumerate(lines) if i > 0 and _DOF_DATE.search(line)), len(lines)
        )
    description = " ".join(" ".join(lines[:first]).split())
    notes: list[str] = []
    for line in lines[first:]:
        text = " ".join(line.split())
        if notes and (text.startswith(("(", "DOF ", "[")) or not _ANNOTATION.match(text)):
            notes[-1] = f"{notes[-1]} {text}"
        else:
            notes.append(text)
    return description, notes


def _row_shape(cells: Sequence[str]) -> tuple[str, str, str, str, str, str] | None:
    """A Tarifa row as (code, dashes, description, unit, imp, exp), or None for other tables."""
    if len(cells) != 6:
        return None
    code, dash, desc, unit, imp, exp = (c.strip() for c in cells)
    if dash in _DASHES:
        return code, dash, desc, unit, imp, exp
    # a shifted row (the description in the dash column): code, desc, unit, imp, exp, extra
    if FRACCION.match(code):
        return code, "", dash, desc, unit, imp
    return None


def _bounds(items: Sequence[Item]) -> tuple[int, int]:
    start = next(
        (i for i, x in enumerate(items) if isinstance(x, Para) and x.text.strip() == "TARIFA"),
        None,
    )
    if start is None:
        raise ValueError("no TARIFA heading: not a LIGIE 2022 text")
    end = next(
        (
            i
            for i, x in enumerate(items)
            if i > start and isinstance(x, Para) and one_line(x.text).startswith("Artículo 2o")
        ),
        len(items),
    )
    return start, end


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.order: list[str] = []
        self.warnings: list[str] = []
        self.sort = 0
        self.sections: list[Section] = []
        self.chapter: Node | None = None
        self.chapter_notes: list[str] = []
        self.heading: Node | None = None
        self.subchapter: str | None = None
        self.pending_group: tuple[str, int] | None = None  # (text, sort) of an uncoded group
        self.group: Node | None = None
        self.expect: str | None = None  # "section-title" | "chapter-title" | "subchapter-title"

    def add(self, node: Node) -> Node:
        if node.code in self.nodes:
            self.warnings.append(f"duplicate code {node.dotted}; first kept")
            return self.nodes[node.code]
        self.nodes[node.code] = node
        self.order.append(node.code)
        return node

    def next_sort(self) -> int:
        self.sort += 1
        return self.sort

    def close_chapter_notes(self) -> None:
        if self.chapter is None:
            return
        notes: list[dict[str, str]] = []
        if self.chapter_notes:
            notes.append({"kind": "notas_capitulo", "text": "\n".join(self.chapter_notes)})
        self.chapter.notes = notes

    def para(self, text: str) -> None:
        line = one_line(text)
        section = _SECTION.match(line)
        chapter = _CHAPTER.match(line)
        if section:
            self.close_chapter_notes()
            self.chapter = None
            code = section.group(1)
            self.sections.append(Section(code, len(self.sections) + 1, ""))
            self.expect = "section-title"
            return
        if chapter:
            self.close_chapter_notes()
            code = chapter.group(1)
            self.chapter = self.add(Node(code, "chapter", "", None, self.next_sort()))
            if self.sections:
                self.sections[-1].chapters.append(code)
            else:
                self.warnings.append(f"chapter {code} before any section")
            self.chapter_notes = []
            if chapter.group(2).strip():
                self.chapter_notes.append(chapter.group(2).strip())
            self.heading = None
            self.subchapter = None
            self.group = None
            self.pending_group = None
            self.expect = "chapter-title"
            return
        if set(line) <= {"_", " "}:
            return
        if self.expect == "section-title" and self.sections:
            self.sections[-1].title = line
            self.expect = None
        elif self.expect == "chapter-title" and self.chapter is not None:
            self.chapter.description = line
            self.expect = None
        elif self.chapter is not None:
            self.chapter_notes.append(line)
        elif self.sections:
            self.sections[-1].notes.append(line)

    def row(self, cells: Sequence[str]) -> None:
        shape = _row_shape(cells)
        if shape is None:
            if self.chapter is not None and any(c.strip() for c in cells):
                # a small table inside the notes (cereal ash content, paper strength, …)
                self.chapter_notes.append(" | ".join(one_line(c) for c in cells))
            return
        code, dash, desc, unit, imp, exp = shape
        if self.chapter is None:
            if code:
                self.warnings.append(f"row {code} before any chapter")
            return
        if not code:
            self._uncoded(dash, desc)
            return
        if HEADING.match(code):
            self._heading(code, desc)
        elif SUBHEADING.match(code):
            self._subheading(code, dash, desc)
        elif FRACCION.match(code):
            self._fraccion(code, desc, unit, imp, exp)
        elif code.upper() not in ("CÓDIGO", "CODIGO"):
            self.warnings.append(f"unknown code shape {code!r}")

    def _uncoded(self, dash: str, desc: str) -> None:
        text = one_line(desc)
        if not text:
            return
        sub = _SUBCHAPTER.match(text)
        if sub:
            self.subchapter = f"Subcapítulo {sub.group(1)}"
            self.expect = "subchapter-title"
            return
        if self.expect == "subchapter-title" and dash == "":
            self.subchapter = f"{self.subchapter}. {text}"
            self.expect = None
            return
        if dash == "-":
            self.pending_group = (text, self.next_sort())
            self.group = None
            return
        self.warnings.append(f"uncoded row without a dash in chapter {self.chapter_code}: {text}")

    @property
    def chapter_code(self) -> str:
        return self.chapter.code if self.chapter else "?"

    def _heading(self, code: str, desc: str) -> None:
        d = digits(code)
        if self.chapter is None or not d.startswith(self.chapter.code):
            self.warnings.append(f"partida {code} outside chapter {self.chapter_code}")
        node = Node(d, "heading", split_description(desc)[0], self.chapter_code, self.next_sort())
        if self.subchapter:
            node.notes.append({"kind": "subcapitulo", "text": self.subchapter})
        self.heading = self.add(node)
        self.group = None
        self.pending_group = None

    def _subheading(self, code: str, dash: str, desc: str) -> None:
        d = digits(code)
        parent = self.heading.code if self.heading else None
        if parent is None or not d.startswith(parent):
            self.warnings.append(f"subpartida {code} outside partida {parent}")
        if dash == "--":
            if self.pending_group is not None:
                text, sort = self.pending_group
                group = Node(d[:5], "subheading", text, parent, sort, uncoded=True)
                group.notes.append(
                    {
                        "kind": "sin_codigo",
                        "text": "Subpartida de un guion que la Tarifa no codifica; el código de "
                        "cinco dígitos sirve para navegar.",
                    }
                )
                self.group = self.add(group)
                self.pending_group = None
            if self.group is not None and d.startswith(self.group.code):
                parent = self.group.code
            elif self.group is not None:
                self.warnings.append(f"two-dash subpartida {code} outside group {self.group.code}")
        else:
            self.group = None
            if self.pending_group is not None:
                self.warnings.append(f"uncoded group before {code} has no two-dash child")
                self.pending_group = None
        description = split_description(desc)[0]
        self.add(Node(d, "subheading", description, parent, self.next_sort()))

    def _fraccion(self, code: str, desc: str, unit: str, imp: str, exp: str) -> None:
        d = digits(code)
        parent = d[:6]
        if parent not in self.nodes:
            self.warnings.append(f"fracción {code} without subpartida {parent}")
        description, annotations = split_description(desc)
        node = Node(
            d,
            "fraccion",
            description,
            parent,
            self.next_sort(),
            unit=one_line(unit) or None,
            imp=parse_rate(imp),
            exp=parse_rate(exp),
            annotations=annotations,
        )
        self.add(node)


def parse_tarifa(items: Sequence[Item]) -> Tarifa:
    start, end = _bounds(items)
    builder = _Builder()
    for item in items[start + 1 : end]:
        if isinstance(item, Para):
            builder.para(item.text)
        elif isinstance(item, Row):
            builder.row(item.cells)
    builder.close_chapter_notes()
    for node in builder.nodes.values():
        if node.level == "chapter" and not node.description:
            builder.warnings.append(f"chapter {node.code} has no title")
    for sec in builder.sections:
        if not sec.title or not sec.chapters:
            builder.warnings.append(f"section {sec.code} has no title or no chapters")
    return Tarifa(builder.nodes, builder.order, builder.warnings, builder.sections)
