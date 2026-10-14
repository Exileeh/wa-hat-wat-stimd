"""Tests for vergaderstukken.py (no network: the Notubiz answers are stubbed).

    python -m unittest discover -s collector
"""

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vergaderstukken as vs  # noqa: E402


def docx_bytes(text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


MEETING = {"meeting": {
    "id": 1501613,
    "gremium": {"name": "Steatekommisje"},
    "plannings": [{"start_date": "2026-10-21 13:00:00", "end_date": "2026-10-21 17:00:00"}],
    "attributes": [],
    "agenda_items": [
        {"id": 1, "type_data": {"title_prefix": "1", "attributes": [
            {"id": 1, "value": "Iepenjen en f&ecirc;ststellen fan 'e wurklist"}]}},
        {"id": 3, "type_data": {"title_prefix": "3", "attributes": [
            {"id": 1, "value": "Omjouwingsfisy, beweging 2"},
            {"id": 7, "label": "Eftergrûn", "value": "<p>Earste rigel</p><p>Twadde rigel</p>"}]},
         "documents": [{"id": 111, "title": "PS-stik POVI"}, {"id": 112, "title": "Bylage kaart"}],
         "agenda_items": [{"id": 31, "type_data": {"title_prefix": "3a", "attributes": [
             {"id": 1, "value": "Sub"}]}, "documents": [{"id": 113, "title": "Notysje"}]}]},
    ],
}}


class Parse(unittest.TestCase):
    def test_meeting_id(self):
        self.assertEqual(vs.meeting_id("1501613"), 1501613)
        self.assertEqual(vs.meeting_id("https://fryslan.notubiz.nl/vergadering/1501613"), 1501613)
        self.assertEqual(vs.meeting_id("https://fryslan.notubiz.nl/vergadering/1501613/Steatekommisje"), 1501613)
        with self.assertRaises(SystemExit):
            vs.meeting_id("https://fryslan.notubiz.nl/")

    def test_strip_html(self):
        self.assertEqual(vs.strip_html("<p>a&amp;b</p><ul><li>x</li></ul>"), "a&b\n- x")

    def test_text_of(self):
        self.assertEqual(vs.text_of(docx_bytes("Hallo"))[0], "Hallo")
        self.assertEqual(vs.text_of(b"<html>")[1], "onbekend bestandstype")


class Run(unittest.TestCase):
    def test_writes_agenda_and_texts(self):
        files = {111: docx_bytes("Beslútpunten"), 112: b"\x89PNG", 113: None}

        def fake_bytes(url):
            for did, data in files.items():
                if f"/document/{did}/" in url:
                    return data
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(vs.collect, "try_json", return_value=MEETING), \
                mock.patch.object(vs.collect, "try_bytes", side_effect=fake_bytes), \
                mock.patch.object(vs.collect, "SLEEP", 0):
            self.assertEqual(vs.run(1501613, Path(tmp)), 0)
            out = Path(tmp) / "1501613"
            agenda = (out / "agenda.md").read_text("utf-8")
            self.assertIn("**1 Iepenjen en fêststellen fan 'e wurklist**", agenda)
            self.assertIn("_Eftergrûn:_ Earste rigel", agenda)
            self.assertIn("→ `01-PS-stik_POVI.txt`", agenda)
            self.assertIn("Bylage kaart — onbekend bestandstype", agenda)
            self.assertIn("**3a Sub**", agenda)
            self.assertIn("Notysje — NIET OPGEHAALD", agenda)
            self.assertIn("Beslútpunten", (out / "01-PS-stik_POVI.txt").read_text("utf-8"))
            self.assertTrue((out / "meeting.json").exists())

    def test_meeting_not_found(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(vs.collect, "try_json", return_value=None):
            self.assertEqual(vs.run(1, Path(tmp)), 1)


if __name__ == "__main__":
    unittest.main()
