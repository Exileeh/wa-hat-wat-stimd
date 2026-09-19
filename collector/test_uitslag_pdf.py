"""Unit tests for the "Útslach stimming" PDF reader (stdlib unittest; Pillow only for the grid).

    python -m unittest discover -s collector
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uitslag_pdf as up  # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:   # pragma: no cover
    Image = None

GREEN, RED, YELLOW, GREY, DARK = (105, 195, 121), (255, 116, 119), (255, 235, 121), (192, 192, 192), (51, 51, 51)


class TitleInfo(unittest.TestCase):
    def test_motie_without_spaces(self):
        i = up.title_info("07Moasje01-Pragmatischherbestemmen-BBB")
        self.assertEqual((i["agenda"], i["type"], i["number"]), (7, "motie", "1"))
        self.assertFalse(i["withdrawn"] or i["revote"])

    def test_amendement(self):
        i = up.title_info("05Amendemint 02-Geen spaarpot naast de VAR-D66")
        self.assertEqual((i["agenda"], i["type"], i["number"]), (5, "amendement", "2"))

    def test_ocr_o_for_zero_in_agenda_number(self):
        i = up.title_info("1o Moasje frjemd - Underhâld rykswegen - FNP")
        self.assertEqual((i["agenda"], i["type"], i["number"]), (10, "frjemd", None))
        i = up.title_info("O6 Ofhannele moasjes en tasizzings-Finale beslut")
        self.assertEqual((i["agenda"], i["type"]), (6, "besluit"))

    def test_withdrawn_and_revote(self):
        self.assertTrue(up.title_info("YNLUTSEN03Moasje25-Grootsteuitstoters-SP")["withdrawn"])
        i = up.title_info("14b-Werstimming:PS6maaie2026,wurklistpunt03Moasje19-Iedereen draagt bij")
        self.assertTrue(i["revote"])
        self.assertEqual((i["agenda"], i["type"], i["number"]), (14, "motie", "19"))

    def test_besluit(self):
        i = up.title_info("07StartnotysjeFrysk Wenplan-Finalebeslut")
        self.assertEqual((i["agenda"], i["type"], i["number"]), (7, "besluit", None))


class Totals(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(up.parse_totals("J.Stalenburg Voor:2Tegen:4oOnthouding:0 D.Olivier"), (2, 40, 0))
        self.assertEqual(up.parse_totals("Voor: 40 Tegen: 0 Onthouding: 1"), (40, 0, 1))
        self.assertEqual(up.parse_totals("Voor:3oTegen:8Onthouding:0"), (30, 8, 0))
        self.assertIsNone(up.parse_totals("PROVINSJALE steaten"))


class PartyMatch(unittest.TestCase):
    PRIMARY = ["BBB", "PvdA", "PvdD", "PVV", "CDA", "GrienLinks", "Steatelid Jonker",
               "Provinciaal Belang Fryslân", "ChristenUnie"]
    SECONDARY = ["GroenLinks", "FVD", "50PLUS"]

    def test_exact_and_fuzzy(self):
        self.assertEqual(up.match_party("PvdA", self.PRIMARY), "PvdA")
        self.assertEqual(up.match_party("PdA", self.PRIMARY), "PvdA")
        self.assertEqual(up.match_party("PvdD", self.PRIMARY), "PvdD")
        self.assertEqual(up.match_party("PV", self.PRIMARY), "PVV")
        self.assertEqual(up.match_party("SteatelidJonker", self.PRIMARY), "Steatelid Jonker")

    def test_alias_and_secondary(self):
        self.assertEqual(up.match_party("PBF", self.PRIMARY), "Provinciaal Belang Fryslân")
        self.assertEqual(up.match_party("FVD", self.PRIMARY, self.SECONDARY), "FVD")

    def test_rejects_noise(self):
        self.assertIsNone(up.match_party("Voor:7Tegen:35Onthouding:0", self.PRIMARY, self.SECONDARY))
        self.assertIsNone(up.match_party("", self.PRIMARY))


class ModuleMatch(unittest.TestCase):
    """collect.match_pdf_module_item: PDF page -> item of the 'Moasjes en amendeminten' module."""
    RECS = [
        {"title": "03 Moasje 19 - Iedereen draagt bij aan het oplossen van het stikstofslot - GrienLinks, PvdA en SP",
         "type": "moasje", "number": "3", "date": "2026-05-06"},
        {"title": "07 Moasje 19 - Geen verhuisdruk voor onze ouderen - PVV en Steatelid Van Dijk",
         "type": "moasje", "number": "7", "date": "2026-05-27"},
        {"title": "06 Amendemint 01 - Niet afvoeren toezegging 4208 - PvdA",
         "type": "amendemint", "number": "6", "date": "2026-05-27"},
        {"title": "05 Amendemint 01 - Knaken voor kerntaken - CDA en VVD",
         "type": "amendemint", "number": "5", "date": "2026-06-24"},
    ]

    def setUp(self):
        import collect
        self.match = collect.match_pdf_module_item

    def test_number_and_agenda(self):
        info = up.title_info("05Amendemint01-Knakenvoorkerntaken-CDA")
        self.assertEqual(self.match(info, "05Amendemint01-Knakenvoorkerntaken-CDA", self.RECS)["number"], "5")

    def test_revote_prefers_the_original_motion(self):
        t = "14b-Werstimming:PS6maaie2026,wurklistpunt03Moasje19-ledereen draagtbij aan hetoplossenvan het stikstofslot-GrienLinks,PvdAenSP"
        info = up.title_info(t)
        self.assertTrue(info["revote"])
        self.assertEqual(self.match(info, t, self.RECS)["date"], "2026-05-06")

    def test_same_day_first_vote(self):
        t = "07 Moasje 19-Geen verhuisdruk vooronze ouderen-PvVSteatelid VanDijk"
        self.assertEqual(self.match(up.title_info(t), t, self.RECS)["date"], "2026-05-27")

    def test_nothing_convincing(self):
        t = "07Moasje02-Woonfabrieken laten draaien-BBB"
        self.assertIsNone(self.match(up.title_info(t), t, self.RECS))


@unittest.skipIf(Image is None, "Pillow not installed")
class Grid(unittest.TestCase):
    def synthetic(self):
        """Two columns like the real display: col 1 JA21 (1 row) + PvdA (3 rows, one absent),
        col 2 BBB (4 rows, one abstain). Names drawn in black at the left like the original."""
        im = Image.new("RGB", (up.GRID_WIDTH, 800), "white")
        d = ImageDraw.Draw(im)
        boxes = []
        layout = [(58, 331, [("JA21", [GREEN]), ("PvdA", [RED, GREY, RED])]),
                  (348, 622, [("BBB", [GREEN, GREEN, YELLOW, GREEN])])]
        for x0, x1, blocks in layout:
            y = 140
            for name, rows in blocks:
                d.rectangle([x0, y, x1, y + up.ROW - 1], fill=DARK)
                d.text((x0 + 6, y + 6), name, fill="white")
                boxes.append({"x": x0 + 2, "y": y + 1, "y2": y + 30, "text": name})
                y += up.ROW
                for c in rows:
                    d.rectangle([x0, y, x1, y + up.ROW - 1], fill=c)
                    d.text((x0 + 6, y + 8), "A. Member", fill="black")
                    boxes.append({"x": x0 + 4, "y": y + 3, "y2": y + 28, "text": "A. Member"})
                    y += up.ROW
                y += 8   # small white gap between fracties, as in the original
        d.text((360, 700), "Voor: 4  Tegen: 2  Onthouding: 1", fill="black")
        boxes.append({"x": 360, "y": 695, "y2": 725, "text": "Voor: 4  Tegen: 2  Onthouding: 1"})
        boxes.append({"x": 60, "y": 35, "y2": 65, "text": "07Moasje01-Test-BBB"})
        return im, boxes

    def test_read_grid(self):
        im, boxes = self.synthetic()
        blocks = up.read_grid(im, boxes)
        self.assertEqual([(b["header"], b["rows"]) for b in blocks],
                         [("JA21", "F"), ("PvdA", "AXA"), ("BBB", "FFOF")])

    def test_read_page(self):
        im, boxes = self.synthetic()
        page = up.read_page(im, boxes, ["JA21", "PvdA", "BBB"])
        self.assertTrue(page["ok"], page["warning"])
        self.assertEqual(page["totals"], (4, 2, 1))
        self.assertEqual(page["votes"]["PvdA"], {"agree": 0, "disagree": 2, "abstain": 0, "absent": 1})
        self.assertEqual(page["votes"]["BBB"], {"agree": 3, "disagree": 0, "abstain": 1, "absent": 0})
        self.assertEqual(page["info"]["number"], "1")

    def test_totals_mismatch_rejects_page(self):
        im, boxes = self.synthetic()
        boxes[-2]["text"] = "Voor: 5  Tegen: 2  Onthouding: 1"
        page = up.read_page(im, boxes, ["JA21", "PvdA", "BBB"])
        self.assertFalse(page["ok"])
        self.assertIn("wijkt af", page["warning"])

    def test_unknown_fractie_rejects_page(self):
        im, boxes = self.synthetic()
        page = up.read_page(im, boxes, ["JA21", "PvdA"])
        self.assertFalse(page["ok"])
        self.assertIn("BBB", page["warning"])


if __name__ == "__main__":
    unittest.main()
