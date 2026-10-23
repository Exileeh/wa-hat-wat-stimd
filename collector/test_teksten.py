"""Unit tests for collector/teksten.py (no network).

    python -m unittest discover -s collector
"""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import teksten  # noqa: E402

URL = "https://fryslan.notubiz.nl/document/{}/1/Moasje"


def pdf_with_text(text):
    """A one-page PDF whose text layer holds `text` (built with pypdf, no other dependency)."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    w = PdfWriter()
    page = w.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
    lines = "".join(f"({ln}) Tj T* " for ln in text.split("\n"))
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 11 Tf 14 TL 50 800 Td {lines}ET".encode("latin-1"))
    page[NameObject("/Contents")] = w._add_object(stream)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


class Helpers(unittest.TestCase):
    def test_doc_id(self):
        self.assertEqual(teksten.doc_id(URL.format(17486774)), "17486774")
        self.assertIsNone(teksten.doc_id(None))
        self.assertIsNone(teksten.doc_id("https://fryslan.notubiz.nl/vergadering/1"))

    def test_clean_rejoins_hyphenated_words(self):
        self.assertEqual(teksten.clean("de stikstof-\n uitstoot  van\n\nboeren"), "de stikstofuitstoot van boeren")
        self.assertEqual(teksten.clean("D66-\nFractie"), "D66- Fractie")   # capital: a real hyphen

    def test_clean_caps_length(self):
        self.assertEqual(len(teksten.clean("a " * 40000)), teksten.MAX_CHARS)


@unittest.skipUnless(teksten.available(), "pypdf not installed")
class Update(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "teksten.json"
        self.calls = []
        self.pdfs = {
            "1": pdf_with_text("Provinciale Staten verzoeken het college\nde stikstof-\nuitstoot te halveren."),
            "2": pdf_with_text(""),   # no text layer
        }

    def tearDown(self):
        self.dir.cleanup()

    def fetch(self, url):
        self.calls.append(url)
        return self.pdfs.get(teksten.doc_id(url))

    def run_update(self, moties, **kw):
        return teksten.update(moties, self.path, self.fetch, sleep=0, log=lambda *_: None, **kw)

    def test_first_run_and_incremental(self):
        moties = [{"document": URL.format(i)} for i in ("1", "2", "3")]   # 3 cannot be fetched
        self.assertEqual(self.run_update(moties), (1, 1, 1, 0))
        j = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("stikstofuitstoot te halveren", j["docs"]["1"])
        self.assertEqual(j["noText"], ["2"])

        self.calls.clear()
        self.run_update(moties)
        self.assertEqual(self.calls, [URL.format(3)])   # only the one that failed is retried

    def test_dropped_documents_are_pruned(self):
        self.run_update([{"document": URL.format(1)}, {"document": URL.format(2)}])
        self.run_update([{"document": URL.format(1)}])
        j = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(list(j["docs"]), ["1"])
        self.assertEqual(j["noText"], [])

    def test_budget_stops_cleanly(self):
        moties = [{"document": URL.format(i)} for i in ("1", "2")]
        self.assertEqual(self.run_update(moties, budget=-1), (0, 0, 0, 2))
        self.assertTrue(self.path.exists())


if __name__ == "__main__":
    unittest.main()
