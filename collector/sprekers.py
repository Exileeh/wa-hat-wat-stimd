#!/usr/bin/env python3
"""Sprekers en transcripten van een plenaire vergadering (zie ../docs/sprekers.md).

Two things live in the portal page that `collect.py` already fetches for the voting breakdown:

  1. the griffie's **speaker index** — per agendapunt a <ul class="speakers_indexations"> with one
     <li class="speaker_index" id="si_<n>" data-speaker_id data-start_offset data-end_offset> per
     spreekmoment, whose button text reads "spreker: Naam (fractie of rol)". Maintained by hand, so
     it is reliable; it covers the whole meeting without gaps.
  2. the JW Player config, which names an **.srt subtitle file** per meeting. That one is automatic
     speech recognition of wildly varying quality — good enough to search in, not to quote from
     without checking the video.

A cue timestamp falls inside exactly one spreekmoment, so "who said this" is an interval lookup.
That join is left to the browser (it has both arrays), which keeps the shipped file small: the
speaker id is not repeated on every one of the ~7.500 cues.

Stdlib only, and no import of `collect` — `party_slug` is passed in, so this module stays testable
on its own.
"""

import html as _html
import json
import re

# The labels in brackets that are a role rather than a fractie. Everything else goes through
# party_slug() and lands in a voting column. Compared lower-case.
ROLES = {
    "voorzitter",
    "plaatsvervangend voorzitter",
    "gedeputeerde",
    "commissaris van de koning",
    "griffier",
    "statengriffier",
}

# <li class="speaker_index js_only" id="si_32544285" data-si_id="…" data-speaker_id="…"
#     data-start_offset="1" data-end_offset="90"> … <span class="icon-user">spreker: </span>NAAM
# Attribute order is not guaranteed, so the tag is matched first and picked apart afterwards.
_LI = re.compile(r'<li\b([^>]*\bclass="[^"]*\bspeaker_index\b[^"]*"[^>]*)>(.*?)(?:<span class="item_time"|</li>)',
                 re.S | re.I)
_NAME = re.compile(r'spreker:\s*</span>(.*?)$', re.S | re.I)
_SUBTITLES = re.compile(r'subtitles_file\s*:\s*"([^"]+\.srt)"', re.I)
_TRAILING_ROLE = re.compile(r'\(([^()]*)\)\s*$')


def _attr(tag, name):
    m = re.search(r'\b%s="([^"]*)"' % re.escape(name), tag)
    return m.group(1) if m else None


def _text(fragment):
    """Tag-free, entity-decoded, whitespace-collapsed text."""
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]*>", " ", fragment))).strip()


def split_label(who):
    """"Keurs, E.J. (Eric) ter (VVD)" -> ("Keurs, E.J. (Eric) ter", "VVD").

    Only the *trailing* bracketed group counts, so a first name in brackets survives."""
    m = _TRAILING_ROLE.search(who)
    if not m:
        return who.strip(), None
    return who[:m.start()].strip(), m.group(1).strip()


def is_role(label):
    return bool(label) and label.lower() in ROLES


def parse_indexations(page_html):
    """[{start, end, speaker_id, si_id, name, label}] for every spreekmoment, sorted by start.

    `label` is the bracketed fractie or role, verbatim; the caller decides what it means."""
    out = []
    for tag, body in _LI.findall(page_html or ""):
        start, end = _attr(tag, "data-start_offset"), _attr(tag, "data-end_offset")
        sid = _attr(tag, "data-speaker_id")
        if start is None or end is None or not sid:
            continue
        try:
            start, end = int(start), int(end)
        except ValueError:
            continue
        if end < start:
            continue
        m = _NAME.search(body)
        name, label = split_label(_text(m.group(1)) if m else "")
        si = _attr(tag, "data-si_id") or (_attr(tag, "id") or "").removeprefix("si_")
        out.append({"start": start, "end": end, "speaker_id": sid,
                    "si_id": int(si) if (si or "").isdigit() else None,
                    "name": name, "label": label})
    out.sort(key=lambda r: (r["start"], r["end"]))
    return out


def subtitle_url(page_html):
    """The .srt named in the player config, or None. `subtitles_file : null` (the live stream) is
    skipped by requiring a quoted value."""
    m = _SUBTITLES.search(page_html or "")
    return m.group(1) if m else None


def _seconds(stamp):
    h, m, rest = stamp.split(":")
    s, _, ms = rest.partition(",")
    return int(h) * 3600 + int(m) * 60 + int(s)


_CUE = re.compile(r"(\d\d:\d\d:\d\d,\d+)\s*-->\s*(\d\d:\d\d:\d\d,\d+)\s*\n(.*)", re.S)


def parse_srt(text):
    """[(start_seconds, text)] — one entry per cue, its line breaks collapsed to spaces."""
    out = []
    for block in re.split(r"\r?\n\s*\r?\n", (text or "").replace("\r\n", "\n")):
        m = _CUE.search(block)
        if not m:
            continue
        line = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", m.group(3))).strip()
        if line:
            out.append((_seconds(m.group(1)), line))
    out.sort(key=lambda c: c[0])
    return out


def aggregate(index, party_slug):
    """Seconds spoken per fractie and per role, plus the span the index covers.

    Fracties and roles are kept apart on purpose: the gedeputeerde alone is good for a fifth of the
    speaking time and would otherwise dwarf every fractie in the chart."""
    fracties, rollen, unknown = {}, {}, set()
    for r in index:
        secs = max(0, r["end"] - r["start"])
        label = r["label"]
        if not label:
            unknown.add(r["name"] or "?")
            continue
        if is_role(label):
            rollen[label.lower()] = rollen.get(label.lower(), 0) + secs
            continue
        slug = party_slug(label)
        if not slug:
            unknown.add(label)
            continue
        fracties[slug] = fracties.get(slug, 0) + secs
    return {
        "indexed": max((r["end"] for r in index), default=0),
        "momenten": len(index),
        "fracties": dict(sorted(fracties.items(), key=lambda kv: -kv[1])),
        "rollen": dict(sorted(rollen.items(), key=lambda kv: -kv[1])),
        "unknown": sorted(unknown),
    }


def coverage(cues, index):
    """How many cues fall inside a spreekmoment — a health check for the log, not shipped data."""
    if not cues:
        return 0, 0
    spans = [(r["start"], r["end"]) for r in index]
    hit, i = 0, 0
    for t, _ in cues:
        while i + 1 < len(spans) and spans[i][1] < t:
            i += 1
        if i < len(spans) and spans[i][0] <= t <= spans[i][1]:
            hit += 1
    return hit, len(cues)


def transcript_doc(mid, source, srt, index, cues, party_slug):
    """The per-meeting file the site lazy-loads. Speaker and si_id are looked up in `index` by the
    browser, so a cue carries nothing but its time and its text."""
    speakers = {}
    for r in index:
        if r["speaker_id"] in speakers:
            continue
        label = r["label"]
        speakers[r["speaker_id"]] = {
            "n": r["name"],
            "p": None if (not label or is_role(label)) else party_slug(label),
            "r": label.lower() if is_role(label) else None,
        }
    return {
        "meetingId": mid,
        "source": source,
        "srt": srt,
        "speakers": speakers,
        "index": [[r["start"], r["end"], r["speaker_id"], r["si_id"]] for r in index],
        "cues": [[t, x] for t, x in cues],
    }


def write_transcript(path, doc):
    """Compact JSON: these files are ~600 KB and are never read by hand."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
