"""The edition as files: CSV (one per table), a SQLite database with views, a JSON edition, a ZIP of
the CSVs, the build summary and `SHA256SUMS`.

Every output is deterministic: the same capture and the same `as_of` give the same bytes (no build
timestamp anywhere; the ZIP entries carry the consolidation date), so `SHA256SUMS` can be compared
between builds.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from tigie_nico_mx.build import COLUMNS, Edition
from tigie_nico_mx.sources import CONSOLIDATED_ON

CSV_DIR = "csv"
SQLITE_NAME = "tigie.sqlite"
JSON_NAME = "tigie.json"
ZIP_NAME = "tigie-nico-mx-csv.zip"
SUMMARY_NAME = "resumen.json"
SUMS_NAME = "SHA256SUMS"
FORMATS = ("csv", "sqlite", "json")

INTEGER = frozenset(
    {
        "numero",
        "orden",
        "sistema_armonizado",
        "nicos_vigentes",
        "codnota",
        "decreto_codnota",
        "fracciones",
    }
)
REAL = frozenset({"valor_numerico"})
PRIMARY = {
    "secciones": "seccion",
    "capitulos": "capitulo",
    "partidas": "partida",
    "grupos": "grupo",
    "subpartidas": "subpartida",
    "fracciones": "fraccion",
    "nicos": "codigo",
    "fuentes": "clave",
}
INDEXES = {
    "subpartidas": ["partida", "capitulo"],
    "fracciones": ["subpartida", "partida", "capitulo"],
    "nicos": ["fraccion"],
    "medidas": ["fraccion", "tipo", "desde"],
    "notas": ["codigo"],
    "historial_descripciones": ["fraccion"],
}
TODAY = "date('now', 'localtime')"
VIEWS = {
    "v_fracciones": """
SELECT f.fraccion, f.descripcion, f.umt, f.igi_vigente, f.ige_vigente,
       f.igi_calculado, f.ige_calculado, f.nicos_vigentes,
       s.subpartida, s.descripcion AS subpartida_descripcion, s.grupo,
       g.descripcion AS grupo_descripcion,
       p.partida, p.descripcion AS partida_descripcion,
       c.capitulo, c.descripcion AS capitulo_descripcion,
       se.seccion, se.titulo AS seccion_titulo
FROM fracciones f
LEFT JOIN subpartidas s ON s.subpartida = f.subpartida
LEFT JOIN grupos g ON g.grupo = s.grupo
LEFT JOIN partidas p ON p.partida = f.partida
LEFT JOIN capitulos c ON c.capitulo = f.capitulo
LEFT JOIN secciones se ON se.seccion = c.seccion""",
    "v_medidas_hoy": f"""
SELECT * FROM medidas
WHERE desde <= {TODAY} AND (hasta IS NULL OR hasta >= {TODAY})""",
    "v_nicos_vigentes": f"""
SELECT * FROM nicos
WHERE alta <= {TODAY} AND (baja IS NULL OR baja > {TODAY})""",
    "v_arancel_hoy": f"""
SELECT f.fraccion, f.descripcion, f.umt,
  (SELECT m.valor FROM medidas m
    WHERE m.fraccion = f.fraccion AND m.tipo = 'IGI' AND m.alcance IS NULL
      AND m.desde <= {TODAY} AND (m.hasta IS NULL OR m.hasta >= {TODAY})) AS igi,
  (SELECT m.valor FROM medidas m
    WHERE m.fraccion = f.fraccion AND m.tipo = 'IGE' AND m.alcance IS NULL
      AND m.desde <= {TODAY} AND (m.hasta IS NULL OR m.hasta >= {TODAY})) AS ige,
  (SELECT group_concat(m.valor || ' (' || m.alcance || ')', '; ') FROM medidas m
    WHERE m.fraccion = f.fraccion AND m.tipo = 'IGI' AND m.alcance IS NOT NULL
      AND m.desde <= {TODAY} AND (m.hasta IS NULL OR m.hasta >= {TODAY})) AS igi_parcial
