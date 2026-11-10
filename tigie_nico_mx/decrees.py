"""Every decree that changed an IGI or IGE of the TIGIE 2022, as dated rate events.

Two kinds of events come out of the decrees (`timeline.py` turns them into measure segments):

- a `Change` is permanent: it replaces the Tarifa's own cuota from its date (the 29-12-2025 reform,
  the sugar decree of 10-11-2025, the 23-04-2026 decree, ammonium sulphate on 08-05-2024, the
  fracciones the 21-07-2025 reform created or reformed);
- an `Overlay` is temporary: the cuota a decree "modifica temporalmente" for a period, after which
  the Tarifa's cuota rules again; abrogations, derogations, suppressions and the canasta básica
  list's eliminations end it early. Where overlays overlap, the later decree rules. A decree whose
  row carries an "acotación" ("Únicamente pan de caja") covers only some goods of the fracción: its
  overlay is an IGI with that `scope` (the `alcance` column), beside the fracción's own IGI
  (scope '').

A decree can also change a fracción's text: the 18-11-2022 decree (artículo Primero, in force with
the LIGIE) and the 21-07-2025 reform (in force 17-01-2026). `Events.descriptions` keeps each such
fracción's dated texts.

Dates come from each decree's transitorios (read by hand; the module asserts the text it relies on
still says so). "N años contados a partir de su entrada en vigor" is counted from date to date: the
last day is the anniversary of the first one (the 19-12-2024 decree states the same end, 23-04-2026,
for the 22-04-2024 one's companions).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from tigie_nico_mx.html import Item, Para, Row, one_line
from tigie_nico_mx.rates import Rate, parse_rate
from tigie_nico_mx.sources import LIGIE_IN_FORCE, SOURCES, Capture
from tigie_nico_mx.tigie import FRACCION, digits, parse_tarifa

COVID_END = date(2023, 5, 10)  # DOF 09-05-2023 codNota 5688265, in force the next day
COVID_END_SOURCE = "DOF 09-05-2023 codNota 5688265"
CANASTA_END = date(2027, 1, 1)  # "estará vigente hasta el 31 de diciembre de 2026" (DOF 31-12-2025)
_DASHES = frozenset({"", "-", "--", "---"})
_BOUNDARY = re.compile(
    r"^(Art[íi]culo\s+)?(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[ée]ptimo|Octavo|Noveno|"
    r"D[ée]cimo|[ÚU]nico)\b|^TRANSITORIOS?\b|^[IVX]+\. Se ",
    re.IGNORECASE,
)
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        (
            "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
            "diciembre"
        ).split()
    )
}


@dataclass(frozen=True)
class DecreeRow:
    code: str
    description: str
    unit: str
    imp: Rate | None
    exp: Rate | None
    scope: str  # the acotación, "" when the row covers the whole fracción


@dataclass
class Change:
    code: str
    kind: str  # igi | ige
    rate: Rate
    start: date
    source: str
    note: str


@dataclass
class Text:
    start: date
    end: date | None
    description: str
    authority: str


@dataclass
class Overlay:
    code: str
    kind: str  # igi | ige
    rate: Rate
    start: date
    end: date | None
    source: str
    note: str
    scope: str = ""
    ended_by: str = ""  # what ended it early, for the notes

    @property
    def rank(self) -> tuple[date, int]:
        s = SOURCES[self.source]
        return s.dof, s.cod_nota


@dataclass
class Events:
    base: dict[str, tuple[Rate | None, Rate | None]] = field(default_factory=dict)
    created: dict[str, tuple[date, str]] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    descriptions: dict[str, list[Text]] = field(default_factory=dict)
    original: dict[str, str] = field(default_factory=dict)  # the LIGIE's text as published
    applied: list[dict[str, object]] = field(default_factory=list)
    not_applied: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def decree_rows(items: Iterable[Item]) -> list[DecreeRow]:
    """The fracción rows of a decree's tables, whatever their column layout."""
    out: list[DecreeRow] = []
    for item in items:
        if not isinstance(item, Row) or not item.cells or not FRACCION.match(item.cells[0].strip()):
            continue
        cells = [c.strip() for c in item.cells]
        if len(cells) == 6 and cells[1] in _DASHES:
            code, _, desc, unit, imp, exp = cells
            scope = ""
        elif len(cells) == 6:
            code, desc, unit, imp, exp, scope = cells
        elif len(cells) == 5:
            code, desc, unit, imp, exp = cells
            scope = ""
        else:
            continue
        out.append(
            DecreeRow(
                digits(code),
                one_line(desc),
                one_line(unit),
                parse_rate(imp),
                parse_rate(exp),
                one_line(scope),
            )
        )
    return out


