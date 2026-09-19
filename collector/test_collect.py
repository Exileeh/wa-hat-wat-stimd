"""Unit tests for the pure helpers of collect.py (no network).

    python -m unittest discover -s collector
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402


class Classify(unittest.TestCase):
    def test_frjemd_wins_over_voting_type(self):
        self.assertEqual(collect.notubiz_classify("Moasje frjemd PVV oer 'Friese vuist'", "motion"), "frjemd")
        self.assertEqual(collect.notubiz_classify("Moasje frjemd FNP oer Stop sintralisaasje", "council_proposal"), "frjemd")
        self.assertEqual(collect.notubiz_classify("10 Moasje Fremd - Underhâld rykswegen", None), "frjemd")

    def test_plain_types(self):
        self.assertEqual(collect.notubiz_classify("Moasje 9 (CDA): Each foar predatoaren", "motion"), "motie")
        self.assertEqual(collect.notubiz_classify("Amendemint 2: Geen spaarpot", "amendment"), "amendement")
        self.assertEqual(collect.notubiz_classify("Untwerp Fryske Oanpak - Finale beslút", "council_proposal"), "besluit")
        self.assertEqual(collect.notubiz_classify("Moasje 3: Moasje frjemd is een woord in de titel", "motion"), "motie")


class Parties(unittest.TestCase):
    def test_van_dijk_and_fvd_merge(self):
        self.assertEqual(collect.party_slug("FVD"), "van-dijk-fvd")
        self.assertEqual(collect.party_slug("Steatelid Van Dijk"), "van-dijk-fvd")
        self.assertEqual(collect.NOTUBIZ_ALIASES["FVD"], "Van Dijk (FvD)")

    def test_other_parties_untouched(self):
        self.assertEqual(collect.party_slug("Steatelid Jonker"), "steatelid-jonker")
        self.assertEqual(collect.party_slug("Partij voor de Dieren"), "pvdd")
        self.assertIsNone(collect.party_slug("Geen partij"))


class ModuleMatching(unittest.TestCase):
    def test_type_matches(self):
        self.assertTrue(collect.module_type_matches("moasje frjemd", "frjemd"))
        self.assertTrue(collect.module_type_matches("moasje", "frjemd"))       # module is inconsistent
        self.assertTrue(collect.module_type_matches("moasje frjemd", "motie"))
        self.assertFalse(collect.module_type_matches("amendemint", "frjemd"))
        self.assertTrue(collect.module_type_matches("amendemint", "amendement"))

    def test_frjemd_prefers_frjemd_records(self):
        plain = {"title": "Moasje 4 (PVV): Friese vuist voor koopkrachtherstel", "type": "moasje", "number": "4"}
        frjemd = {"title": "Moasje frjemd PVV oer 'Friese vuist voor koopkrachtherstel'", "type": "moasje frjemd", "number": ""}
        rec = collect.match_module_item("Moasje frjemd PVV oer 'Friese vuist voor koopkrachtherstel'", "frjemd", [plain, frjemd])
        self.assertIs(rec, frjemd)


class MeetingDetail(unittest.TestCase):
    FIXTURE = {"meeting": {"agenda_items": [
        {"id": 1, "type_data": {"title_prefix": "1", "attributes": [{"id": 1, "value": "Iepening"}]},
         "documents": [], "agenda_items": []},
        {"id": 2, "type_data": {"title_prefix": "2a", "attributes": [{"id": 1, "value": "Frageoerke"}]},
         "documents": [], "agenda_items": []},
        {"id": 3, "type_data": {"title_prefix": None, "attributes": []}, "documents": [], "agenda_items": [
            {"id": 30, "type_data": {"title_prefix": "3", "attributes": [{"id": 1, "value": "Untwerp  Fryske Oanpak"}]},
             "documents": [], "agenda_items": [
                 {"id": 300, "type_data": {}, "documents": [], "agenda_items": []}]},
        ]},
        {"id": 4, "type_data": {"title_prefix": "4", "attributes": [{"id": 1, "value": "Stimming"}]},
         "documents": [{"id": 99, "title": "Útslach stimming 17 juny 2026"}], "agenda_items": []},
    ]}}

    def test_walk(self):
        orig = collect.try_json
        collect.try_json = lambda url: self.FIXTURE
        try:
            doc, titles, by_id = collect.notubiz_meeting_detail(123)
        finally:
            collect.try_json = orig
        self.assertEqual(doc, {"id": 99, "title": "Útslach stimming 17 juny 2026"})
        self.assertEqual(titles, {1: "Iepening", 3: "Untwerp Fryske Oanpak", 4: "Stimming"})
        self.assertEqual(by_id[2], {"nr": "2a", "title": "Frageoerke"})
        self.assertEqual(by_id[30], {"nr": "3", "title": "Untwerp Fryske Oanpak"})
        self.assertNotIn(300, by_id)   # a voting node, not an agenda point
        self.assertNotIn(3, by_id)     # section header without number or title

    def test_agenda_for_number(self):
        by_id = {30: {"nr": "3", "title": "Untwerp"}, 41: {"nr": "10", "title": "Moasje frjemd"}}
        self.assertEqual(collect.agenda_for_number(3, by_id), {"id": 30, "nr": "3", "title": "Untwerp"})
        self.assertEqual(collect.agenda_for_number(10, by_id)["id"], 41)
        self.assertIsNone(collect.agenda_for_number(7, by_id))
        self.assertIsNone(collect.agenda_for_number(None, by_id))


if __name__ == "__main__":
    unittest.main()