FROM fracciones f""",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def csv_bytes(columns: list[str], rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_text(row.get(c)) for c in columns])
    return buffer.getvalue().encode("utf-8")


def write_csv(edition: Edition, out: Path) -> list[Path]:
    folder = out / CSV_DIR
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, rows in edition.tables().items():
        path = folder / f"{name}.csv"
        path.write_bytes(csv_bytes(COLUMNS[name], rows))
        written.append(path)
    return written


def write_zip(csv_paths: list[Path], out: Path) -> Path:
    path = out / ZIP_NAME
    stamp = (CONSOLIDATED_ON.year, CONSOLIDATED_ON.month, CONSOLIDATED_ON.day, 0, 0, 0)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for csv_path in sorted(csv_paths):
            info = zipfile.ZipInfo(f"{CSV_DIR}/{csv_path.name}", date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, csv_path.read_bytes())
    return path


def _sql_type(column: str) -> str:
    if column in INTEGER:
        return "INTEGER"
    if column in REAL:
        return "REAL"
    return "TEXT"


def _sql_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    return value


def write_sqlite(edition: Edition, out: Path) -> Path:
    path = out / SQLITE_NAME
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA page_size = 4096")
        db.execute("PRAGMA journal_mode = OFF")
        db.execute("CREATE TABLE edicion (clave TEXT PRIMARY KEY, valor TEXT)")
        db.executemany(
            "INSERT INTO edicion VALUES (?, ?)",
            [(k, _text(v)) for k, v in edition.metadata().items()],
        )
        for name, rows in edition.tables().items():
            columns = COLUMNS[name]
            defs = []
            for c in columns:
                pk = " PRIMARY KEY" if PRIMARY.get(name) == c else ""
                defs.append(f"{c} {_sql_type(c)}{pk}")
            db.execute(f"CREATE TABLE {name} ({', '.join(defs)})")
            marks = ", ".join("?" for _ in columns)
            db.executemany(
                f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({marks})",
                [[_sql_value(r.get(c)) for c in columns] for r in rows],
            )
            for c in INDEXES.get(name, []):
                db.execute(f"CREATE INDEX {name}_{c} ON {name} ({c})")
        for view, sql in VIEWS.items():
            db.execute(f"CREATE VIEW {view} AS{sql}")
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()
    return path


def edition_json(edition: Edition) -> dict[str, Any]:
    """One document: the tree's upper levels as lists, each fracción with its NICOs, measures and
    dated texts nested."""
    t = edition.tables()
    nicos: dict[str, list[dict[str, Any]]] = {}
    for n in t["nicos"]:
        nicos.setdefault(n["fraccion"], []).append({k: v for k, v in n.items() if k != "fraccion"})
    medidas: dict[str, list[dict[str, Any]]] = {}
    for m in t["medidas"]:
        medidas.setdefault(m["fraccion"], []).append(
            {k: v for k, v in m.items() if k != "fraccion"}
        )
    textos: dict[str, list[dict[str, Any]]] = {}
    for h in t["historial_descripciones"]:
        textos.setdefault(h["fraccion"], []).append({k: v for k, v in h.items() if k != "fraccion"})
    fracciones = []
    for f in t["fracciones"]:
        row = dict(f)
        row["nicos"] = nicos.get(f["fraccion"], [])
        row["medidas"] = medidas.get(f["fraccion"], [])
        if f["fraccion"] in textos:
            row["historial_descripciones"] = textos[f["fraccion"]]
        fracciones.append(row)
    return {
        "edicion": edition.metadata(),
        "secciones": t["secciones"],
        "capitulos": t["capitulos"],
        "partidas": t["partidas"],
        "grupos": t["grupos"],
        "subpartidas": t["subpartidas"],
        "fracciones": fracciones,
        "notas": t["notas"],
        "fuentes": t["fuentes"],
    }


def write_json(edition: Edition, out: Path) -> Path:
    path = out / JSON_NAME
    text = json.dumps(edition_json(edition), ensure_ascii=False, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_summary(edition: Edition, out: Path) -> Path:
    path = out / SUMMARY_NAME
    text = json.dumps(edition.summary(), ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_sums(paths: list[Path], out: Path) -> Path:
    lines = []
    for path in sorted(paths, key=lambda p: p.relative_to(out).as_posix()):
        rel = path.relative_to(out).as_posix()
        lines.append(f"{sha256_bytes(path.read_bytes())}  {rel}")
    sums = out / SUMS_NAME
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sums


def export(edition: Edition, out: Path, formats: tuple[str, ...] = FORMATS) -> list[Path]:
    """Write the requested formats into `out` and `SHA256SUMS` over everything written."""
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if "csv" in formats:
        csv_paths = write_csv(edition, out)
        written += csv_paths
        written.append(write_zip(csv_paths, out))
    if "sqlite" in formats:
        written.append(write_sqlite(edition, out))
    if "json" in formats:
        written.append(write_json(edition, out))
    written.append(write_summary(edition, out))
    written.append(write_sums(written, out))
    return written
