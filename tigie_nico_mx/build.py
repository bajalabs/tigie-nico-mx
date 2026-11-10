"""A capture → the edition: every table as rows, plus the build summary.

The edition holds:

- the tree of the consolidated Tarifa: sections I–XXII, chapters, partidas, subpartidas (the
  Harmonized System 2022 six-digit level, with the TIGIE's own Spanish text, never WCO text), the
  uncoded one-dash groups, and the fracciones with their unit (UMT) and the cuotas the Cámara's
  consolidated text shows;
- the NICOs: the acuerdo of DOF 22-08-2022 and its two modifications, with the date each NICO was
  created or suppressed;
- the measures: IGI and IGE per fracción from the LIGIE as published (in force 12-12-2022), then
  every decree that changed them, each segment dated by the decree that set it; a partial measure
  (an "acotación" that limits a decree to some goods) is an IGI with that `alcance`;
- the notes (sections, chapters, NICO anotaciones, the Cámara's annotations), the dated texts of
  the fracciones a decree rewrote, the sources with their sha256, the decrees applied and not
  applied, and the cross-check of the computed cuotas against the consolidated Tarifa.

Dates in the tables are ISO (`YYYY-MM-DD`). A measure's `hasta` is its last day in force; a NICO's
`baja` is the first day it no longer exists.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from tigie_nico_mx import __version__
from tigie_nico_mx.decrees import Events, collect
from tigie_nico_mx.nico import NicoSet, apply_acuerdo
from tigie_nico_mx.rates import Rate
from tigie_nico_mx.sources import (
    CONSOLIDATED_ON,
    INDEX_URL,
    LIGIE_IN_FORCE,
    SOURCES,
    Capture,
    Source,
)
from tigie_nico_mx.tigie import Node, Tarifa, parse_tarifa
from tigie_nico_mx.timeline import Key, Segment, build_segments, rate_on

# The two NICO modifications take effect on these days (their transitorios).
NICO_MOD1_IN_FORCE = date(2023, 7, 1)
NICO_MOD2_IN_FORCE = date(2024, 3, 22)
HS_LAST_CHAPTER = 97  # chapter 98 is national (Mexican special operations), not HS
_NOT_A_UNIT = frozenset({"prohibida", ""})

Row = dict[str, Any]

# Every table's columns, in order. The first columns of fracciones, subpartidas, nicos and medidas
# are a contract with downstream users: never rename or remove one; add new ones at the end.
COLUMNS: dict[str, list[str]] = {
    "secciones": ["seccion", "numero", "titulo", "capitulos"],
    "capitulos": ["capitulo", "seccion", "descripcion", "sistema_armonizado", "orden"],
    "partidas": ["partida", "capitulo", "descripcion", "subcapitulo", "orden"],
    "grupos": ["grupo", "partida", "descripcion", "orden"],
    "subpartidas": [
        "subpartida",
        "partida",
        "capitulo",
        "descripcion",
        "grupo",
        "sistema_armonizado",
        "orden",
    ],
    "fracciones": [
        "fraccion",
        "subpartida",
        "descripcion",
        "umt",
        "igi_vigente",
        "ige_vigente",
        "partida",
        "capitulo",
        "igi_calculado",
        "ige_calculado",
        "alta",
        "nicos_vigentes",
        "orden",
    ],
    "nicos": [
        "fraccion",
        "nico",
        "codigo",
        "descripcion",
        "alta",
        "baja",
        "fuente_alta",
        "fuente_baja",
    ],
    "medidas": [
        "fraccion",
        "tipo",
        "valor",
        "desde",
        "hasta",
        "decreto",
        "alcance",
        "valor_numerico",
        "decreto_fecha",
        "decreto_codnota",
        "decreto_url",
        "nota",
    ],
    "notas": ["nivel", "codigo", "tipo", "texto", "fuente"],
    "historial_descripciones": ["fraccion", "desde", "hasta", "descripcion", "decreto"],
    "fuentes": [
        "clave",
        "archivo",
        "url",
        "dof",
        "codnota",
        "titulo",
        "sha256",
        "papel",
    ],
    "aplicacion": ["clave", "decreto", "aplicado", "que", "fracciones", "motivo"],
    "cotejo": [
        "fraccion",
        "tipo",
        "publicado",
        "calculado",
        "medida_parcial",
        "ultima_nota_camara",
    ],
}


def _iso(day: date | None) -> str:
    return f"{day:%Y-%m-%d}" if day else ""


def _last_day(end: date | None) -> str:
    """An exclusive end as the last day in force."""
    return _iso(end - timedelta(days=1)) if end else ""


def _cell(rate: Rate | None) -> str:
    return rate.cell if rate else ""


def _numeric(rate: Rate | None) -> int | float | None:
    return rate.json_numeric() if rate else None


def _unit(node: Node) -> str:
    if node.unit is None or node.unit.strip().lower() in _NOT_A_UNIT:
        return ""
    return node.unit


def _hs(code: str) -> int:
    return 1 if int(code[:2]) <= HS_LAST_CHAPTER else 0


def _by_authority() -> dict[str, Source]:
    """DOF authority → source; the consolidated text shares its authority with the reform of
    29-12-2025 and is never the authority of a measure."""
    return {s.authority: s for s in SOURCES.values() if s.key != "ligie"}


@dataclass
class Edition:
    tarifa: Tarifa
    nicos: NicoSet
    events: Events
    segments: dict[Key, list[Segment]]
    sources: list[dict[str, object]]
    as_of: date
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    _tables: dict[str, list[Row]] | None = None

    # -- tables ---------------------------------------------------------------------------------

    def tables(self) -> dict[str, list[Row]]:
        if self._tables is None:
            self._tables = {
                "secciones": self._secciones(),
                "capitulos": self._capitulos(),
                "partidas": self._partidas(),
                "grupos": self._grupos(),
                "subpartidas": self._subpartidas(),
                "fracciones": self._fracciones(),
                "nicos": self._nicos(),
                "medidas": self._medidas(),
                "notas": self._notas(),
                "historial_descripciones": self._historial(),
                "fuentes": self._fuentes(),
                "aplicacion": self._aplicacion(),
                "cotejo": self._cotejo(),
            }
        return self._tables

    def _section_of(self) -> dict[str, str]:
        return {c: s.code for s in self.tarifa.sections for c in s.chapters}

    def _secciones(self) -> list[Row]:
        return [
            {
                "seccion": s.code,
                "numero": s.sort,
                "titulo": s.title,
                "capitulos": " ".join(s.chapters),
            }
            for s in self.tarifa.sections
        ]

    def _capitulos(self) -> list[Row]:
        section = self._section_of()
        return [
            {
                "capitulo": n.code,
                "seccion": section.get(n.code, ""),
                "descripcion": n.description,
                "sistema_armonizado": _hs(n.code),
                "orden": n.sort,
            }
            for n in self.tarifa.by_level("chapter")
        ]

    def _partidas(self) -> list[Row]:
        out: list[Row] = []
        for n in self.tarifa.by_level("heading"):
            sub = next((x["text"] for x in n.notes if x["kind"] == "subcapitulo"), "")
            out.append(
                {
                    "partida": n.code,
                    "capitulo": n.code[:2],
                    "descripcion": n.description,
                    "subcapitulo": sub,
                    "orden": n.sort,
                }
            )
        return out

    def _grupos(self) -> list[Row]:
        return [
            {"grupo": n.code, "partida": n.code[:4], "descripcion": n.description, "orden": n.sort}
            for n in self.tarifa.by_level("subheading")
            if n.uncoded
        ]

    def _subpartidas(self) -> list[Row]:
        out: list[Row] = []
        for n in self.tarifa.by_level("subheading"):
            if n.uncoded:
                continue
            out.append(
                {
                    "subpartida": n.code,
                    "partida": n.code[:4],
                    "capitulo": n.code[:2],
                    "descripcion": n.description,
                    "grupo": n.parent if n.parent and len(n.parent) == 5 else "",
                    "sistema_armonizado": _hs(n.code),
                    "orden": n.sort,
                }
            )
        return out

    def _fracciones(self) -> list[Row]:
        in_force = Counter(
            n.fraccion
            for n in self.nicos.nicos.values()
            if n.valid_from <= self.as_of and (n.valid_to is None or n.valid_to > self.as_of)
        )
        out: list[Row] = []
        for n in self.tarifa.by_level("fraccion"):
            created = self.events.created.get(n.code)
            igi = rate_on(self.segments.get((n.code, "igi", ""), []), self.as_of)
            ige = rate_on(self.segments.get((n.code, "ige", ""), []), self.as_of)
            out.append(
                {
                    "fraccion": n.code,
                    "subpartida": n.code[:6],
                    "descripcion": n.description,
                    "umt": _unit(n),
                    "igi_vigente": _cell(n.imp),
                    "ige_vigente": _cell(n.exp),
                    "partida": n.code[:4],
                    "capitulo": n.code[:2],
                    "igi_calculado": _cell(igi),
                    "ige_calculado": _cell(ige),
                    "alta": _iso(created[0] if created else LIGIE_IN_FORCE),
                    "nicos_vigentes": in_force.get(n.code, 0),
                    "orden": n.sort,
                }
            )
        return out

    def _nicos(self) -> list[Row]:
        fracciones = self.tarifa.fracciones()

        def order(code: str) -> tuple[int, str]:
            n = self.nicos.nicos[code]
            parent = fracciones.get(n.fraccion)
            return (parent.sort if parent else 1 << 30, code)

        out: list[Row] = []
        for code in sorted(self.nicos.nicos, key=order):
            n = self.nicos.nicos[code]
            out.append(
                {
                    "fraccion": n.fraccion,
                    "nico": n.nico,
                    "codigo": n.code,
                    "descripcion": n.description,
                    "alta": _iso(n.valid_from),
                    "baja": _iso(n.valid_to),
                    "fuente_alta": SOURCES[n.source].label,
                    "fuente_baja": SOURCES[n.suppressed_by].label if n.suppressed_by else "",
                }
            )
        return out

    def _medidas(self) -> list[Row]:
        order = {code: i for i, code in enumerate(self.tarifa.order)}
        kinds = {"igi": 0, "ige": 1}

        def key(k: Key) -> tuple[int, str, int, str]:
            code, kind, scope = k
            return (order.get(code, 1 << 30), code, kinds[kind], scope)

        out: list[Row] = []
        for k in sorted(self.segments, key=key):
            code, kind, scope = k
            for seg in self.segments[k]:
                src = SOURCES[seg.source]
                out.append(
                    {
                        "fraccion": code,
                        "tipo": kind.upper(),
                        "valor": seg.rate.cell,
                        "desde": _iso(seg.start),
                        "hasta": _last_day(seg.end),
                        "decreto": src.label,
                        "alcance": scope,
                        "valor_numerico": seg.rate.json_numeric(),
                        "decreto_fecha": _iso(src.dof),
                        "decreto_codnota": src.cod_nota,
                        "decreto_url": src.url,
                        "nota": seg.note,
                    }
                )
        return out

    def _notas(self) -> list[Row]:
        out: list[Row] = []
        consolidated = SOURCES["ligie"].label
        for s in self.tarifa.sections:
            if s.notes:
                out.append(
                    {
                        "nivel": "seccion",
                        "codigo": s.code,
                        "tipo": "notas_seccion",
                        "texto": "\n".join(s.notes),
                        "fuente": consolidated,
                    }
                )
        levels = {
            "chapter": "capitulo",
            "heading": "partida",
            "subheading": "subpartida",
            "fraccion": "fraccion",
        }
        for code in self.tarifa.order:
            node = self.tarifa.nodes[code]
            level = levels[node.level]
            if node.level == "subheading" and node.uncoded:
                level = "grupo"
            for note in node.notes:
                source = note.get("source")
                out.append(
                    {
                        "nivel": level,
                        "codigo": code,
                        "tipo": note["kind"],
                        "texto": note["text"],
                        "fuente": SOURCES[source].label if source else consolidated,
                    }
                )
            for text in node.annotations:
                out.append(
                    {
                        "nivel": level,
                        "codigo": code,
                        "tipo": "nota_camara",
                        "texto": text,
                        "fuente": consolidated,
                    }
                )
        return out

    def _historial(self) -> list[Row]:
        by_authority = _by_authority()
        out: list[Row] = []
        order = {code: i for i, code in enumerate(self.tarifa.order)}
        for code in sorted(self.events.descriptions, key=lambda c: (order.get(c, 1 << 30), c)):
            for t in self.events.descriptions[code]:
                src = by_authority.get(t.authority)
                out.append(
                    {
                        "fraccion": code,
                        "desde": _iso(t.start),
                        "hasta": _last_day(t.end),
                        "descripcion": t.description,
                        "decreto": src.label if src else t.authority,
                    }
                )
        return out

    def _fuentes(self) -> list[Row]:
        return [
            {
                "clave": s.key,
                "archivo": s.path,
                "url": s.url,
                "dof": _iso(s.dof),
                "codnota": s.cod_nota,
                "titulo": s.title,
                "sha256": s.sha256,
                "papel": s.role,
            }
            for s in SOURCES.values()
        ]

    def _aplicacion(self) -> list[Row]:
        out: list[Row] = []
        for a in self.events.applied:
            out.append(
                {
                    "clave": a["key"],
                    "decreto": SOURCES[str(a["key"])].label,
                    "aplicado": "si",
                    "que": a["what"],
                    "fracciones": a["fracciones"],
                    "motivo": "",
                }
            )
        for n in self.events.not_applied:
            out.append(
                {
                    "clave": n["key"],
                    "decreto": SOURCES[n["key"]].label,
                    "aplicado": "no",
                    "que": n["what"],
                    "fracciones": None,
                    "motivo": n["why"],
                }
            )
        return out

    def _cotejo(self) -> list[Row]:
        return [
            {
                "fraccion": m["code"],
                "tipo": m["kind"].upper(),
                "publicado": m["camara"] or "",
                "calculado": m["computed"] or "",
                "medida_parcial": m["partial_measure"] or "",
                "ultima_nota_camara": m["last_camara_note"] or "",
            }
            for m in crosscheck(self)["mismatches"]
        ]

    # -- summary --------------------------------------------------------------------------------

    def counts(self) -> dict[str, Any]:
        t = self.tables()
        nicos = t["nicos"]
        medidas = t["medidas"]
        kinds = Counter(m["tipo"] + (" (alcance parcial)" if m["alcance"] else "") for m in medidas)
        hs = [s for s in t["subpartidas"] if s["sistema_armonizado"]]
        return {
            "secciones": len(t["secciones"]),
            "capitulos": len(t["capitulos"]),
            "partidas": len(t["partidas"]),
            "grupos_sin_codigo": len(t["grupos"]),
            "subpartidas": len(t["subpartidas"]),
            "subpartidas_sa2022": len(hs),
            "fracciones": len(t["fracciones"]),
            "fracciones_con_nico_vigente": sum(1 for f in t["fracciones"] if f["nicos_vigentes"]),
            "nicos": len(nicos),
            "nicos_vigentes": sum(1 for n in nicos if not n["baja"]),
            "nicos_suprimidos": sum(1 for n in nicos if n["baja"]),
            "medidas": len(medidas),
            "medidas_por_tipo": dict(sorted(kinds.items())),
            "fracciones_con_historial_de_texto": len(self.events.descriptions),
            "notas": len(t["notas"]),
            "cotejo_diferencias": len(t["cotejo"]),
        }

    def metadata(self) -> dict[str, Any]:
        ligie = SOURCES["ligie"]
        return {
            "titulo": "Tarifa de la Ley de los Impuestos Generales de Importación y de Exportación "
            "(TIGIE 2022) con sus Números de Identificación Comercial (NICO)",
            "version": __version__,
            "ley": f"LIGIE {SOURCES['orig'].authority}, en vigor el {LIGIE_IN_FORCE:%d-%m-%Y}",
            "texto_consolidado": f"Cámara de Diputados, {ligie.url} (al "
            f"{CONSOLIDATED_ON:%d-%m-%Y})",
            "decretos_hasta": max(s.dof for s in SOURCES.values()).isoformat(),
            "indice_fuentes": INDEX_URL,
            "fecha_corte_calculado": _iso(self.as_of),
            "licencia_datos": "CC0-1.0",
        }

    def summary(self) -> dict[str, Any]:
        check = crosscheck(self)
        return {
            "edicion": self.metadata(),
            "conteos": self.counts(),
            "fuentes": self.sources,
            "aplicacion": self.tables()["aplicacion"],
            "cotejo": {
                "fecha": check["as_of"],
                "cuotas_comparadas": check["rates_compared"],
                "diferencias": len(check["mismatches"]),
            },
            "fracciones_sin_nico": nico_gaps(self),
            "advertencias": self.warnings,
            "errores": self.errors,
        }


def build(capture: Capture, *, as_of: date = CONSOLIDATED_ON) -> Edition:
    sources = capture.verify()
    tarifa = parse_tarifa(capture.items("ligie"))
    nicos = NicoSet()
    apply_acuerdo(nicos, capture.items("nico"), effective=LIGIE_IN_FORCE, source="nico", base=True)
    apply_acuerdo(
        nicos,
        capture.items("nico_mod1"),
        effective=NICO_MOD1_IN_FORCE,
        source="nico_mod1",
        base=False,
    )
    apply_acuerdo(
        nicos,
        capture.items("nico_mod2"),
        effective=NICO_MOD2_IN_FORCE,
        source="nico_mod2",
        base=False,
    )
    events = collect(capture)
    segments = build_segments(events)
    for code, texts in events.descriptions.items():
        node = tarifa.nodes.get(code)
        if node is not None and texts[-1].description != node.description:
            events.warnings.append(
                f"fracción {node.dotted}: the decree's text differs from the Cámara's"
            )
    warnings = [f"tarifa: {w}" for w in tarifa.warnings]
    warnings += [f"nico: {w}" for w in nicos.warnings]
    warnings += [f"decrees: {w}" for w in events.warnings]
    for chapter, notes in nicos.annotations.items():
        node = tarifa.nodes.get(chapter)
        if node is not None:
            node.notes.extend(notes)
    current = set(tarifa.fracciones())
    for code in sorted(set(events.base) - current):
        warnings.append(f"fracción {code} of the original Tarifa is not in the consolidated text")
    for code in sorted(current - set(events.base)):
        warnings.append(
            f"fracción {code} has no base cuota (not in the original Tarifa or a reform)"
        )
    fracciones = tarifa.fracciones()
    for nico in nicos.nicos.values():
        if nico.fraccion not in fracciones:
            warnings.append(f"NICO {nico.code} without its fracción in the Tarifa")
    return Edition(
        tarifa=tarifa,
        nicos=nicos,
        events=events,
        segments=segments,
        sources=sources,
        as_of=as_of,
        warnings=warnings,
    )


def crosscheck(edition: Edition, day: date = CONSOLIDATED_ON) -> dict[str, Any]:
    """The computed IGI/IGE on the Cámara's consolidation date against the consolidated Tarifa."""
    mismatches: list[dict[str, Any]] = []
    total = 0
    scoped: dict[tuple[str, str], list[list[Segment]]] = defaultdict(list)
    for (c, k, scope), segs in edition.segments.items():
        if scope:
            scoped[(c, k)].append(segs)
    for code, node in edition.tarifa.fracciones().items():
        for kind, shown in (("igi", node.imp), ("ige", node.exp)):
            total += 1
            mine = rate_on(edition.segments.get((code, kind, ""), []), day)
            if (shown.text if shown else None) == (mine.text if mine else None):
                continue
            partial = next(
                (r for segs in scoped.get((code, kind), []) if (r := rate_on(segs, day))),
                None,
            )
            mismatches.append(
                {
                    "code": code,
                    "kind": kind,
                    "camara": shown.cell if shown else None,
                    "computed": mine.cell if mine else None,
                    "partial_measure": partial.cell if partial else None,
                    "last_camara_note": node.annotations[-1] if node.annotations else None,
                }
            )
    return {"as_of": _iso(day), "rates_compared": total, "mismatches": mismatches}


def nico_gaps(edition: Edition) -> dict[str, list[str]]:
    with_nico = {n.fraccion for n in edition.nicos.nicos.values() if n.valid_to is None}
    prohibited: list[str] = []
    missing: list[str] = []
    for code, node in edition.tarifa.fracciones().items():
        if code in with_nico:
            continue
        if node.imp is not None and node.imp.text.lower().startswith("prohibid"):
            prohibited.append(code)
        else:
            missing.append(code)
    return {"prohibidas_sin_nico": prohibited, "sin_nico": missing}
