"""The NICOs (números de identificación comercial, LIGIE art. 2, regla complementaria 10a).

The SE acuerdo of DOF 22-08-2022 lists, in its Artículo Primero, one row per NICO
(`[fracción, NICO, descripción]`), chapter by chapter, with the chapters' "Anotaciones"; its
Artículo Segundo is the 2020 → 2022 correlation (not read here). It entered into force with the
LIGIE (12-12-2022). Each modifying acuerdo creates NICOs in its Artículo Primero and suppresses
others in its Artículo Segundo ("SUPRIMIDO"), from its own date of entry into force.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from tigie_nico_mx.html import Item, Para, Row, one_line
from tigie_nico_mx.tigie import FRACCION, digits

_NICO = re.compile(r"^\d{2}$")
_ARTICLE = re.compile(r"^Art[ií]culo (Primero|Segundo|Tercero|Cuarto)\b", re.IGNORECASE)
_CHAPTER = re.compile(r"^[“\"]?Cap[ií]tulo (\d{2})")


@dataclass
class Nico:
    fraccion: str  # 8 digits
    nico: str  # 2 digits
    description: str
    valid_from: date
    valid_to: date | None = None
    source: str = ""
    suppressed_by: str = ""

    @property
    def code(self) -> str:
        return self.fraccion + self.nico


@dataclass
class NicoSet:
    nicos: dict[str, Nico] = field(default_factory=dict)
    annotations: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _articles(items: Sequence[Item]) -> dict[str, list[Item]]:
    """The items under each "Artículo …" paragraph (first word: Primero, Segundo, …)."""
    out: dict[str, list[Item]] = {}
    current: str | None = None
    for item in items:
        if isinstance(item, Para):
            match = _ARTICLE.match(one_line(item.text))
            if match:
                current = match.group(1).capitalize()
                out.setdefault(current, [])
                continue
            if one_line(item.text).upper().startswith("TRANSITORIO"):
                current = None
        if current is not None:
            out[current].append(item)
    return out


def _rows(items: Sequence[Item]) -> list[tuple[str, str, str]]:
    out = []
    for item in items:
        if isinstance(item, Row) and len(item.cells) == 3:
            fraccion, nico, desc = (c.strip() for c in item.cells)
            if FRACCION.match(fraccion) and _NICO.match(nico):
                out.append((digits(fraccion), nico, one_line(desc)))
    return out


def _annotations(items: Sequence[Item], source: str) -> dict[str, list[dict[str, str]]]:
    """Chapter → its "Anotaciones de los Números de Identificación Comercial" paragraphs."""
    out: dict[str, list[dict[str, str]]] = {}
    chapter: str | None = None
    collecting = False
    lines: list[str] = []

    def close() -> None:
        if chapter and lines:
            out.setdefault(chapter, []).append(
                {"kind": "anotaciones_nico", "text": "\n".join(lines), "source": source}
            )

    for item in items:
        if isinstance(item, Row):
            if collecting:
                close()
                collecting, lines = False, []
            continue
        text = one_line(item.text)
        match = _CHAPTER.match(text)
        if match and len(text) < 40:
            if collecting:
                close()
            chapter, collecting, lines = match.group(1), False, []
            continue
        if text.startswith("Anotaciones de los Números de Identificación Comercial"):
            collecting, lines = True, []
            continue
        if collecting:
            if _ARTICLE.match(text) or text.upper().startswith("TRANSITORIO"):
                close()
                collecting, lines = False, []
            else:
                lines.append(text.strip('“”" '))
    if collecting:
        close()
    return out


def apply_acuerdo(
    target: NicoSet, items: Sequence[Item], *, effective: date, source: str, base: bool
) -> None:
    """Fold one acuerdo into `target`: the base list, or a modification's creations and
    suppressions (each from `effective`)."""
    articles = _articles(items)
    created = _rows(articles.get("Primero", []))
    if not created:
        target.warnings.append(f"{source}: no NICO rows in its Artículo Primero")
    for fraccion, nico, desc in created:
        code = fraccion + nico
        known = target.nicos.get(code)
        if known is not None and known.valid_to is None:
            if base:
                target.warnings.append(f"{source}: NICO {code} listed twice")
            else:
                known.description = desc
                known.source = source
            continue
        if known is not None:
            target.warnings.append(f"{source}: NICO {code} recreated after its suppression")
        target.nicos[code] = Nico(fraccion, nico, desc, effective, None, source)
    if not base:
        for fraccion, nico, _ in _rows(articles.get("Segundo", [])):
            code = fraccion + nico
            known = target.nicos.get(code)
            if known is None:
                target.warnings.append(f"{source}: suppresses unknown NICO {code}")
                continue
            known.valid_to = effective
            known.suppressed_by = source
    for chapter, notes in _annotations(items, source).items():
        # a modification restates the chapter's Anotaciones it creates or reforms (the 2023 one
        # reforms Anotación 1 of chapter 72, the only one that chapter had): its text replaces them
        if base:
            target.annotations.setdefault(chapter, []).extend(notes)
        else:
            target.annotations[chapter] = notes
