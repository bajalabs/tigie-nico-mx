"""Decree events → non-overlapping measure segments per fracción, kind and scope.

For IGI and IGE the rate on a day is the latest-published overlay in force that day, else the
Tarifa's own cuota (the LIGIE as published, then each permanent change from its date). Adjacent days
with the same rate and the same authority form one segment; a segment that resumes the Tarifa's
cuota after a temporary one says so in its notes. A scoped IGI (an acotación, the `alcance` column)
holds only the partial overlays of that scope: no segment between them.

The segments of one (fracción, kind, scope) never overlap; only the last segment of a series is
open-ended.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from tigie_nico_mx.decrees import Change, Events, Overlay
from tigie_nico_mx.rates import Rate
from tigie_nico_mx.sources import LIGIE_IN_FORCE, LIGIE_IN_FORCE_SOURCE, SOURCES

BASE_SOURCE = "orig"
BASE_AUTHORITY = SOURCES[BASE_SOURCE].authority
BASE_NOTE = (
    "Cuota de la Tarifa del artículo 1o. de la LIGIE 2022 (DOF 07-06-2022 codNota 5654292), en "
    f"vigor desde el 12-12-2022 ({LIGIE_IN_FORCE_SOURCE})."
)


@dataclass(frozen=True)
class Segment:
    start: date
    end: date | None  # exclusive
    rate: Rate
    authority: str
    note: str
    scope: str = ""
    source: str = BASE_SOURCE  # the key in sources.json of the publication that set it

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day < self.end)


@dataclass(frozen=True)
class _Piece:
    rate: Rate
    authority: str
    note: str
    scope: str
    temporary: bool
    source: str


def _authority(source: str) -> str:
    return SOURCES[source].authority


def _base_piece(change: Change | None, created: tuple[date, str] | None, rate: Rate) -> _Piece:
    if change is not None:
        return _Piece(rate, _authority(change.source), change.note, "", False, change.source)
    if created is not None:
        when, source = created
        note = f"Fracción adicionada por {_authority(source)}, en vigor el {when:%d-%m-%Y}."
        return _Piece(rate, _authority(source), note, "", False, source)
    return _Piece(rate, BASE_AUTHORITY, BASE_NOTE, "", False, BASE_SOURCE)


def _overlay_piece(o: Overlay) -> _Piece:
    note = o.note
    if o.ended_by and o.end is not None:
        last = o.end - timedelta(days=1)
        note = f"{note} Concluyó el {last:%d-%m-%Y} ({o.ended_by})."
    return _Piece(o.rate, _authority(o.source), note, o.scope, True, o.source)


Key = tuple[str, str, str]  # (fracción, kind, scope)


def segments_for(
    kind: str,
    start: date,
    base: Rate | None,
    created: tuple[date, str] | None,
    changes: list[Change],
    overlays: list[Overlay],
    scope: str = "",
) -> list[Segment]:
    """One fracción's segments of one kind and scope (a scoped series has only its overlays)."""
    if scope:
        base, changes = None, []
    changes = sorted(changes, key=lambda ch: ch.start)
    if kind == "ige":
        # decrees about import cuotas restate the export column unchanged: not a new IGE
        kept: list[Change] = []
        for ch in changes:
            before = kept[-1].rate if kept else base
            if before is None or ch.rate.text != before.text:
                kept.append(ch)
        changes = kept
    if scope:
        cuts = {o.start for o in overlays} | {o.end for o in overlays if o.end is not None}
    else:
        cuts = {start} | {ch.start for ch in changes}
        cuts |= {o.start for o in overlays} | {o.end for o in overlays if o.end is not None}
    points = sorted(d for d in cuts if d >= start)
    pieces: list[tuple[date, date | None, _Piece | None, bool]] = []
    for i, day in enumerate(points):
        nxt = points[i + 1] if i + 1 < len(points) else None
        active = [o for o in overlays if o.start <= day and (o.end is None or day < o.end)]
        piece: _Piece | None
        resumed = False  # the Tarifa's cuota (or an earlier change) applies again
        if active:
            top = max(active, key=lambda o: (o.rank, o.start))
            piece = _overlay_piece(top)
        elif scope:
            piece = None
        else:
            current = [ch for ch in changes if ch.start <= day]
            change = current[-1] if current else None
            rate = change.rate if change is not None else base
            piece = None if rate is None else _base_piece(change, created, rate)
            resumed = change is None or change.start < day
        pieces.append((day, nxt, piece, resumed))
    out: list[Segment] = []
    previous: _Piece | None = None
    for day, nxt, piece, resumed in pieces:
        if piece is None:
            previous = None
            continue
        if out and previous is not None and out[-1].end == day and _same(previous, piece):
            last = out[-1]
            out[-1] = Segment(
                last.start, nxt, last.rate, last.authority, last.note, last.scope, last.source
            )
        else:
            note = piece.note
            if previous is not None and previous.temporary and resumed:
                note = f"{note} Rige de nuevo al concluir la medida temporal anterior."
            out.append(
                Segment(day, nxt, piece.rate, piece.authority, note, piece.scope, piece.source)
            )
        previous = piece
    return out


def _same(a: _Piece, b: _Piece) -> bool:
    return (a.rate.text, a.authority, a.note, a.scope) == (
        b.rate.text,
        b.authority,
        b.note,
        b.scope,
    )


def build_segments(events: Events) -> dict[Key, list[Segment]]:
    """(fracción, kind, scope) → segments, for every fracción of the base: its IGI and IGE
    (scope '') and one IGI series per acotación a decree gave it."""
    changes: dict[tuple[str, str], list[Change]] = defaultdict(list)
    for ch in events.changes:
        changes[(ch.code, ch.kind)].append(ch)
    overlays: dict[Key, list[Overlay]] = defaultdict(list)
    for o in events.overlays:
        overlays[(o.code, o.kind, o.scope)].append(o)
    scopes: dict[str, set[str]] = defaultdict(set)
    for code, kind, scope in overlays:
        if scope and kind == "igi":
            scopes[code].add(scope)
    out: dict[Key, list[Segment]] = {}
    for code, (imp, exp) in events.base.items():
        created = events.created.get(code)
        start = created[0] if created else LIGIE_IN_FORCE
        series = [("igi", imp, ""), ("ige", exp, "")]
        series += [("igi", None, s) for s in sorted(scopes.get(code, ()))]
        for kind, base, scope in series:
            segs = segments_for(
                kind,
                start,
                base,
                created,
                changes.get((code, kind), []),
                overlays.get((code, kind, scope), []),
                scope,
            )
            if segs:
                out[(code, kind, scope)] = segs
    return out


def rate_on(segments: list[Segment], day: date) -> Rate | None:
    for seg in segments:
        if seg.covers(day):
            return seg.rate
    return None
