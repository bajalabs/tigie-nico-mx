"""The decrees as dated measures, on fixtures cut from the real decrees."""

from __future__ import annotations

import unittest
from datetime import date

from tests import TARIFF
from tigie_nico_mx.decrees import Change, Overlay, collect, decree_rows, spanish_dates
from tigie_nico_mx.html import Row
from tigie_nico_mx.rates import Rate, parse_rate
from tigie_nico_mx.sources import Capture
from tigie_nico_mx.timeline import (
    BASE_AUTHORITY,
    Key,
    Segment,
    build_segments,
    rate_on,
    segments_for,
)

CAPTURE = Capture(TARIFF)
EVENTS = collect(CAPTURE)
SEGMENTS: dict[Key, list[Segment]] = build_segments(EVENTS)


def r(text: str) -> Rate:
    rate = parse_rate(text)
    assert rate is not None
    return rate


def igi(code: str, day: str) -> str | None:
    rate = rate_on(SEGMENTS.get((code, "igi", ""), []), date.fromisoformat(day))
    return rate.text if rate else None


class DecreeRowsTest(unittest.TestCase):
    def test_every_layout(self) -> None:
        rows = decree_rows(
            [
                Row(0, ("0101.21.01", "", "Reproductores de raza pura.", "Cbza", "10", "Ex.")),
                Row(
                    0, ("1905.40.01", "Pan tostado.", "Kg", "Ex", "Ex", "Únicamente: Pan de caja.")
                ),
                Row(0, ("3303.00.01", "Aguas de tocador.", "L", "25", "Ex.")),
                Row(0, ("01.02", "Animales vivos de la especie bovina.", "", "", "", "")),
            ]
        )
        self.assertEqual(
            [(x.code, x.imp.text if x.imp else None, x.scope) for x in rows],
            [
                ("01012101", "10%", ""),
                ("19054001", "Ex.", "Únicamente: Pan de caja."),
                ("33030001", "25%", ""),
            ],
        )
        self.assertEqual(
            spanish_dates("a partir del 22 de septiembre de 2023 y del 1 de junio del 2023"),
            [date(2023, 9, 22), date(2023, 6, 1)],
        )


