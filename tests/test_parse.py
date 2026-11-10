"""The readers: the LibreOffice HTML export, rates, the Tarifa tree and the NICO acuerdos."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from tests import TARIFF
from tigie_nico_mx.html import Item, Para, Row, parse_items, read_items
from tigie_nico_mx.nico import NicoSet, apply_acuerdo
from tigie_nico_mx.rates import parse_rate
from tigie_nico_mx.sources import LIGIE_IN_FORCE, SOURCES
from tigie_nico_mx.tigie import parse_tarifa, split_description


def items(key: str) -> list[Item]:
    return read_items(TARIFF / SOURCES[key].html)


class HtmlTest(unittest.TestCase):
    def test_keeps_paragraphs_rows_and_cell_lines_and_drops_the_page_header(self) -> None:
        markup = """<html><head><title>x</title><style>p{}</style></head><body>
        <div title="header"><table><tr><td><p>Cámara de Diputados</p></td></tr></table></div>
        <p>Capítulo<br>01</p>
        <table><tr><td><p>0101.21.01</p></td><td><p>Reproductores
           de raza pura.</p><p>Arancel modificado DOF 18-11-2022</p></td></tr></table>
        <p>Artículo 2o.-</p></body></html>"""
        out = parse_items(markup)
        self.assertEqual(out[0], Para("Capítulo\n01"))
        self.assertIsInstance(out[1], Row)
        assert isinstance(out[1], Row)
        self.assertEqual(
            out[1].cells,
            ("0101.21.01", "Reproductores de raza pura.\nArancel modificado DOF 18-11-2022"),
        )
        self.assertEqual(out[2], Para("Artículo 2o.-"))
        self.assertTrue(all("Cámara" not in getattr(x, "text", "") for x in out))


class RateTest(unittest.TestCase):
    def test_rates(self) -> None:
        cases = [
            ("15", "15%", "15", Decimal(15)),
            ("Ex.", "Ex.", "Ex.", Decimal(0)),
            ("Ex", "Ex.", "Ex.", Decimal(0)),
            ("156", "156%", "156", Decimal(156)),
            ("210.44", "210.44%", "210.44", Decimal("210.44")),
            (
                "AE (0.36 Dls EUA por Kg)",
                "AE (0.36 Dls EUA por Kg)",
                "AE (0.36 Dls EUA por Kg)",
                None,
            ),
            ("Prohibida", "Prohibida", "Prohibida", None),
            ("20%", "20%", "20", Decimal(20)),
        ]
        for cell, text, published, numeric in cases:
            with self.subTest(cell=cell):
                rate = parse_rate(cell)
                assert rate is not None
                self.assertEqual((rate.text, rate.cell, rate.numeric), (text, published, numeric))
        self.assertIsNone(parse_rate("  "))


class TarifaTest(unittest.TestCase):
    def test_description_and_the_camaras_annotations_split(self) -> None:
        cell = (
            "Los demás.\nArancel modificado con vigencia temporal DOF 18-11-2022\n(antes Imp. 15)\n"
            "Arancel “eliminado” del Decreto DOF 06-01-2023 por Decreto DOF 31-12-2025 (antes "
            "Imp. Ex. y se restablece Imp. 15)"
        )
        description, notes = split_description(cell)
        self.assertEqual(description, "Los demás.")
        self.assertEqual(
            notes,
            [
                "Arancel modificado con vigencia temporal DOF 18-11-2022 (antes Imp. 15)",
                "Arancel “eliminado” del Decreto DOF 06-01-2023 por Decreto DOF 31-12-2025 "
                "(antes Imp. Ex. y se restablece Imp. 15)",
            ],
        )
        self.assertEqual(
            split_description("Totoabas de manejo intensivo\nFracción adicionada DOF 21-07-2025"),
            ("Totoabas de manejo intensivo", ["Fracción adicionada DOF 21-07-2025"]),
        )

    def test_the_tree(self) -> None:
        tarifa = parse_tarifa(items("ligie"))
        self.assertEqual(tarifa.warnings, [])
        nodes = tarifa.nodes
        laptop = nodes["84713001"]
        self.assertEqual((laptop.level, laptop.parent, laptop.unit), ("fraccion", "847130", "Pza"))
        assert laptop.imp is not None
        self.assertEqual(laptop.imp.text, "Ex.")
        self.assertTrue(laptop.description.startswith("Máquinas automáticas para tratamiento"))
        # the uncoded one-dash group "-Las demás máquinas automáticas…:" gets 84714
        group = nodes["84714"]
        self.assertTrue(group.uncoded)
        self.assertEqual((group.level, group.parent), ("subheading", "8471"))
        self.assertEqual(nodes["847141"].parent, "84714")
        self.assertEqual(nodes["8471"].parent, "84")
        self.assertEqual(nodes["84"].level, "chapter")
        chapter = nodes["01"]
        self.assertEqual(chapter.description, "Animales vivos")
        self.assertEqual([n["kind"] for n in chapter.notes], ["notas_capitulo"])
        first = tarifa.sections[0]
        self.assertEqual(
            (first.code, first.sort, first.title),
            ("I", 1, "ANIMALES VIVOS Y PRODUCTOS DEL REINO ANIMAL"),
        )
        self.assertEqual(first.chapters, ["01", "03"])
        self.assertEqual(first.notes[0], "Notas.")
        by_code = {s.code: s for s in tarifa.sections}
        self.assertEqual(by_code["XVI"].chapters, ["84"])
        self.assertEqual(by_code["XXII"].chapters, ["98"])
        cattle = nodes["01022999"]
        self.assertEqual(cattle.description, "Los demás.")
        self.assertEqual(len(cattle.annotations), 3)
        assert cattle.imp is not None
        self.assertEqual(cattle.imp.text, "15%")
        self.assertEqual(nodes["03028902"].annotations, ["Fracción adicionada DOF 21-07-2025"])
        seen: set[str] = set()
        for code in tarifa.order:  # every node's parent comes before it
            parent = nodes[code].parent
            self.assertTrue(parent is None or parent in seen, code)
            seen.add(code)

    def test_the_original_tarifa_lacks_the_2025_fracciones(self) -> None:
        original = parse_tarifa(items("orig")).fracciones()
        self.assertNotIn("03028902", original)
        for code, rate in (("52121101", "10%"), ("09042102", "20%"), ("98030001", "10%")):
            imp = original[code].imp
            assert imp is not None
            self.assertEqual(imp.text, rate, code)


class NicoTest(unittest.TestCase):
    def test_creation_and_suppression_dates(self) -> None:
        nicos = NicoSet()
        apply_acuerdo(nicos, items("nico"), effective=LIGIE_IN_FORCE, source="nico", base=True)
        apply_acuerdo(
            nicos, items("nico_mod1"), effective=date(2023, 7, 1), source="nico_mod1", base=False
        )
        apply_acuerdo(
            nicos, items("nico_mod2"), effective=date(2024, 3, 22), source="nico_mod2", base=False
        )
        self.assertEqual(nicos.warnings, [])
        tablets = nicos.nicos["8471300101"]
        self.assertEqual(tablets.description, 'Tableta electrónica ("Tablets").')
        self.assertEqual((tablets.valid_from, tablets.valid_to), (LIGIE_IN_FORCE, None))
        # mod01 (in force 01-07-2023) splits 8414.51.01: 00 suppressed, 01 and 99 created
        fan = nicos.nicos["8414510100"]
        self.assertEqual((fan.valid_to, fan.suppressed_by), (date(2023, 7, 1), "nico_mod1"))
        self.assertEqual(nicos.nicos["8414510101"].valid_from, date(2023, 7, 1))
        self.assertEqual(nicos.nicos["8414510101"].description, "Ventiladores de techo.")
        # mod02 (22-03-2024) splits coffee 0901.21.99 into capsules and the rest
        self.assertEqual(nicos.nicos["0901219900"].valid_to, date(2024, 3, 22))
        self.assertEqual(nicos.nicos["0901219901"].description, "En cápsulas.")
        # the Anotaciones: chapter 72's is reformed by mod01, chapter 09's created by mod02
        self.assertEqual(nicos.annotations["72"][0]["source"], "nico_mod1")
        self.assertTrue(
            nicos.annotations["09"][0]["text"].startswith("1. Se entenderá por “cápsulas”")
        )


if __name__ == "__main__":
    unittest.main()