def section(items: Sequence[Item], start: str) -> list[Item]:
    """The items after the first paragraph matching `start`, up to the next article-like one."""
    pattern = re.compile(start, re.IGNORECASE)
    out: list[Item] = []
    inside = False
    for item in items:
        if isinstance(item, Para):
            text = one_line(item.text)
            if not inside and pattern.match(text):
                inside = True
                continue
            if inside and _BOUNDARY.match(text):
                break
        if inside:
            out.append(item)
    return out


def paragraph(items: Sequence[Item], start: str) -> str:
    pattern = re.compile(start, re.IGNORECASE)
    for item in items:
        if isinstance(item, Para) and pattern.match(one_line(item.text)):
            return one_line(item.text)
    raise ValueError(f"no paragraph matching {start!r}")


def require(items: Sequence[Item], start: str, phrase: str) -> str:
    """The paragraph starting with `start`, which must contain `phrase` (the date it relies on)."""
    text = paragraph(items, start)
    if phrase not in text:
        raise ValueError(f"the decree text changed: {start!r} no longer says {phrase!r}")
    return text


def spanish_dates(text: str) -> list[date]:
    return [
        date(int(y), _MONTHS[m.lower()], int(d))
        for d, m, y in re.findall(r"(\d{1,2}) de ([a-zA-Z]+) de?l? ?(\d{4})", text)
        if m.lower() in _MONTHS
    ]


def codes_in(text: str) -> list[str]:
    return [digits(c) for c in re.findall(r"\b\d{4}\.\d{2}\.\d{2}\b", text)]


class _Collector:
    def __init__(self, capture: Capture) -> None:
        self.capture = capture
        self.events = Events()

    def items(self, key: str) -> list[Item]:
        return self.capture.items(key)

    def applied(self, key: str, what: str, count: int, **extra: object) -> None:
        source = SOURCES[key]
        self.events.applied.append(
            {
                "decree": source.authority,
                "key": key,
                "what": what,
                "fracciones": count,
                **extra,
            }
        )

    def skipped(self, key: str, what: str, why: str) -> None:
        self.events.not_applied.append(
            {"decree": SOURCES[key].authority, "key": key, "what": what, "why": why}
        )

    def overlay(
        self,
        rows: Sequence[DecreeRow],
        key: str,
        start: date,
        end: date | None,
        note: str,
        *,
        kinds: Sequence[str] = ("igi",),
    ) -> list[Overlay]:
        made: list[Overlay] = []
        for row in rows:
            for kind in kinds:
                rate = row.imp if kind == "igi" else row.exp
                if rate is None:
                    self.events.warnings.append(f"{key}: {row.code} has no {kind} rate")
                    continue
                # an acotación limits the import side only (the maize export decree of
                # 16-01-2023 repeats the import acotación beside a full export cuota)
                scope = row.scope if kind == "igi" else ""
                made.append(Overlay(row.code, kind, rate, start, end, key, note, scope=scope))
        self.events.overlays.extend(made)
        return made

    def change(self, rows: Sequence[DecreeRow], key: str, start: date, note: str) -> None:
        for row in rows:
            for kind, rate in (("igi", row.imp), ("ige", row.exp)):
                if rate is not None:
                    self.events.changes.append(Change(row.code, kind, rate, start, key, note))

    def end(
        self,
        source: str,
        at: date,
        by: str,
        codes: Iterable[str] | None = None,
        kinds: Iterable[str] = ("igi", "ige"),
    ) -> int:
        """End `source`'s overlays (all, or those of `codes`) at `at` when they run past it."""
        wanted = set(codes) if codes is not None else None
        count = 0
        for o in self.events.overlays:
            if o.source != source or o.kind not in kinds:
                continue
            if wanted is not None and o.code not in wanted:
                continue
            if o.start >= at:
                o.end = o.start  # never took effect; dropped below
                o.ended_by = by
                count += 1
            elif o.end is None or o.end > at:
                o.end = at
                o.ended_by = by
                count += 1
        return count