class TimelineTest(unittest.TestCase):
    def test_8471_30_01_stays_exempt(self) -> None:
        segs = SEGMENTS[("84713001", "igi", "")]
        self.assertEqual(len(segs), 1)
        self.assertEqual((segs[0].authority, segs[0].source), (BASE_AUTHORITY, "orig"))
        self.assertEqual((segs[0].start, segs[0].end), (date(2022, 12, 12), None))
        self.assertEqual(igi("84713001", "2025-12-31"), "Ex.")
        self.assertEqual(igi("84713001", "2026-01-02"), "Ex.")

    def test_steel_from_the_ligie_to_the_reform(self) -> None:
        code = "72081003"
        self.assertIsNone(igi(code, "2022-12-11"))  # before the LIGIE 2022
        self.assertEqual(igi(code, "2022-12-12"), "15%")  # DOF 18-11-2022 art. Segundo
        self.assertEqual(igi(code, "2023-06-01"), "10%")  # its transitorio Segundo, a)
        self.assertEqual(igi(code, "2023-08-16"), "25%")  # DOF 15-08-2023
        self.assertEqual(igi(code, "2024-04-23"), "25%")  # DOF 22-04-2024
        self.assertEqual(igi(code, "2026-01-01"), "35%")  # DOF 29-12-2025, permanent
        self.assertEqual(
            [s.source for s in SEGMENTS[(code, "igi", "")]],
            ["tarifa02", "tarifa02", "tarifa07", "tarifa09", "ref02"],
        )

    def test_rates_on_dates(self) -> None:
        cases = [
            # temporary cuotas the Cámara's consolidated Tarifa still shows after they ended
            ("30024106", "2023-05-09", "Ex."),
            ("30024106", "2023-05-10", "5%"),
            ("87024001", "2024-09-30", "Ex."),
            ("87024001", "2024-10-01", "15%"),
            ("71041001", "2024-04-22", "25%"),
            ("71041001", "2024-04-23", "Ex."),
            ("10059004", "2023-12-31", "50%"),
            ("10059004", "2024-01-01", "20%"),
            # the canasta básica list: in, out
            ("01022999", "2025-12-31", "Ex."),
            ("01022999", "2026-01-01", "15%"),
            ("09042102", "2024-12-31", "Ex."),
            ("09042102", "2025-01-01", "20%"),
            ("31022101", "2024-05-09", "35%"),
            ("31022101", "2025-01-01", "Ex."),
            ("31022101", "2027-01-01", "35%"),
            # a later permanent cuota ends an earlier temporary one
            ("73102999", "2026-04-23", "Ex."),
            ("73102999", "2026-04-24", "35%"),
            # the decree, not the Cámara's consolidation, for 5212.11.01 and 5212.12.01
            ("52121101", "2026-01-01", "25%"),
            ("52121201", "2026-01-01", "35%"),
            # 9803.00.01: exempt five years from 14-10-2026, then the Tarifa's 10% again
            ("98030001", "2026-10-13", "10%"),
            ("98030001", "2026-10-14", "Ex."),
            ("98030001", "2031-10-14", "Ex."),
            ("98030001", "2031-10-15", "10%"),
            # sugar: a specific duty, then 156% from 11-11-2025
            ("17011205", "2025-11-10", "AE (0.36 Dls EUA por Kg)"),
            ("17011205", "2025-11-11", "156%"),
            # a fracción the 21-07-2025 reform created exists from 17-01-2026
            ("03028902", "2026-01-16", None),
            ("03028902", "2026-01-17", "15%"),
        ]
        for code, day, rate in cases:
            with self.subTest(code=code, day=day):
                self.assertEqual(igi(code, day), rate)

    def test_a_partial_exemption_is_a_scoped_igi(self) -> None:
        self.assertEqual(igi("19054001", "2026-10-21"), "10%")
        scoped = {k[2]: v for k, v in SEGMENTS.items() if k[0] == "19054001" and k[2]}
        self.assertEqual(set(scoped), {"Únicamente: Pan de caja.", "Únicamente pan de caja."})
        first, second = scoped["Únicamente: Pan de caja."], scoped["Únicamente pan de caja."]
        self.assertEqual(
            [(s.rate.text, s.start, s.end) for s in first],
            [("Ex.", date(2022, 12, 12), date(2023, 1, 7))],
        )
        self.assertEqual(
            [(s.rate.text, s.start, s.end) for s in second],
            [("Ex.", date(2023, 1, 7), date(2027, 1, 1))],
        )
        self.assertTrue(all(k[1] == "igi" for k in SEGMENTS if k[2]))

    def test_segments_never_overlap(self) -> None:
        for key, segs in SEGMENTS.items():
            for a, b in zip(segs, segs[1:], strict=False):
                self.assertIsNotNone(a.end, key)
                assert a.end is not None
                self.assertLessEqual(a.end, b.start, key)
            self.assertTrue(all(s.end is None or s.start < s.end for s in segs), key)
            self.assertTrue(all(s.end is not None for s in segs[:-1]), key)

    def test_the_engine_on_its_own(self) -> None:
        overlays = [
            Overlay("1", "igi", r("Ex."), date(2023, 1, 1), date(2024, 1, 1), "tarifa03", "a"),
            Overlay("1", "igi", r("25"), date(2023, 6, 1), date(2023, 7, 1), "tarifa07", "b"),
        ]
        changes = [Change("1", "igi", r("35"), date(2025, 1, 1), "ref02", "c")]
        segs = segments_for("igi", date(2022, 12, 12), r("15"), None, changes, overlays)
        self.assertEqual(
            [(s.start.isoformat(), s.rate.text, s.source) for s in segs],
            [
                ("2022-12-12", "15%", "orig"),
                ("2023-01-01", "Ex.", "tarifa03"),
                ("2023-06-01", "25%", "tarifa07"),  # the later decree rules while both apply
                ("2023-07-01", "Ex.", "tarifa03"),
                ("2024-01-01", "15%", "orig"),
                ("2025-01-01", "35%", "ref02"),
            ],
        )
        self.assertIn("Rige de nuevo", segs[4].note)
        self.assertNotIn("Rige de nuevo", segs[5].note)
        ige = segments_for(
            "ige",
            date(2022, 12, 12),
            r("Ex."),
            None,
            [Change("1", "ige", r("Ex."), date(2025, 1, 1), "ref02", "")],
            [],
        )
        self.assertEqual(len(ige), 1)  # an IGE restated unchanged is not a new segment

    def test_the_decrees_applied_and_not(self) -> None:
        keys = {a["key"] for a in EVENTS.applied}
        self.assertLessEqual(
            {"orig", "tarifa02", "tarifa07", "tarifa09", "ref02", "tarifa15", "tarifa16"}, keys
        )
        skipped = {n["key"] for n in EVENTS.not_applied}
        self.assertLessEqual({"tarifa02_mod01", "tarifa02_mod02"}, skipped)
        self.assertEqual(EVENTS.warnings, [])


if __name__ == "__main__":
    unittest.main()
