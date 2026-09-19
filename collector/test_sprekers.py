#!/usr/bin/env python3
"""Tests for sprekers.py — run with `python -m unittest discover -s collector`.

Network-free: every fixture is a trimmed copy of what the portal really serves.
"""

import unittest

import sprekers

# Two spreekmomenten as the portal writes them: attributes spread over several lines, the name
# separated from the bracketed fractie by a pile of tabs, and a first name in brackets that must
# not be mistaken for the fractie.
PAGE = """
<ul class="speakers_indexations">
    <li class="speaker_index js_only" id="si_32544285"
    data-si_id="32544285" data-speaker_id="138027"
    data-start_offset="1"
    data-end_offset="90">
    <button>
        <span class="icon-user">spreker: </span>Brok, A.A.M.\t\t\t(commissaris van de Koning)
            <span class="item_time">
            <time datetime="PT00H01M29S">00:01:29</time>
    </button>
    </li>
    <li class="speaker_index js_only" id="si_32544312"
    data-si_id="32544312" data-speaker_id="238518"
    data-start_offset="675"
    data-end_offset="813">
    <button>
        <span class="icon-user">spreker: </span>Keurs, E.J. (Eric) ter\t(VVD)
            <span class="item_time">
    </button>
    </li>
</ul>
"""

SRT = """1
00:00:00,000 --> 00:00:02,600
Ik...

2
00:00:02,680 --> 00:00:05,679
iepenje de steategearkomste
fan acht en tweintich.

3
00:11:15,000 --> 00:11:18,000
en dat is kalk inzetten.
"""

# Stand-in for collect.party_slug, including the alias the real one applies.
ALIASES = {"Partij voor de Dieren": "pvdd", "Steatelid Van Dijk": "van-dijk-fvd"}
SKIP = {"Geen partij", "Gedeputeerde Staten"}


def party_slug(name):
    if name in SKIP:
        return None
    if name in ALIASES:
        return ALIASES[name]
    return name.lower().replace(" ", "-")


class Indexations(unittest.TestCase):
    def test_parses_both(self):
        rows = sprekers.parse_indexations(PAGE)
        self.assertEqual(len(rows), 2)

    def test_fields(self):
        first = sprekers.parse_indexations(PAGE)[0]
        self.assertEqual(first["start"], 1)
        self.assertEqual(first["end"], 90)
        self.assertEqual(first["speaker_id"], "138027")
        self.assertEqual(first["si_id"], 32544285)
        self.assertEqual(first["name"], "Brok, A.A.M.")
        self.assertEqual(first["label"], "commissaris van de Koning")

    def test_bracketed_first_name_is_not_the_fractie(self):
        second = sprekers.parse_indexations(PAGE)[1]
        self.assertEqual(second["name"], "Keurs, E.J. (Eric) ter")
        self.assertEqual(second["label"], "VVD")

    def test_sorted_by_start(self):
        rows = sprekers.parse_indexations(PAGE)
        self.assertEqual([r["start"] for r in rows], [1, 675])

    def test_empty_page(self):
        self.assertEqual(sprekers.parse_indexations(""), [])


class Roles(unittest.TestCase):
    def test_role_labels(self):
        for label in ("voorzitter", "Gedeputeerde", "commissaris van de Koning"):
            self.assertTrue(sprekers.is_role(label), label)

    def test_fractie_is_not_a_role(self):
        for label in ("VVD", "BBB", "Partij voor de Dieren", "Steatelid Van Dijk"):
            self.assertFalse(sprekers.is_role(label), label)


class Subtitles(unittest.TestCase):
    def test_finds_the_url(self):
        page = 'streamname: "x", subtitles_file: "https://host/media/subtitles/a_b.srt",'
        self.assertEqual(sprekers.subtitle_url(page), "https://host/media/subtitles/a_b.srt")

    def test_skips_the_live_null(self):
        self.assertIsNone(sprekers.subtitle_url("subtitles_file : null,"))

    def test_first_real_url_wins(self):
        page = ('subtitles_file : null,\n'
                'subtitles_file: "https://host/media/subtitles/real.srt",')
        self.assertEqual(sprekers.subtitle_url(page), "https://host/media/subtitles/real.srt")

    def test_none_when_absent(self):
        self.assertIsNone(sprekers.subtitle_url("<html></html>"))