def _base(c: _Collector) -> None:
    tarifa = parse_tarifa(c.items("orig"))
    c.events.warnings.extend(f"orig: {w}" for w in tarifa.warnings)
    for code, node in tarifa.fracciones().items():
        c.events.base[code] = (node.imp, node.exp)
        c.events.original[code] = node.description
    c.applied(
        "orig",
        "Tarifa del artículo 1o. como se publicó, en vigor el 12-12-2022 (IGI e IGE base)",
        len(c.events.base),
    )


def _tarifa01(c: _Collector) -> None:
    items = c.items("tarifa01")
    require(items, r"^PRIMERO", "hasta el 17 de mayo de 2023")
    rows = decree_rows(section(items, r"^Art[íi]culo [ÚU]nico"))
    made = c.overlay(
        rows,
        "tarifa01",
        LIGIE_IN_FORCE,
        date(2023, 5, 18),
        "Arancel temporal a la importación (DOF 18-11-2022), en vigor con la LIGIE.",
    )
    c.applied("tarifa01", "aranceles temporales a la importación", len(rows), overlays=len(made))


def _tarifa02(c: _Collector) -> None:
    items = c.items("tarifa02")
    s2 = decree_rows(section(items, r"^Segundo\. Se modifican los aranceles"))
    s3 = decree_rows(section(items, r"^Tercero\. Se modifican los aranceles"))
    s4 = decree_rows(section(items, r"^Cuarto\. Se modifican los aranceles"))
    s5 = decree_rows(section(items, r"^Quinto\. Se modifican los aranceles"))
    # Primero: new texts for nine fracciones of chapters 97 and 98, in force with the LIGIE itself
    texts = decree_rows(section(items, r"^Primero\. Se modifica la descripci"))
    for row in texts:
        c.events.descriptions[row.code] = [
            Text(LIGIE_IN_FORCE, None, row.description, SOURCES["tarifa02"].authority)
        ]
    c.applied("tarifa02", "artículo Primero: descripciones (en vigor el 12-12-2022)", len(texts))
    # Segundo: 15% from the LIGIE's entry into force, then the schedule of transitorio SEGUNDO
    sched = section(items, r"^SEGUNDO\. El arancel aplicable")
    steps: dict[str, list[tuple[date, Rate]]] = {}
    current: list[tuple[date, Rate]] = []
    for item in sched:
        if isinstance(item, Para):
            text = one_line(item.text)
            current = []
            for m in re.finditer(
                r"(?:de (\d+)%|(exento)) a partir del (\d{1,2} de [a-z]+ (?:de|del) \d{4})", text
            ):
                when = spanish_dates(m.group(3).replace("del ", "de "))[0]
                rate = parse_rate(m.group(1) or "Ex.")
                if rate is None:
                    raise ValueError(f"tarifa02: no rate in {m.group(0)!r}")
                current.append((when, rate))
            for code in codes_in(text):
                steps[code] = current
        elif isinstance(item, Row) and item.cells and FRACCION.match(item.cells[0].strip()):
            steps[digits(item.cells[0])] = current
    derogated = date(2023, 8, 16)  # DOF 15-08-2023 transitorio Segundo
    by = "derogado por DOF 15-08-2023"
    for row in s2:
        if row.imp is None:
            continue
        points = [(LIGIE_IN_FORCE, row.imp), *steps.get(row.code, [])]
        for i, (start, rate) in enumerate(points):
            end = points[i + 1][0] if i + 1 < len(points) else None
            c.events.overlays.append(
                Overlay(
                    row.code,
                    "igi",
                    rate,
                    start,
                    end,
                    "tarifa02",
                    "Arancel del artículo Segundo del Decreto DOF 18-11-2022 (acero), con la "
                    "desgravación de su transitorio Segundo.",
                )
            )
    c.end("tarifa02", derogated, by, codes=[r.code for r in s2])
    c.applied(
        "tarifa02",
        "artículo Segundo (acero, 15% y luego su calendario; derogado desde el 16-08-2023)",
        len(s2),
        scheduled=len([r for r in s2 if r.code in steps]),
    )
    c.skipped(
        "tarifa02",
        f"artículo Tercero ({len(s3)} fracciones textiles desde el 01-10-2024)",
        "derogado por DOF 15-08-2023 antes de entrar en vigor",
    )
    require(items, r"^CUARTO\. El arancel", "hasta el 30 de septiembre de 2024")
    made = c.overlay(
        s4,
        "tarifa02",
        LIGIE_IN_FORCE,
        date(2024, 10, 1),
        "Arancel temporal del artículo Cuarto del Decreto DOF 18-11-2022, hasta el 30-09-2024.",
    )
    c.applied("tarifa02", "artículo Cuarto (hasta el 30-09-2024)", len(s4), overlays=len(made))
    require(items, r"^QUINTO\. El arancel", "SARS-CoV-2")
    made = c.overlay(
        s5,
        "tarifa02",
        LIGIE_IN_FORCE,
        COVID_END,
        "Arancel temporal del artículo Quinto del Decreto DOF 18-11-2022 (COVID-19), hasta la "
        "entrada en vigor del decreto que declaró terminada la acción extraordinaria "
        f"({COVID_END_SOURCE}).",
    )
    c.applied(
        "tarifa02",
        f"artículo Quinto (mercancías COVID-19, hasta el 10-05-2023 según {COVID_END_SOURCE})",
        len(s5),
        overlays=len(made),
    )
    c.skipped(
        "tarifa02",
        "artículos Sexto a Décimo Quinto (automotriz, IMMEX, región fronteriza, Chetumal, PROSEC, "
        "vehículos usados, aranceles-cupo)",
        "modifican otros decretos (programas sectoriales y cupos), no las cuotas de la Tarifa",
    )


