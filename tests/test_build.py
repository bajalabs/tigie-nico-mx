"""From a capture to the tables, and the tables to files (fixtures: 21 fracciones, 15 chapters)."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests import TARIFF
from tigie_nico_mx.build import COLUMNS, build, nico_gaps
from tigie_nico_mx.export import csv_bytes, export, sha256_bytes
from tigie_nico_mx.sources import SOURCES, Capture

EDITION = build(Capture(TARIFF))
TABLES = EDITION.tables()

# The first columns are a contract with downstream users (hs-crosswalk-us-mx and others).
CONTRACT = {
    "subpartidas": ["subpartida", "partida", "capitulo", "descripcion"],
    "fracciones": ["fraccion", "subpartida", "descripcion", "umt", "igi_vigente", "ige_vigente"],
    "nicos": ["fraccion", "nico", "codigo", "descripcion", "alta", "baja"],
    "medidas": ["fraccion", "tipo", "valor", "desde", "hasta", "decreto", "alcance"],
}


def by(table: str, key: str) -> dict[str, dict[str, object]]:
    return {str(r[key]): r for r in TABLES[table]}


class TablesTest(unittest.TestCase):
    def test_contract_columns_come_first(self) -> None:
        for name, columns in CONTRACT.items():
            with self.subTest(table=name):
                self.assertEqual(COLUMNS[name][: len(columns)], columns)
        for name, rows in TABLES.items():
            for row in rows:
                self.assertEqual(set(row), set(COLUMNS[name]), name)

    def test_counts_and_no_warnings(self) -> None:
        self.assertEqual(EDITION.warnings, [])
        counts = EDITION.counts()
        self.assertEqual(counts["fracciones"], 21)
        self.assertEqual(counts["capitulos"], 15)
        self.assertEqual(counts["secciones"], len(EDITION.tarifa.sections))

    def test_tree_rows(self) -> None:
        laptop = by("fracciones", "fraccion")["84713001"]
        self.assertEqual(
            (laptop["subpartida"], laptop["umt"], laptop["igi_vigente"], laptop["ige_vigente"]),
            ("847130", "Pza", "Ex.", "Ex."),
        )
        self.assertEqual(
            (laptop["partida"], laptop["capitulo"], laptop["alta"]), ("8471", "84", "2022-12-12")
        )
        self.assertEqual(by("fracciones", "fraccion")["03028902"]["alta"], "2026-01-17")
        cattle = by("fracciones", "fraccion")["01022999"]
        self.assertEqual(cattle["igi_vigente"], "15")  # the Tarifa's convention: a bare percent
        sub = by("subpartidas", "subpartida")["847141"]
        self.assertEqual((sub["partida"], sub["capitulo"], sub["grupo"]), ("8471", "84", "84714"))
        self.assertEqual(by("grupos", "grupo")["84714"]["partida"], "8471")
        self.assertNotIn("84714", by("subpartidas", "subpartida"))  # not a six-digit code
        self.assertEqual(by("subpartidas", "subpartida")["980300"]["sistema_armonizado"], 0)
        self.assertEqual(by("subpartidas", "subpartida")["847130"]["sistema_armonizado"], 1)
        for row in TABLES["subpartidas"]:
            self.assertRegex(str(row["subpartida"]), r"^\d{6}$")
        for row in TABLES["fracciones"]:
            self.assertRegex(str(row["fraccion"]), r"^\d{8}$")
        self.assertEqual(by("capitulos", "capitulo")["84"]["seccion"], "XVI")

    def test_nicos(self) -> None:
        nicos = by("nicos", "codigo")
        fan = nicos["8414510100"]
        self.assertEqual((fan["alta"], fan["baja"]), ("2022-12-12", "2023-07-01"))
        self.assertEqual(fan["fuente_baja"], SOURCES["nico_mod1"].label)
        tablets = nicos["8471300101"]
        self.assertEqual(
            (tablets["fraccion"], tablets["nico"], tablets["baja"]), ("84713001", "01", "")
        )
        for row in TABLES["nicos"]:
            self.assertEqual(row["codigo"], f"{row['fraccion']}{row['nico']}")

    def test_measures(self) -> None:
        steel = [m for m in TABLES["medidas"] if m["fraccion"] == "72081003" and m["tipo"] == "IGI"]
        self.assertEqual(steel[0]["desde"], "2022-12-12")
        self.assertEqual(steel[0]["valor"], "15")
        self.assertTrue(str(steel[0]["decreto"]).startswith("DOF 18-11-2022: "))
        # `hasta` is the last day in force: the 22-04-2024 cuota runs to the eve of the reform
        self.assertEqual(
            (steel[-2]["hasta"], steel[-1]["desde"], steel[-1]["hasta"]),
            ("2025-12-31", "2026-01-01", ""),
        )
        self.assertEqual(steel[-1]["valor"], "35")
        for a, b in zip(steel, steel[1:], strict=False):
            self.assertLess(str(a["hasta"]), str(b["desde"]))
        bread = [m for m in TABLES["medidas"] if m["fraccion"] == "19054001" and m["alcance"]]
        self.assertEqual(
            sorted((m["alcance"], m["desde"], m["hasta"]) for m in bread),
            [
                ("Únicamente pan de caja.", "2023-01-07", "2026-12-31"),
                ("Únicamente: Pan de caja.", "2022-12-12", "2023-01-06"),
            ],
        )
        self.assertEqual({m["tipo"] for m in TABLES["medidas"]}, {"IGI", "IGE"})

    def test_description_history(self) -> None:
        rows = [r for r in TABLES["historial_descripciones"] if r["fraccion"] == "03028901"]
        self.assertEqual(
            [(r["desde"], r["hasta"], r["descripcion"]) for r in rows],
            [
                ("2022-12-12", "2026-01-16", "Totoabas."),
                ("2026-01-17", "", "Totoabas en vida libre."),
            ],
        )
        self.assertEqual(rows[1]["decreto"], SOURCES["ref01"].label)

    def test_crosscheck_and_gaps(self) -> None:
        mismatches = {(r["fraccion"], r["tipo"]) for r in TABLES["cotejo"]}
        # expired temporaries, partial exemptions, and the Cámara's two errors on 5212.1x
        self.assertLessEqual(
            {("30024106", "IGI"), ("19054001", "IGI"), ("52121101", "IGI")}, mismatches
        )
        self.assertNotIn(("84713001", "IGI"), mismatches)
        self.assertEqual(nico_gaps(EDITION)["sin_nico"], ["03028902"])
        applied = {r["clave"] for r in TABLES["aplicacion"] if r["aplicado"] == "si"}
        self.assertIn("tarifa16", applied)


class ExportTest(unittest.TestCase):
    def test_csv_quoting_and_header(self) -> None:
        data = csv_bytes(["a", "b"], [{"a": 'x, "y"', "b": None}, {"a": "línea\ndos", "b": 3}])
        rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
        self.assertEqual(rows, [["a", "b"], ['x, "y"', ""], ["línea\ndos", "3"]])

    def test_export_is_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = export(EDITION, Path(one))
            export(EDITION, Path(two))
            sums_one = (Path(one) / "SHA256SUMS").read_text(encoding="utf-8")
            sums_two = (Path(two) / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertEqual(sums_one, sums_two)
            names = {p.relative_to(one).as_posix() for p in first}
            for table in COLUMNS:
                self.assertIn(f"csv/{table}.csv", names)
            self.assertLessEqual(
                {
                    "tigie.sqlite",
                    "tigie.json",
                    "tigie-nico-mx-csv.zip",
                    "resumen.json",
                    "SHA256SUMS",
                },
                names,
            )
            for line in sums_one.splitlines():
                digest, rel = line.split("  ", 1)
                self.assertEqual(sha256_bytes((Path(one) / rel).read_bytes()), digest, rel)
            header = (
                (Path(one) / "csv" / "fracciones.csv").read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertTrue(
                header.startswith("fraccion,subpartida,descripcion,umt,igi_vigente,ige_vigente")
            )
            with zipfile.ZipFile(Path(one) / "tigie-nico-mx-csv.zip") as archive:
                self.assertIn("csv/nicos.csv", archive.namelist())

    def test_sqlite_tables_and_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export(EDITION, Path(tmp), ("sqlite",))
            db = sqlite3.connect(Path(tmp) / "tigie.sqlite")
            try:
                count = db.execute("SELECT count(*) FROM fracciones").fetchone()[0]
                self.assertEqual(count, 21)
                row = db.execute(
                    "SELECT subpartida_descripcion, capitulo_descripcion, seccion "
                    "FROM v_fracciones WHERE fraccion = '84713001'"
                ).fetchone()
                self.assertEqual(row[2], "XVI")
                history = db.execute(
                    "SELECT valor, desde, hasta FROM medidas WHERE fraccion = '72081003' "
                    "AND tipo = 'IGI' AND alcance IS NULL ORDER BY desde"
                ).fetchall()
                self.assertEqual(history[-1], ("35", "2026-01-01", None))
                for view in ("v_medidas_hoy", "v_nicos_vigentes", "v_arancel_hoy"):
                    db.execute(f"SELECT * FROM {view} LIMIT 1").fetchall()  # noqa: S608
                laptop = db.execute(
                    "SELECT igi, ige FROM v_arancel_hoy WHERE fraccion = '84713001'"
                ).fetchone()
                self.assertEqual(laptop, ("Ex.", "Ex."))
                meta = dict(db.execute("SELECT clave, valor FROM edicion").fetchall())
                self.assertEqual(meta["licencia_datos"], "CC0-1.0")
            finally:
                db.close()

    def test_json_edition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            export(EDITION, Path(tmp), ("json",))
            data = json.loads((Path(tmp) / "tigie.json").read_text(encoding="utf-8"))
            fracciones = {f["fraccion"]: f for f in data["fracciones"]}
            self.assertEqual(len(fracciones), 21)
            self.assertEqual(fracciones["84713001"]["nicos"][0]["codigo"], "8471300101")
            self.assertIn("historial_descripciones", fracciones["03028901"])
            summary = json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["conteos"]["fracciones"], 21)


if __name__ == "__main__":
    unittest.main()