class Srt(unittest.TestCase):
    def test_times_and_text(self):
        cues = sprekers.parse_srt(SRT)
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0], (0, "Ik..."))
        self.assertEqual(cues[2][0], 11 * 60 + 15)

    def test_two_line_cue_is_joined(self):
        self.assertEqual(sprekers.parse_srt(SRT)[1][1],
                         "iepenje de steategearkomste fan acht en tweintich.")

    def test_crlf(self):
        self.assertEqual(len(sprekers.parse_srt(SRT.replace("\n", "\r\n"))), 3)

    def test_empty(self):
        self.assertEqual(sprekers.parse_srt(""), [])


class Coverage(unittest.TestCase):
    index = [{"start": 0, "end": 10}, {"start": 20, "end": 30}]

    def test_boundaries_count(self):
        hit, total = sprekers.coverage([(0, "a"), (10, "b"), (30, "c")], self.index)
        self.assertEqual((hit, total), (3, 3))

    def test_cue_in_a_gap_does_not(self):
        hit, total = sprekers.coverage([(15, "x")], self.index)
        self.assertEqual((hit, total), (0, 1))


class Aggregate(unittest.TestCase):
    def rows(self):
        return [
            {"start": 0, "end": 100, "label": "Partij voor de Dieren", "name": "A",
             "speaker_id": "1", "si_id": 1},
            {"start": 100, "end": 150, "label": "VVD", "name": "B", "speaker_id": "2", "si_id": 2},
            {"start": 150, "end": 400, "label": "gedeputeerde", "name": "C",
             "speaker_id": "3", "si_id": 3},
        ]

    def test_alias_is_applied(self):
        agg = sprekers.aggregate(self.rows(), party_slug)
        self.assertEqual(agg["fracties"]["pvdd"], 100)

    def test_role_stays_out_of_the_fracties(self):
        agg = sprekers.aggregate(self.rows(), party_slug)
        self.assertNotIn("gedeputeerde", agg["fracties"])
        self.assertEqual(agg["rollen"]["gedeputeerde"], 250)

    def test_span_and_count(self):
        agg = sprekers.aggregate(self.rows(), party_slug)
        self.assertEqual(agg["indexed"], 400)
        self.assertEqual(agg["momenten"], 3)

    def test_fracties_sorted_by_time(self):
        agg = sprekers.aggregate(self.rows(), party_slug)
        self.assertEqual(list(agg["fracties"]), ["pvdd", "vvd"])

    def test_skipped_label_is_reported_not_counted(self):
        rows = [{"start": 0, "end": 10, "label": "Geen partij", "name": "X",
                 "speaker_id": "9", "si_id": 9}]
        agg = sprekers.aggregate(rows, party_slug)
        self.assertEqual(agg["fracties"], {})
        self.assertEqual(agg["unknown"], ["Geen partij"])


class TranscriptDoc(unittest.TestCase):
    def doc(self):
        index = sprekers.parse_indexations(PAGE)
        cues = sprekers.parse_srt(SRT)
        return sprekers.transcript_doc(7, "https://host/vergadering/7", "https://host/a.srt",
                                       index, cues, party_slug)

    def test_shape(self):
        d = self.doc()
        self.assertEqual(d["meetingId"], 7)
        self.assertEqual(d["index"][1], [675, 813, "238518", 32544312])
        self.assertEqual(d["cues"][0], [0, "Ik..."])

    def test_speaker_party_and_role(self):
        sp = self.doc()["speakers"]
        self.assertEqual(sp["238518"]["p"], "vvd")
        self.assertIsNone(sp["238518"]["r"])
        self.assertIsNone(sp["138027"]["p"])
        self.assertEqual(sp["138027"]["r"], "commissaris van de koning")


if __name__ == "__main__":
    unittest.main()