def _canasta(c: _Collector) -> None:
    """The canasta básica list (DOF 06-01-2023 and the decrees that add to it or take from it)."""
    t03 = c.items("tarifa03")
    require(t03, r"^Primero\. El presente decreto", "31 de diciembre de 2023")
    require(c.items("tarifa08"), r"^[“\"]?Primero\. El presente decreto", "31 de diciembre de 2024")
    require(c.items("tarifa12"), r"^[“\"]?Primero\. El presente decreto", "31 de diciembre de 2025")
    require(c.items("tarifa14"), r"^[“\"]?Primero\. El presente decreto", "31 de diciembre de 2026")
    require(c.items("tarifa14"), r"^Primero\. El presente decreto entra", "1 de enero de 2026")
    extended = (
        "vigente hasta el 31-12-2026 (DOF 31-12-2025 codNota 5777651; ampliaciones anteriores: "
        "DOF 27-12-2023 y 31-12-2024)"
    )
    note = (
        "Exención temporal de arancel a la importación definitiva (canasta básica y de consumo "
        "básico de las familias)."
    )
    base_rows = decree_rows(section(t03, r"^Art[íi]culo Primero"))
    made = c.overlay(base_rows, "tarifa03", date(2023, 1, 7), CANASTA_END, note)
    c.applied("tarifa03", "canasta básica, artículo Primero (desde el 07-01-2023)", len(base_rows))
    c.skipped(
        "tarifa03",
        "artículo Segundo (facilidades administrativas para 30 fracciones)",
        "no cambia la cuota: solo facilita el cumplimiento no arancelario",
    )
    # tarifa01 ended when tarifa03 entered into force (its transitorio Segundo abrogates it)
    c.end("tarifa01", date(2023, 1, 7), "abrogado por DOF 06-01-2023")
    t05 = c.items("tarifa05")
    adds = decree_rows(section(t05, r"^I\. Se adiciona"))
    drops = [r.code for r in decree_rows(section(t05, r"^II\. Se eliminan"))]
    made += c.overlay(adds, "tarifa05", date(2023, 5, 18), CANASTA_END, note)
    c.end("tarifa03", date(2023, 5, 18), "eliminada de la lista por DOF 18-05-2023", codes=drops)
    c.applied(
        "tarifa05", "canasta básica: adiciones y eliminaciones (18-05-2023)", len(adds) + len(drops)
    )
    c.end(
        "tarifa03",
        date(2023, 6, 24),
        "eliminada de la lista por DOF 23-06-2023",
        codes=["10059004"],
    )
    t12 = c.items("tarifa12")
    adds = decree_rows(section(t12, r"^I\. Se adicionan"))
    drops = [r.code for r in decree_rows(section(t12, r"^II\. Se eliminan"))]
    made += c.overlay(adds, "tarifa12", date(2025, 1, 1), CANASTA_END, note)
    for key in ("tarifa03", "tarifa05"):
        c.end(key, date(2025, 1, 1), "eliminada de la lista por DOF 31-12-2024", codes=drops)
    c.applied(
        "tarifa12", "canasta básica: adiciones y eliminaciones (01-01-2025)", len(adds) + len(drops)
    )
    drops = [r.code for r in decree_rows(section(c.items("tarifa14"), r"^Art[íi]culo Primero"))]
    for key in ("tarifa03", "tarifa05", "tarifa12"):
        c.end(key, date(2026, 1, 1), "eliminada de la lista por DOF 31-12-2025", codes=drops)
    c.applied(
        "tarifa14",
        "canasta básica: eliminaciones (01-01-2026), vigencia hasta el 31-12-2026",
        len(drops),
    )
    c.applied("tarifa08", "canasta básica: vigencia ampliada al 31-12-2024", 0)
    for o in made:
        if o.end == CANASTA_END and not o.ended_by:
            o.note = f"{o.note} {extended[0].upper()}{extended[1:]}."
    c.skipped(
        "tarifa12",
        "artículo Segundo (7210.70.02 y 7212.40.04 salen de la lista de facilidades)",
        "no cambia la cuota",
    )


def _maize(c: _Collector) -> None:
    t04 = c.items("tarifa04")
    require(t04, r"^[ÚU]NICO\. El presente", "30 de junio de 2023")
    rows = decree_rows(section(t04, r"^Art[íi]culo [ÚU]nico"))
    made = c.overlay(
        rows,
        "tarifa04",
        date(2023, 1, 17),
        date(2023, 7, 1),
        "Arancel temporal a la exportación de maíz blanco (DOF 16-01-2023).",
        kinds=("ige",),
    )
    c.applied(
        "tarifa04",
        "arancel temporal a la exportación de maíz blanco",
        len(rows),
        overlays=len(made),
    )
    t06 = c.items("tarifa06")
    require(t06, r"^Primero\. El presente decreto", "31 de diciembre de 2023")
    c.end("tarifa04", date(2023, 6, 24), "abrogado por DOF 23-06-2023")
    rows = decree_rows(section(t06, r"^Art[íi]culo Segundo"))
    made = c.overlay(
        rows,
        "tarifa06",
        date(2023, 6, 24),
        date(2024, 1, 1),
        "Aranceles temporales del maíz blanco (DOF 23-06-2023), hasta el 31-12-2023.",
        kinds=("igi", "ige"),
    )
    c.applied(
        "tarifa06",
        "aranceles temporales a la importación y exportación de maíz blanco",
        len(rows),
        overlays=len(made),
    )


def _steel_and_more(c: _Collector) -> None:
    t07 = c.items("tarifa07")
    require(t07, r"^Primero\. El presente decreto", "31 de julio de 2025")
    require(t07, r"^Primero\. El presente decreto", "16 de agosto de 2023")
    special = require(t07, r"^Tratándose de la importación", "hasta el 31 de diciembre de 2023")
    rows = decree_rows(section(t07, r"^Art[íi]culo [ÚU]nico"))
    early = set(codes_in(special))
    note = "Arancel temporal (DOF 15-08-2023), del 16-08-2023 al 31-07-2025."
    plain = [r for r in rows if r.code not in early]
    made = c.overlay(plain, "tarifa07", date(2023, 8, 16), date(2025, 8, 1), note)
    ten = parse_rate("10")
    if ten is None or "arancel del 10%" not in special:
        raise ValueError("tarifa07: the 10% transitional cuota is no longer in its transitorio")
    for r in rows:
        if r.code in early and r.imp is not None:
            first_note = "Arancel temporal (DOF 15-08-2023): 10% hasta el 31-12-2023."
            made.append(
                Overlay(
                    r.code, "igi", ten, date(2023, 8, 16), date(2024, 1, 1), "tarifa07", first_note
                )
            )
            made.append(
                Overlay(r.code, "igi", r.imp, date(2024, 1, 1), date(2025, 8, 1), "tarifa07", note)
            )
            c.events.overlays.extend(made[-2:])
    c.applied(
        "tarifa07", "aranceles temporales a la importación (16-08-2023 al 31-07-2025)", len(rows)
    )
    t09 = c.items("tarifa09")
    require(t09, r"^Primero\. El presente decreto", "dos años")
    require(t09, r"^Segundo\. Se abroga", "15 de agosto de 2023")
    c.end("tarifa07", date(2024, 4, 23), "abrogado por DOF 22-04-2024")
    rows = decree_rows(section(t09, r"^Art[íi]culo [ÚU]nico"))
    made = c.overlay(
        rows,
        "tarifa09",
        date(2024, 4, 23),
        date(2026, 4, 24),
        "Arancel temporal (DOF 22-04-2024), dos años desde el 23-04-2024.",
    )
    c.applied(
        "tarifa09", "aranceles temporales a la importación (23-04-2024 al 23-04-2026)", len(rows)
    )
    t10 = c.items("tarifa10")
    gone = codes_in(paragraph(t10, r"^Art[íi]culo Primero"))
    c.end("tarifa09", date(2024, 5, 9), "suprimida por DOF 08-05-2024", codes=gone)
    rows = decree_rows(section(t10, r"^Art[íi]culo Segundo"))
    c.change(rows, "tarifa10", date(2024, 5, 9), "Arancel modificado por DOF 08-05-2024.")
    c.applied(
        "tarifa10", "artículo Primero: 2 fracciones salen de la lista del 22-04-2024", len(gone)
    )
    c.applied("tarifa10", "artículo Segundo: cuota permanente (09-05-2024)", len(rows))
    t11 = c.items("tarifa11")
    rows = decree_rows(section(t11, r"^Primero\. Se modifican temporalmente"))
    require(t11, r"^Primero\. Se modifican temporalmente", "hasta el 23 de abril de 2026")
    c.overlay(
        rows,
        "tarifa11",
        date(2024, 12, 20),
        date(2026, 4, 24),
        "Arancel temporal (DOF 19-12-2024), hasta el 23-04-2026.",
    )
    c.applied(
        "tarifa11", "aranceles temporales a la importación (20-12-2024 al 23-04-2026)", len(rows)
    )
    c.skipped(
        "tarifa11",
        "artículos Segundo y Tercero (anexos IMMEX)",
        "modifican el Decreto IMMEX, no la Tarifa",
    )


def _permanent(c: _Collector) -> None:
    t13 = c.items("tarifa13")
    rows = decree_rows(section(t13, r"^[ÚU]nico\. Se modifican"))
    c.change(rows, "tarifa13", date(2025, 11, 11), "Arancel modificado por DOF 10-11-2025.")
    c.applied("tarifa13", "cuotas permanentes (11-11-2025)", len(rows))
    ref01 = c.items("ref01")
    require(ref01, r"^[ÚU]nico\. El presente Decreto", "180 días")
    in_force = date(2026, 1, 17)  # 180 days after 21-07-2025
    head = paragraph(ref01, r"^Art[íi]culo [ÚU]nico")
    added = set(codes_in(head.split("se adicionan", 1)[1])) if "se adicionan" in head else set()
    rows = decree_rows(ref01)
    new = [r for r in rows if r.code in added]
    reformed = [r for r in rows if r.code not in added]
    for r in new:
        c.events.created[r.code] = (in_force, "ref01")
        c.events.base[r.code] = (r.imp, r.exp)
    for r in reformed:
        before = c.events.original.get(r.code)
        if before is not None and before != r.description:
            c.events.descriptions[r.code] = [
                Text(LIGIE_IN_FORCE, in_force, before, SOURCES["orig"].authority),
                Text(in_force, None, r.description, SOURCES["ref01"].authority),
            ]
    c.change(
        reformed,
        "ref01",
        in_force,
        "Fracción reformada por DOF 21-07-2025 (en vigor el 17-01-2026).",
    )
    c.applied("ref01", "capítulo 03: fracciones creadas (17-01-2026)", len(new))
    c.applied("ref01", "capítulo 03: fracciones reformadas (17-01-2026)", len(reformed))
    ref02 = c.items("ref02")
    require(ref02, r"^Primero\. El presente Decreto", "primero de enero de 2026")
    rows = decree_rows(ref02)
    c.change(
        rows,
        "ref02",
        date(2026, 1, 1),
        "Cuota reformada por el Congreso (DOF 29-12-2025), en vigor el 01-01-2026; deja sin "
        "efectos las disposiciones que se le opongan (transitorio Tercero).",
    )
    c.applied("ref02", "cuotas permanentes (01-01-2026)", len(rows))
    t15 = c.items("tarifa15")
    require(t15, r"^[ÚU]nico\. El presente decreto", "día siguiente")
    rows = decree_rows(section(t15, r"^Primero\. Se modifican los aranceles"))
    c.change(rows, "tarifa15", date(2026, 4, 24), "Arancel modificado por DOF 23-04-2026.")
    c.applied("tarifa15", "cuotas permanentes (24-04-2026)", len(rows))
    c.skipped(
        "tarifa15",
        "artículo Segundo (aranceles de los PROSEC)",
        "modifica el Decreto PROSEC, no la Tarifa",
    )
    t16 = c.items("tarifa16")
    require(t16, r"^[ÚU]NICO\. El presente decreto", "cinco años")
    rows = decree_rows(section(t16, r"^Art[íi]culo [ÚU]nico"))
    c.overlay(
        rows,
        "tarifa16",
        date(2026, 10, 14),
        date(2031, 10, 15),
        "Arancel temporal a la importación (DOF 13-10-2026), cinco años desde el 14-10-2026.",
    )
    c.applied("tarifa16", "arancel temporal a la importación (14-10-2026 al 14-10-2031)", len(rows))
    for key, why in (
        ("tarifa02_mod01", "un arancel-cupo para café en cápsulas, no el IGI general"),
        (
            "tarifa02_mod02",
            "un arancel-cupo del Decreto del 18-11-2022, no el IGI general",
        ),
    ):
        c.skipped(key, "arancel-cupo", why)


def _later_changes_win(c: _Collector) -> None:
    """A permanent change ends the earlier decrees' temporary cuotas on its fracción (lex
    posterior; the 29-12-2025 reform also says so in its transitorio Tercero). Partial overlays
    (an acotación) are left alone: a new general cuota does not repeal a narrower exemption."""
    cut: dict[str, list[str]] = {}
    by_key: dict[tuple[str, str], list[Overlay]] = {}
    for o in c.events.overlays:
        by_key.setdefault((o.code, o.kind), []).append(o)
    for ch in c.events.changes:
        for o in by_key.get((ch.code, ch.kind), []):
            if o.scope or o.rank >= SOURCES[ch.source].dof_rank:
                continue
            if o.start < ch.start and (o.end is None or o.end > ch.start):
                o.end = ch.start
                o.ended_by = f"sin efectos por {SOURCES[ch.source].authority}"
                cut.setdefault(ch.source, []).append(f"{o.code}:{o.kind}:{o.source}")
    for source, rows in cut.items():
        c.events.applied.append(
            {
                "decree": SOURCES[source].authority,
                "key": source,
                "what": "los aranceles temporales anteriores de sus fracciones terminan al entrar "
                "en vigor",
                "fracciones": len({r.split(":")[0] for r in rows}),
                "ended": sorted(set(rows)),
            }
        )


def collect(capture: Capture) -> Events:
    c = _Collector(capture)
    _base(c)
    _tarifa01(c)
    _tarifa02(c)
    _canasta(c)
    _maize(c)
    _steel_and_more(c)
    _permanent(c)
    _later_changes_win(c)
    c.events.overlays = [o for o in c.events.overlays if o.end is None or o.end > o.start]
    known = set(c.events.base)
    for o in c.events.overlays:
        if o.code not in known:
            c.events.warnings.append(f"{o.source}: {o.code} is not a fracción of the Tarifa")
    for ch in c.events.changes:
        if ch.code not in known:
            c.events.warnings.append(f"{ch.source}: {ch.code} is not a fracción of the Tarifa")
    return c.events
