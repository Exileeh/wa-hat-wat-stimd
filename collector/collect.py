#!/usr/bin/env python3
"""
Collector — Provinciale Staten voting overview.

Pulls per-party voting records per scope, unions them into one motie list, and writes a
normalized data/<scope>.json that the static site reads, plus a data/catalog.json index that
groups scopes by category (Tweede Kamer / Provinciale Staten) for the "pick category -> scope" UX.

Multi-vendor / multi-category: each entry in SOURCES names a `vendor`, dispatched to an adapter
in ADAPTERS (go = GemeenteOplossingen, ibabs, tk = Tweede Kamer OData). Each entry also names a
`category` (legislative body): "provinciale-staten" (the provinces) or "tweede-kamer". The site is
organized as categories -> scopes; main() writes one data/<key>.json per scope plus a
data/catalog.json index grouping scopes by category. See ../provinces.md and ../data-sources.md.

Zero dependencies (stdlib only) so GitHub Actions needs no install step.
See ../data-sources.md for the reverse-engineered GO endpoints.
"""

import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --- Source registry ----------------------------------------------------------
# Each entry: key, name, vendor, category, base, term_start (y,m,d), term_label, style, license.
# `category` defaults to "provinciale-staten"; the Tweede Kamer entry sets "tweede-kamer".
# Add a source here once its vendor adapter exists (see ../provinces.md + ../data-sources.md).
SOURCES = [
    {
        "key": "utrecht",
        "name": "Utrecht",
        "vendor": "go",
        "base": "https://www.stateninformatie.provincie-utrecht.nl",
        "term_start": (2023, 3, 29),   # PS election 29 March 2023
        "term_label": "2023-2027",
        "style": {"accent": "#EC0000", "headerBg": "#1b1b1b"},
        "license": "Open data - Provincie Utrecht / Statengriffie",
    },
    {
        "key": "drenthe",
        "name": "Drenthe",
        "vendor": "go",
        "base": "https://www.drentsparlement.nl",
        # Same GemeenteOplossingen stack as Utrecht, but this install routes the per-fractie
        # votings page via /Leden/{slug}/votings instead of /Samenstelling/... The Statengriffie
        # had GO enable/locate the stemgedrag data after outreach (bevestigd 2026-06-30).
        "votings_path": "Leden",
        "term_start": (2023, 3, 29),   # PS election 29 March 2023
        "term_label": "2023-2027",
        "style": {"accent": "#76b82a", "headerBg": "#16321a"},   # Drenthe huisstijlgroen
        "license": "Open data - Provincie Drenthe / Statengriffie (Drents Parlement)",
    },
    {
        "key": "noord-holland",
        "name": "Noord-Holland",
        "vendor": "ibabs",
        "base": "https://noordholland.bestuurlijkeinformatie.nl",
        # One or more iBabs reports (GET /Reports lists them). These registers track *adopted*
        # items only; verworpen moties/amendementen aren't published here in structured form.
        "reports": [
            {"guid": "84a8ac43-1424-48a9-8a1a-0c0bbcdfd8ed", "type": "motie"},
            {"guid": "95a2053b-5dd6-4aa4-9e60-fdf5158fc48f", "type": "amendement"},
        ],
        "term_start": (2023, 3, 29),   # PS election 15 March 2023
        "term_label": "2023-2027",
        "style": {"accent": "#2891e0", "headerBg": "#0e2438"},   # NH portal huisstijl blue
        "license": "Open data - Provincie Noord-Holland (iBabs publieksportaal)",
        # iBabs scope: these registers list adopted items only, and votes are recorded per
        # fractie (not per member), so "ruwe getallen" show 1–0 rather than seat counts.
        "note": "De bron (iBabs-registers) bevat alleen aangenomen moties en amendementen; "
                "stemmen zijn op fractieniveau geregistreerd, dus zonder exacte aantallen per fractie.",
    },
    {
        "key": "limburg",
        "name": "Limburg",
        "vendor": "ibabs",
        "votes": "stemmen",   # structured per-fractie member counts (not NH's free text)
        "base": "https://limburg.bestuurlijkeinformatie.nl",
        "reports": [
            {"guid": "0493fdd4-4d92-45b7-9645-64a5cb38e1dd", "type": "motie"},
            {"guid": "34a4e0ce-064b-4457-9acb-8e89a2a93019", "type": "amendement"},
        ],
        "term_start": (2023, 3, 29),
        "term_label": "2023-2027",
        "style": {"accent": "#0059a2", "headerBg": "#0a2540"},   # Limburg portal huisstijl blue
        "license": "Open data - Provincie Limburg (iBabs publieksportaal)",
        # Richer than NH: includes verworpen moties/amendementen and exact per-fractie counts. Moties
        # zonder hoofdelijke stemming (bij acclamatie) hebben geen telling en worden overgeslagen.
        "note": "Stemmen zijn per fractie met aantallen geregistreerd (aangenomen én verworpen). "
                "Moties/amendementen zonder hoofdelijke stemming zijn niet opgenomen.",
    },
    {
        # Notubiz province. No token needed (data-sources.md §11): the public events + votings API
        # (version=1.21) discovers meetings + per-stemming metadata, and the public portal vergadering
        # page carries the per-fractie breakdown with EXACT member counts -> tier A. Reference province
        # for the vendor; the others differ only in organisation_id / gremium_id / slug.
        "key": "zuid-holland",
        "name": "Zuid-Holland",
        "vendor": "notubiz",
        "organisation_id": 3868,
        "gremium_id": 11157,           # the plenary "Provinciale Staten" gremium (commissies excluded)
        "slug": "pzh",                 # portal host: pzh.notubiz.nl
        "base": "https://api.notubiz.nl",
        "public": "https://pzh.notubiz.nl",   # the "Bron:" link points to the portal vergadering page
        "term_start": (2023, 3, 29),   # PS election 15 March 2023, geïnstalleerd 29 March
        "term_label": "2023-2027",
        "style": {"accent": "#a07400", "headerBg": "#221900"},   # Zuid-Holland huisstijl goud/geel
        "license": "Open data - Provincie Zuid-Holland (Notubiz vergaderportaal)",
        "note": "Stemmen zijn hoofdelijk (per lid) geregistreerd en hier per fractie met exacte "
                "aantallen samengevat (aangenomen én verworpen). Agendapunten zonder hoofdelijke "
                "stemming (bijv. bij acclamatie) en leden die niet deelnamen, staan niet in de telling.",
    },
    {
        "key": "fryslan",
        "name": "Fryslân",
        "vendor": "notubiz",
        "organisation_id": 822,
        "gremium_id": 430,             # "Provinsjale Steaten" (Fries) = the plenary gremium
        "slug": "fryslan",
        "base": "https://api.notubiz.nl",
        "public": "https://fryslan.notubiz.nl",
        "term_start": (2023, 3, 29),
        "term_label": "2023-2027",
        "style": {"accent": "#c8102e", "headerBg": "#2a0a0c"},   # Frysk read (pompeblêd-rood)
        "license": "Open data - Provincie Fryslân (Notubiz vergaderportaal)",
        "note": "Stemmen zijn hoofdelijk (per lid) geregistreerd en hier per fractie met exacte "
                "aantallen samengevat (aangenomen én verworpen). Agendapunten zonder hoofdelijke "
                "stemming (bijv. bij acclamatie) en leden die niet deelnamen, staan niet in de telling.",
    },
    {
        "key": "gelderland",
        "name": "Gelderland",
        "vendor": "notubiz",
        "organisation_id": 1769,
        "gremium_id": 2437,
        "slug": "gelderland",
        "base": "https://api.notubiz.nl",
        "public": "https://gelderland.notubiz.nl",
        "term_start": (2023, 3, 29),
        "term_label": "2023-2027",
        "style": {"accent": "#0d5eaf", "headerBg": "#08203d"},   # Gelderland huisstijl blauw
        "license": "Open data - Provincie Gelderland (Notubiz vergaderportaal)",
        "note": "Stemmen zijn hoofdelijk (per lid) geregistreerd en hier per fractie met exacte "
                "aantallen samengevat (aangenomen én verworpen). Agendapunten zonder hoofdelijke "
                "stemming (bijv. bij acclamatie) en leden die niet deelnamen, staan niet in de telling.",
    },
    {
        "key": "overijssel",
        "name": "Overijssel",
        "vendor": "notubiz",
        "organisation_id": 1750,
        "gremium_id": 2229,
        "slug": "overijssel",
        "base": "https://api.notubiz.nl",
        "public": "https://overijssel.notubiz.nl",
        "term_start": (2023, 3, 29),
        "term_label": "2023-2027",
        "style": {"accent": "#147ab3", "headerBg": "#0a2a3d"},   # Overijssel huisstijl blauw
        "license": "Open data - Provincie Overijssel (Notubiz vergaderportaal)",
        "note": "Stemmen zijn hoofdelijk (per lid) geregistreerd en hier per fractie met exacte "
                "aantallen samengevat (aangenomen én verworpen). Agendapunten zonder hoofdelijke "
                "stemming (bijv. bij acclamatie) en leden die niet deelnamen, staan niet in de telling.",
    },
    {
        # A second *category* (not a province): the national parliament. Clean OData v4 API with
        # per-fractie votes incl. seat counts -> tier A. See data-sources.md §8.
        "key": "tweede-kamer",
        "name": "Tweede Kamer",
        "vendor": "tk",
        "category": "tweede-kamer",
        "body": "Tweede Kamer",
        "base": "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0",
        "public": "https://www.tweedekamer.nl",   # human-facing site (per-item: /zoeken?qry={nummer})
        # Current term = Kamer installed after the 29 Oct 2025 election (constituerende verg. 12 Nov;
        # first stemming 13 Nov). Date-gating here drops old-composition votes cast before installation.
        "term_start": (2025, 11, 13),
        "term_label": "2025-heden",
        "style": {"accent": "#154273", "headerBg": "#0c1d33"},   # Rijkshuisstijl blue
        "license": "Open data - Tweede Kamer der Staten-Generaal (opendata.tweedekamer.nl)",
        "compact": True,   # ~3k stemmingen -> write minified JSON to keep the file ~3 MB
        "note": "Stemmen zijn per fractie met zetelaantallen geregistreerd (aangenomen én verworpen). "
                "Alleen stemmingen met een hoofdelijke of fractiegewijze telling; zaken die zonder "
                "stemming zijn afgedaan, aangehouden of ingetrokken zijn niet opgenomen.",
    },
    {
        # The Senate (revising chamber). Separate body, separate system — no machine API; the
        # per-fractie voor/tegen lists are parsed from the HTML "stemmingen per vergaderdag" pages.
        # Faction-level V/T, no seat counts -> tier B, but BOTH sides are named (nothing inferred).
        # See data-sources.md §9.
        "key": "eerste-kamer",
        "name": "Eerste Kamer",
        "vendor": "ek",
        "category": "eerste-kamer",
        "body": "Eerste Kamer",
        "base": "https://www.eerstekamer.nl",
        # Current EK installed 13 June 2023 (elected by the March 2023 Provinciale Staten). Note: the
        # EK term (2023-2027) differs from the TK term (2025-heden) — different election cycles.
        "term_start": (2023, 6, 13),
        "term_label": "2023-2027",
        "style": {"accent": "#00669a", "headerBg": "#0a2e44"},   # EK huisstijl blue
        "license": "Open data - Eerste Kamer der Staten-Generaal (eerstekamer.nl)",
        "note": "Stemmen zijn op fractieniveau geregistreerd (voor/tegen, zonder zetelaantallen): de "
                "Eerste Kamer stemt meestal bij zitten en opstaan. Beide zijden worden expliciet "
                "vermeld (niets afgeleid). Hamerstukken (zonder stemming aangenomen) zijn niet opgenomen.",
    },
    {
        # The EU's elected chamber. Votes presented by EUROPEAN POLITICAL GROUP (not Dutch MEPs only).
        # Source: HowTheyVote.eu compiles the EP's roll-call open data and exposes per-group MEP counts
        # (stats.by_group) -> exact tallies, tier A. See data-sources.md §10. ODbL license.
        "key": "europees-parlement",
        "name": "Europese fracties",
        "vendor": "ep",
        "category": "europees-parlement",
        "body": "Europees Parlement",
        "base": "https://howtheyvote.eu",
        # Current (10th) term: first sitting after the June 2024 election. (Differs again from TK/EK.)
        "term_start": (2024, 7, 16),
        "term_label": "2024-2029",
        "style": {"accent": "#003399", "headerBg": "#041f4a"},   # EU flag blue
        "sourceName": "HowTheyVote.eu",   # ODbL attribution — the "Bron:" link points here, not the EP
        "license": "Open data - HowTheyVote.eu (ODbL 1.0) op basis van hoofdelijke stemmingen "
                   "(roll-call) van het Europees Parlement",
        "note": "Stemmen per Europese fractie met exacte aantallen (voor/tegen/onthouding), op basis "
                "van hoofdelijke stemmingen (roll-call). Alleen eindstemmingen; stemmingen bij "
                "handopsteken worden niet hoofdelijk geregistreerd. Bron: HowTheyVote.eu (ODbL), "
                "Europees Parlement.",
    },
    {
        # Second view of the same EP votes: the Dutch delegation, grouped by NATIONAL party (PVV,
        # GL-PvdA, VVD, …) instead of by European group. Shares ep_load's cached details (no extra
        # fetch). Columns carry a `members` roster (the MEP names) for the frontend.
        "key": "europees-parlement-nl",
        "name": "Nederlandse afvaardiging",
        "vendor": "ep",
        "breakout": "nl",
        "category": "europees-parlement",
        "body": "Europees Parlement",
        "base": "https://howtheyvote.eu",
        "term_start": (2024, 7, 16),
        "term_label": "2024-2029",
        "style": {"accent": "#003399", "headerBg": "#041f4a"},
        "sourceName": "HowTheyVote.eu",
        "license": "Open data - HowTheyVote.eu (ODbL 1.0) op basis van hoofdelijke stemmingen "
                   "(roll-call) van het Europees Parlement",
        "note": "De 31 Nederlandse Europarlementariërs, gegroepeerd per Nederlandse partij, met "
                "exacte aantallen (voor/tegen/onthouding). Alleen hoofdelijke eindstemmingen. "
                "Bron: HowTheyVote.eu (ODbL) + Europees Parlement Open Data (fractie-indeling).",
    },
]

# Categories (legislative bodies) -> how the frontend labels the "pick category -> pick scope" UX.
# scope_noun is the word for one scope ("provincie"); None when the category is a single body (TK).
CATEGORY_META = {
    "provinciale-staten": {"name": "Provinciale Staten", "scope_noun": "provincie",
                           "blurb": "Stemgedrag in de 12 provinciale staten — kies een provincie."},
    "tweede-kamer": {"name": "Tweede Kamer", "scope_noun": None,
                     "blurb": "Het landelijke parlement — moties, amendementen en wetsvoorstellen."},
    "eerste-kamer": {"name": "Eerste Kamer", "scope_noun": None,
                     "blurb": "De senaat — stemmingen over wetsvoorstellen en moties (op fractieniveau)."},
    "europees-parlement": {"name": "Europees Parlement", "scope_noun": "weergave",
                           "blurb": "Het EU-parlement — per Europese fractie, of de Nederlandse afvaardiging."},
}
# Landing order: national (TK, EK) -> regional (provinces) -> EU (Europees Parlement).
CATEGORY_ORDER = ["tweede-kamer", "eerste-kamer", "provinciale-staten", "europees-parlement"]

# Bodies that are type "Fractie" in the GO API but are not voting parties.
NOT_A_PARTY = {"Gedeputeerde Staten"}

HEADERS = {
    "User-Agent": "wie-stemde-wat collector (open-data overview; contact via GitHub)",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}
SLEEP = 0.3  # be polite between requests


def http(url, data=None, ctype=None):
    """GET, or POST when `data` (a form string) is given. Returns the decoded body."""
    headers = dict(HEADERS)
    if ctype:
        headers["Content-Type"] = ctype
    body = data.encode("utf-8") if isinstance(data, str) else data
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def fetch(url, data=None, ctype=None, tries=3):
    """http() with retries on transient errors. Returns the body, or None on a 4xx/5xx or after
    `tries` failed attempts. A 30s read timeout over hundreds of pages is normal for a weekly
    run, so retry the non-HTTP failures (timeouts, dropped connections) instead of crashing."""
    for attempt in range(tries):
        try:
            return http(url, data=data, ctype=ctype)
        except urllib.error.HTTPError:
            return None   # 4xx/5xx — not worth retrying for our purposes
        except OSError:   # URLError, TimeoutError, dropped connections, …
            if attempt + 1 == tries:
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def try_json(url):
    """GET + JSON parse; None on any network/HTTP/JSON failure."""
    txt = fetch(url)
    try:
        return json.loads(txt) if txt is not None else None
    except json.JSONDecodeError:
        return None


def try_text(url):
    """GET returning text (HTML), tolerant of network/HTTP errors."""
    return fetch(url)


def post_json(url, body):
    """POST a form body and parse the JSON response; None on failure."""
    txt = fetch(url, data=body, ctype="application/x-www-form-urlencoded")
    try:
        return json.loads(txt) if txt is not None else None
    except json.JSONDecodeError:
        return None


def slugify(name):
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)   # drop punctuation (e.g. "UtrechtNu!" -> "utrechtnu")
    s = re.sub(r"\s+", "-", s.strip())
    return s


def classify(title):
    """Two naming schemes exist: word form ("Motie 97", "Amendement 19") and code form
    ("M26-40a", "A26-12"). Handle both."""
    low = title.strip().lower()
    if "ordevoorstel" in low or "orde voorstel" in low:
        return "ordevoorstel"
    if "amendement" in low or re.match(r"^a\s*\d", low):
        return "amendement"
    if "motie" in low or re.match(r"^m\s*\d", low):
        return "motie"
    if (low.startswith("sv") or "statenstuk" in low or "statenvoorstel" in low
            or "besluit" in low):
        return "besluit"
    return "overig"


# --- GemeenteOplossingen (GO) adapter ----------------------------------------
def collect_go(p):
    """Return {parties, moties} for a GO province, or None if it has no votes endpoint."""
    base = p["base"].rstrip("/")
    api = base + "/api/v2"
    term_start = date(*p["term_start"])
    mcache = {}

    def meeting_date(mid):
        if mid in mcache:
            return mcache[mid]
        d = None
        data = try_json(f"{api}/meetings/{mid}")
        if data and data.get("result", {}).get("meeting"):
            d = data["result"]["meeting"].get("date")
        mcache[mid] = d
        time.sleep(SLEEP)
        return d

    gdata = try_json(f"{api}/groups?limit=100")
    if not gdata or "result" not in gdata:
        return None
    parties = [{"name": g["name"], "slug": slugify(g["name"]), "sortOrder": g.get("sortOrder", 999)}
               for g in gdata["result"]["groups"]
               if g.get("type") == "Fractie" and g["name"] not in NOT_A_PARTY]
    print(f"  candidate parties: {len(parties)}")

    # The per-fractie votings page lives under a portal-specific path segment. Utrecht (and the GO
    # default) exposes it at /Samenstelling/{slug}/votings; Drenthe's install routes it via
    # /Leden/{slug}/votings (confirmed by GemeenteOplossingen, 2026-06-30). Same JSON either way.
    vpath = p.get("votings_path", "Samenstelling")
    moties = {}
    parties_with_data = {}
    for party in parties:
        data = try_json(f"{base}/{vpath}/{party['slug']}/votings")
        time.sleep(SLEEP)
        items_by_year = data.get("items") if data else None
        if not isinstance(items_by_year, dict):   # empty result is [] not {}, or 404
            continue
        kept = 0
        for year, items in items_by_year.items():
            if int(year) < term_start.year:
                continue
            for it in items:
                mid = it["meetingId"]
                mdate = meeting_date(mid) or it.get("updatedAt", {}).get("date", "")[:10]
                try:
                    d = datetime.strptime(mdate[:10], "%Y-%m-%d").date()
                except ValueError:
                    continue
                if d < term_start:
                    continue
                vid = it["votingId"]
                if vid not in moties:
                    moties[vid] = {
                        "id": vid,
                        "documentId": it.get("documentId"),
                        "meetingItemId": it.get("meetingItemId"),
                        "meetingId": mid,
                        "date": mdate[:10],
                        "title": it["description"],
                        "type": classify(it["description"]),
                        "result": (it.get("voteResult") or {}).get("name"),
                        "resultLabel": (it.get("voteResult") or {}).get("label"),
                        # Human-facing page (301-redirects to the pretty agenda-item URL).
                        "source": (f"{base}/vergaderingen/document/{it['documentId']}" if it.get("documentId")
                                   else f"{base}/vergaderingen/agendapunt/{it['meetingItemId']}" if it.get("meetingItemId")
                                   else f"{base}/vergaderingen/{mid}"),
                        "votes": {},
                    }
                vc = (it.get("voteResult") or {}).get("voteCounts", {})
                moties[vid]["votes"][party["slug"]] = {
                    "agree": vc.get("agree", 0),
                    "disagree": vc.get("disagree", 0),
                    "abstain": vc.get("abstain", 0),
                }
                kept += 1
        if kept:
            parties_with_data[party["slug"]] = party

    motie_list = sorted(moties.values(), key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in motie_list:
        m["totals"] = {"agree": sum(v["agree"] for v in m["votes"].values()),
                       "disagree": sum(v["disagree"] for v in m["votes"].values())}
    columns = sorted(parties_with_data.values(), key=lambda x: x["sortOrder"])
    return {"parties": [{"slug": x["slug"], "name": x["name"]} for x in columns], "moties": motie_list}


# --- iBabs adapter ------------------------------------------------------------
# The iBabs publieksportaal ({prov}.bestuurlijkeinformatie.nl) is an ASP.NET SPA with a
# DataTables "Moties" report. Per-fractie votes are recoverable without auth (data-sources.md §7):
#   POST /Reports/GetReportData/{guid}  -> clean JSON motie list (DT_RowId, motienummer, ...)
#   GET  /Reports/Item/{DT_RowId}       -> server-rendered HTML; the "Stemverhouding" field
#                                          holds the per-fractie outcome as FREE TEXT, e.g.
#       "Tegen: VVD /BBB /JA21. Voor: overige fracties (Fractie De Weerdt afwezig)."
# Granularity is faction-level only (no member counts) -> store agree/disagree as 1/0; the
# frontend's "ruwe getallen"/split-vote features degrade gracefully for iBabs provinces.
#
# Parsing strategy: the losing side is usually named and the winning side is "overige fracties"
# (= everyone else). To expand "overige fracties" we need the term's party universe; we build it
# data-driven (pass 1: collect every explicitly-named fractie across all in-term moties), then
# resolve each motie (pass 2). Composition changes per term, so we term-scope first via "Datum PS".

# Normalize fractie spellings to one canonical display name. Keys are lowercased; multi-word
# keys let the greedy tokenizer split space-separated lists ("PVV FvD") without breaking
# multi-word party names ("Fractie De Weerdt"). Unknown tokens pass through verbatim, so the
# adapter also works for the other iBabs provinces (Limburg, Noord-Brabant, Zeeland).
IBABS_ALIASES = {
    "gl": "GroenLinks", "groenlinks": "GroenLinks", "groen links": "GroenLinks",
    "pvda": "PvdA", "partij van de arbeid": "PvdA",
    "pvdd": "PvdD", "partij voor de dieren": "PvdD",
    "cu": "ChristenUnie", "christenunie": "ChristenUnie", "christen unie": "ChristenUnie",
    "cda": "CDA", "d66": "D66", "vvd": "VVD", "bbb": "BBB", "sp": "SP",
    "pvv": "PVV", "ja21": "JA21", "ja 21": "JA21", "volt": "Volt",
    "fvd": "FvD", "forum voor democratie": "FvD",
    "50plus": "50PLUS", "50 plus": "50PLUS", "denk": "DENK", "sgp": "SGP",
    "fractie de weerdt": "Fractie De Weerdt", "de weerdt": "Fractie De Weerdt",
}
# A whole side phrased as these means "everyone present" (no opposing side).
IBABS_ALL = ("unaniem", "alle fracties", "alle partijen")
# Filler words to skip when splitting a space-separated list (label words / stopwords).
IBABS_SKIP = {"fractie", "fracties", "frct.", "frc.", "frct", "frc", "de", "en", "het"}


def ibabs_canon(token):
    """Canonical display name for one fractie token, or None if empty."""
    t = re.sub(r"\s+", " ", token or "").strip().strip(".,;:").strip()
    if not t or t.isdigit() or len(t) < 2:   # drop vote-count numerals / stray single chars
        return None
    low = t.lower()
    if low in IBABS_ALIASES:
        return IBABS_ALIASES[low]
    # strip a leading "fractie"/"frct." label (e.g. "fractie FvD" -> "FvD")
    m = re.match(r"(?:fracties?|frct\.?|frc\.?)\s+(.+)$", t, re.I)
    if m and m.group(1).strip().lower() != low:
        return ibabs_canon(m.group(1))
    return t


def ibabs_greedy(text):
    """Tokenize a space-separated side ("PVV FvD") into canonical names, longest-alias-first
    so multi-word names stay intact."""
    words = text.split()
    out, i = [], 0
    while i < len(words):
        hit = False
        for L in range(min(4, len(words) - i), 0, -1):
            cand = " ".join(words[i:i + L]).lower().strip(".,;:")
            if cand in IBABS_ALIASES:
                out.append(IBABS_ALIASES[cand]); i += L; hit = True; break
        if not hit:
            if words[i].lower().strip(".,;:") in IBABS_SKIP:
                i += 1; continue
            c = ibabs_canon(words[i])
            if c:
                out.append(c)
            i += 1
    return out


def ibabs_parties(text):
    """Parse one side's fractie list. Separators vary (',', '/', ' / ', ' en ', or just space)."""
    text = re.sub(r"\s+", " ", text or "").strip(" .")
    if not text:
        return []
    if "/" in text or "," in text:
        chunks = text.replace("/", ",").split(",")
        return [c for c in (ibabs_canon(x) for x in chunks) if c]
    if re.search(r"\sen\s", text, re.I):
        return [c for c in (ibabs_canon(x) for x in re.split(r"\sen\s", text, flags=re.I)) if c]
    return ibabs_greedy(text)


def ibabs_parse(raw):
    """Parse a Stemverhouding string into (voor_spec, tegen_spec, afwezig_set, split_set), or
    None when there is no usable vote (withdrawn/postponed/blank). Each *_spec is one of:
      ("list", {names}) | ("rest", None) | ("all", None) | None.
    The free text is messy: labels sometimes glue to a preceding name ("PvdAVoor:") and a
    "Verdeeld gestemd:" clause marks fracties that split their own vote."""
    t = re.sub(r"\s+", " ", raw or "").strip()
    if not t or t.lower() in ("nvt", "n.v.t.", "aangehouden", "aangehouden.", "vervallen", "ingetrokken"):
        return None
    # Un-glue labels stuck to a preceding word: "SPVerdeeld gestemd:" / "PvdAVoor:".
    t = re.sub(r"(?i)(?<=\w)(verdeeld\s+gestemd\s*:)", r" \1", t)
    t = re.sub(r"(?i)(?<=[A-Za-z])(voor|tegen|afwezig)\s*:", r" \1:", t)

    afwezig, split_set = set(), set()

    def grab_parens(s):
        # "(Fractie De Weerdt afwezig)" / "(CU-SGP/Boer afwezig)" -> absent fracties
        for m in re.finditer(r"\(([^)]*)\)", s):
            inner = m.group(1)
            if "afwezig" in inner.lower():
                for p in ibabs_parties(re.sub(r"afwezig", "", inner, flags=re.I)):
                    afwezig.add(p)
        return re.sub(r"\([^)]*\)", " ", s)

    t = grab_parens(t)
    labels = list(re.finditer(r"(?i)\b(voor|tegen|afwezig|verdeeld(?:\s+gestemd)?)\s*:", t))
    if not labels:
        if any(w in t.lower() for w in IBABS_ALL):
            return (("all", None), None, afwezig, split_set)
        return None

    voor_spec = tegen_spec = None
    for i, m in enumerate(labels):
        key = m.group(1).lower()
        end = labels[i + 1].start() if i + 1 < len(labels) else len(t)
        seg = t[m.end():end].strip(" .")
        seglow = seg.lower()
        if key == "afwezig":
            afwezig.update(ibabs_parties(seg))
            continue
        if key.startswith("verdeeld"):   # fracties that split their own vote
            split_set.update(ibabs_parties(seg))
            continue
        if any(w in seglow for w in IBABS_ALL):
            spec = ("all", None)
        elif "overige" in seglow:
            spec = ("rest", None)
        else:
            spec = ("list", set(ibabs_parties(seg)))
        if key == "voor":
            voor_spec = spec
        else:
            tegen_spec = spec
    return (voor_spec, tegen_spec, afwezig, split_set)


def ibabs_resolve(voor_spec, tegen_spec, afwezig, split, universe):
    """Turn the parsed specs into concrete (voor_set, tegen_set, split_set), expanding "overige
    fracties" / "unaniem" against the term's party universe minus absentees and split voters."""
    split = split - afwezig
    present = universe - afwezig - split
    listed = lambda s: set(s[1]) if s and s[0] == "list" else set()
    voor, tegen = listed(voor_spec), listed(tegen_spec)
    if voor_spec and voor_spec[0] == "all":
        voor = present - tegen
    if tegen_spec and tegen_spec[0] == "all":
        tegen = present - voor
    if voor_spec and voor_spec[0] == "rest":
        voor = present - tegen
    if tegen_spec and tegen_spec[0] == "rest":
        tegen = present - voor
    voor -= afwezig | split
    tegen -= afwezig | split
    voor -= tegen   # a party can't be on both sides
    return voor, tegen, split


def ibabs_date(s):
    m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})", (s or "").strip())
    if not m:
        return None
    dd, mm, yy = map(int, m.groups())
    try:
        return date(yy, mm, dd)
    except ValueError:
        return None


def ibabs_field(html, label):
    """Pull a <dt>Label</dt><dd>VALUE</dd> pair out of the detail page; tags stripped."""
    m = re.search(r"<dt[^>]*>\s*" + re.escape(label) + r"\s*</dt>\s*<dd[^>]*>(.*?)</dd>", html, re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


def ibabs_id(r):
    """Stable numeric id (the frontend coerces dataset ids with +; GUIDs would become NaN)."""
    ident = str(r.get("identity") or "").strip()
    if ident.isdigit():
        return int(ident)
    return int(r["DT_RowId"].replace("-", "")[:12], 16)


def ibabs_result(status):
    s = (status or "").lower()
    if s.startswith("aangenomen"):
        return "accepted"
    if s.startswith("verworpen"):
        return "rejected"
    return s or None


def ibabs_status_from_bijlage(html):
    """Reports without a Status field (Amendementen) encode the outcome in the attachment
    filename, e.g. "A8-2026 AANGENOMEN Volt PvdD …". Return the matched keyword, or ""."""
    bij = ibabs_field(html, "Bijlage") or ""
    m = re.search(r"\b(AANGENOMEN|VERWORPEN|INGETROKKEN|AANGEHOUDEN|VERVALLEN|VERDAAGD)\b", bij, re.I)
    return m.group(1).capitalize() if m else ""


def ibabs_title(r):
    title = (r.get("title") or "").strip()
    num = (r.get("motienummer") or "").strip()
    if num and num.lower() not in title.lower():
        return f"{num} — {title}" if title else num
    return title


def _list_year(r):
    """Best 4-digit year from a list row's date-ish fields (schema varies per portal)."""
    for k in ("ingediendindatum", "datum", "registrationdate"):
        m = re.search(r"(?:19|20)\d{2}", str(r.get(k, "") or ""))
        if m:
            return int(m.group(0))
    return 0


def ibabs_fetch(p):
    """Common iBabs fetch: for every report, pull the DataTables list + each in-term detail page.
    Returns [(row, date, html, type, id_base)] with row['status'] resolved (list / detail field /
    attachment filename). Each report gets its own id_base since `identity` restarts per report."""
    base = p["base"].rstrip("/")
    reports = p.get("reports") or [{"guid": p["report"], "type": "motie"}]
    term_start = date(*p["term_start"])
    raw, skipped = [], 0
    for ri, rep in enumerate(reports):
        id_base = ri * 10_000_000
        listing = post_json(f"{base}/Reports/GetReportData/{rep['guid']}", "draw=1&start=0&length=2000")
        rows = listing.get("data") if isinstance(listing, dict) else None
        if not rows:
            print(f"  {rep['type']}: report {rep['guid']} unreachable/empty — skipped")
            continue
        # Pre-filter by year to skip pre-term detail pages; the exact term cut is on the item's own
        # date below (a 1-year margin covers items indiened just before the term).
        cand = [r for r in rows if _list_year(r) >= term_start.year - 1]
        kept = 0
        for r in cand:
            html = try_text(f"{base}/Reports/Item/{r['DT_RowId']}")
            time.sleep(SLEEP)
            if not html:
                skipped += 1
                continue
            # Date label varies per portal: NH "Datum PS", Limburg list "datum" / detail "Datum".
            d = ibabs_date(ibabs_field(html, "Datum PS") or r.get("datum")
                           or ibabs_field(html, "Datum") or r.get("ingediendindatum"))
            if not d or d < term_start:
                continue
            if not (r.get("status") or "").strip():
                r["status"] = ibabs_field(html, "Status") or ibabs_status_from_bijlage(html)
            raw.append((r, d, html, rep["type"], id_base))
            kept += 1
        print(f"  {rep['type']}: {len(rows)} rows, {len(cand)} candidates, {kept} in-term")
    if skipped:
        print(f"  WARN: {skipped} detail page(s) failed to fetch")
    return raw


def ibabs_item(base, r, d, rtype, id_base, votes):
    status = (r.get("status") or "").strip()
    return {
        "id": ibabs_id(r) + id_base,
        "date": d.isoformat(),
        "title": ibabs_title(r),
        "type": rtype,
        "result": ibabs_result(status),
        "resultLabel": status or None,
        "source": f"{base}/Reports/Item/{r['DT_RowId']}",
        "votes": votes,
    }


def ibabs_finalize(items, appear, name_by_slug):
    """Shared tail: per-item totals, newest-first sort, party columns ordered by activity."""
    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(1 for v in m["votes"].values() if v["agree"] > v["disagree"]),
                       "disagree": sum(1 for v in m["votes"].values() if v["disagree"] > v["agree"])}
    order = sorted(appear, key=lambda s: (-appear[s], name_by_slug[s].lower()))
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  items with votes: {len(items)} {by_type}; fracties: {len(appear)}")
    return {"parties": [{"slug": s, "name": name_by_slug[s]} for s in order], "moties": items}


def collect_ibabs(p):
    """iBabs province. Two vote formats (set per province via "votes"):
    - "stemverhouding" (default, Noord-Holland): free-text, faction-level, "overige fracties" inferred.
    - "stemmen" (Limburg): structured per-fractie member counts — exact, with real split votes."""
    raw = ibabs_fetch(p)
    if not raw:
        return None
    return (ibabs_assemble_stemmen if p.get("votes") == "stemmen"
            else ibabs_assemble_stemverhouding)(p, raw)


def ibabs_assemble_stemverhouding(p, raw):
    """NH free-text "Stemverhouding". Two passes: build the term party universe (+ a first_seen gate
    for mid-term splinters), then resolve each item's "overige fracties" against the fracties that
    already existed on its date."""
    base = p["base"].rstrip("/")
    term_start = date(*p["term_start"])
    parsed = [(r, d, ibabs_parse(ibabs_field(html, "Stemverhouding")), rtype, id_base)
              for (r, d, html, rtype, id_base) in raw]

    universe, first_seen = set(), {}

    def mark(party, d):
        if party and (party not in first_seen or d < first_seen[party]):
            first_seen[party] = d

    for r, d, spec, rtype, id_base in parsed:
        if not spec:
            continue
        voor_spec, tegen_spec, afwezig, split = spec
        explicit = set(afwezig) | set(split)
        for s in (voor_spec, tegen_spec):
            if s and s[0] == "list":
                explicit |= s[1]
        universe |= explicit
        for party in explicit | set(ibabs_parties(r.get("fracties", ""))):
            mark(party, d)

    items, appear, name_by_slug = [], {}, {}
    for r, d, spec, rtype, id_base in parsed:
        if not spec:
            continue
        present = {q for q in universe if first_seen.get(q, term_start) <= d}
        voor, tegen, split = ibabs_resolve(*spec, present)
        if not voor and not tegen and not split:
            continue
        votes = {}
        # split (= "verdeeld gestemd") -> agree==disagree, rendered as "O" + split dot.
        for party, agree, disagree in ([(x, 1, 0) for x in voor] + [(x, 0, 1) for x in tegen]
                                       + [(x, 1, 1) for x in split]):
            slug = slugify(party)
            name_by_slug[slug] = party
            votes[slug] = {"agree": agree, "disagree": disagree, "abstain": 0}
            appear[slug] = appear.get(slug, 0) + 1
        items.append(ibabs_item(base, r, d, rtype, id_base, votes))
    return ibabs_finalize(items, appear, name_by_slug)


def ibabs_assemble_stemmen(p, raw):
    """Limburg "Stemmen": structured per-fractie member counts for the voor and tegen sides.
    Self-contained (nothing inferred); a fractie on both sides is a real split (agree>0, disagree>0)."""
    base = p["base"].rstrip("/")
    items, appear, name_by_slug = [], {}, {}
    for r, d, html, rtype, id_base in raw:
        votes = ibabs_parse_stemmen(html, name_by_slug)
        if not votes:
            continue
        for slug in votes:
            appear[slug] = appear.get(slug, 0) + 1
        items.append(ibabs_item(base, r, d, rtype, id_base, votes))
    return ibabs_finalize(items, appear, name_by_slug)


# Limburg "Stemmen" markup: <div class="vote-summary-legend-{in-favour|against}"> … <div
# class="text">Fractie (Statenleden) (N), …</div>. A fractie on both sides = a split vote.
def ibabs_parse_stemmen(html, name_by_slug):
    m = re.search(r"<dt[^>]*>\s*Stemmen\s*</dt>\s*<dd[^>]*>(.*?)</dd>", html, re.S)
    if not m:
        return {}
    block = m.group(1)
    votes = {}

    def side(css, key):
        sm = re.search(r'vote-summary-legend-' + css + r'\b.*?<div class="text">(.*?)</div>', block, re.S)
        if not sm:
            return
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sm.group(1))).strip()
        for name, cnt in ibabs_stemmen_items(text):
            slug = slugify(name)
            name_by_slug.setdefault(slug, name)
            votes.setdefault(slug, {"agree": 0, "disagree": 0, "abstain": 0})[key] += cnt

    side("in-favour", "agree")
    side("against", "disagree")
    return votes


def ibabs_stemmen_items(text):
    """"50PLUS (Statenlid) (1), CDA (Statenleden) (4), Horizon (1)" -> [(canon_name, count)].
    Fractie names contain no commas in this summary, so a plain comma split is safe."""
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        m = re.match(r"^(.*?)\s*(?:\((?:Statenlid|Statenleden)\)\s*)?\((\d+)\)\s*$", chunk)
        if m:
            name = ibabs_canon(m.group(1))
            if name:
                out.append((name, int(m.group(2))))
    return out


# --- Tweede Kamer (OData) adapter ---------------------------------------------
# The Tweede Kamer publishes an OData v4 API (gegevensmagazijn.tweedekamer.nl). The vote chain is
# Stemming -> Besluit -> Zaak (the motie/amendement/wetsvoorstel) + Agendapunt -> Activiteit (date).
# $expand inlines the children and nested navigation is filterable, so one paged query (250/page,
# follow @odata.nextLink) pulls everything. Votes are per fractie WITH seat counts (FractieGrootte)
# -> exact tallies, tier A. See data-sources.md §8 for the full reverse-engineering notes.

# Stemming.ActorFractie is the fractie name AT vote time, so a mid-term rename yields two names for
# one group. Merge a pure rename into a single column (GroenLinks-PvdA was renamed "Progressief
# Nederland" on 2026-06-09; most of the term it was GL-PvdA, so keep that as the display name).
# GroenLinks-PvdA was renamed "Progressief Nederland" (afkorting "PRO") on 2026-06-09; most of the
# term it voted as GroenLinks-PvdA, so merge both spellings into one column under that name.
TK_ALIASES = {"Progressief Nederland": "GroenLinks-PvdA", "PRO": "GroenLinks-PvdA"}
TK_TYPE = {"Motie": "motie", "Amendement": "amendement", "Wetgeving": "wetsvoorstel"}


def tk_result(besluitsoort):
    """Map BesluitSoort -> (result, label). Check 'niet aangenomen'/'verworpen' before 'aangenomen'
    (the former contains the latter as a substring)."""
    s = (besluitsoort or "").lower()
    if "niet aangenomen" in s or "verworpen" in s:
        return "rejected", "Verworpen"
    if "gestaakt" in s:
        return "tie", "Staken van stemmen"
    if "aangenomen" in s or "goedgekeurd" in s or "vastgesteld" in s:
        return "accepted", "Aangenomen"
    return None, (besluitsoort or None)


def tk_pick_zaak(zaken):
    """A besluit can link to several Zaken; pick the most table-worthy one (motie > amendement >
    wetsvoorstel) and ignore the rest (covering documents, etc.)."""
    ranked = [(("Motie", "Amendement", "Wetgeving").index(z["Soort"]), z)
              for z in zaken if z.get("Soort") in TK_TYPE]
    if not ranked:
        return None
    return min(ranked, key=lambda x: x[0])[1]


def tk_item(public, b, name_by_slug, seats):
    """Build one normalized stemming dict from a Besluit (with expanded Stemming/Zaak/Agendapunt),
    or None if it isn't a usable per-fractie vote on a motie/amendement/wetsvoorstel."""
    z = tk_pick_zaak(b.get("Zaak") or [])
    if not z:
        return None
    rtype = TK_TYPE.get(z.get("Soort"))
    if not rtype:
        return None
    act = (b.get("Agendapunt") or {}).get("Activiteit") or {}
    dt = (act.get("Datum") or "")[:10]
    if not re.match(r"\d{4}-\d{2}-\d{2}$", dt):
        return None
    # Group this besluit's Stemming rows per fractie. Three shapes occur:
    #   - block vote: one row, Persoon_Id null, FractieGrootte = full fractie size.
    #   - hoofdelijke stemming: one row PER MEMBER (Persoon_Id set), each carrying the fractie size.
    #   - block + aantekening: a block row plus a few per-member rows for members who deviated.
    # One rule covers all three: each per-member row counts as 1 seat for that member's vote; a block
    # row contributes its FractieGrootte MINUS the fractie's individually-recorded members (so a
    # deviator isn't counted in both the block and their own row). Sums to seats present, never inflated.
    KEY = {"Voor": "agree", "Tegen": "disagree"}
    by_fr = {}
    for s in b.get("Stemming") or []:
        fr = (s.get("ActorFractie") or s.get("ActorNaam") or "").strip()
        fr = TK_ALIASES.get(fr, fr)
        if fr:
            by_fr.setdefault(fr, []).append(s)
    votes = {}
    for fr, rows in by_fr.items():
        slug = slugify(fr)
        name_by_slug.setdefault(slug, fr)
        size = max((r.get("FractieGrootte") or 0) for r in rows)
        seats[slug] = max(seats.get(slug, 0), size)
        v = votes.setdefault(slug, {"agree": 0, "disagree": 0, "abstain": 0})
        members = [r for r in rows if r.get("Persoon_Id")]
        for r in members:                                   # individual (deviating/hoofdelijke) votes
            v[KEY.get(r.get("Soort"), "abstain")] += 1
        for r in rows:                                      # block rows, minus the members already counted
            if r.get("Persoon_Id"):
                continue
            v[KEY.get(r.get("Soort"), "abstain")] += max((r.get("FractieGrootte") or 0) - len(members), 0)
    if not any(v["agree"] or v["disagree"] for v in votes.values()):
        return None   # roll-call with no actual voor/tegen (shouldn't happen, but guard)
    result, label = tk_result(b.get("BesluitSoort"))
    nummer = (z.get("Nummer") or "").strip()
    title = (z.get("Onderwerp") or z.get("Titel") or "").strip()
    return {
        "id": int(b["Id"].replace("-", "")[:12], 16),   # GUID -> stable int (frontend coerces +id)
        "date": dt,
        "title": title,
        "type": rtype,
        "result": result,
        "resultLabel": label,
        "source": (public.rstrip("/") + "/zoeken?qry=" + urllib.parse.quote(nummer)) if nummer else public,
        "votes": votes,
    }


def collect_tk(p):
    """Tweede Kamer. One paged OData query (with $expand) pulls every in-term roll-call besluit on a
    motie/amendement/wetsvoorstel, votes inlined. Self-contained per besluit (exact seat counts)."""
    base = p["base"].rstrip("/")
    public = p.get("public", base)
    term_start = date(*p["term_start"])
    term_iso = term_start.isoformat() + "T00:00:00Z"
    filt = ("startswith(BesluitSoort,'Stemmen') "
            "and Agendapunt/Activiteit/Datum ge " + term_iso + " "
            "and Stemming/any() "
            "and Zaak/any(z: z/Soort eq 'Motie' or z/Soort eq 'Amendement' or z/Soort eq 'Wetgeving')")
    expand = ("Stemming($select=ActorFractie,ActorNaam,Soort,FractieGrootte,Persoon_Id),"
              "Zaak($select=Nummer,Soort,Onderwerp,Titel),"
              "Agendapunt($expand=Activiteit($select=Datum))")
    qs = urllib.parse.urlencode(
        {"$filter": filt, "$expand": expand, "$select": "Id,BesluitSoort,BesluitTekst",
         "$orderby": "GewijzigdOp desc", "$format": "json"},
        quote_via=urllib.parse.quote)
    url = base + "/Besluit?" + qs

    items, appear, name_by_slug, seats, seen = [], {}, {}, {}, set()
    pages = 0
    while url:
        data = try_json(url)
        if not data:
            break
        for b in data.get("value", []):
            it = tk_item(public, b, name_by_slug, seats)
            if not it or it["id"] in seen:
                continue
            seen.add(it["id"])
            items.append(it)
            for slug in it["votes"]:
                appear[slug] = appear.get(slug, 0) + 1
        pages += 1
        url = data.get("@odata.nextLink")
        time.sleep(SLEEP)
    print(f"  fetched {pages} page(s); {len(items)} stemmingen; {len(appear)} fracties")
    if not items:
        return None

    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(v["agree"] for v in m["votes"].values()),
                       "disagree": sum(v["disagree"] for v in m["votes"].values())}
    # Columns ordered by current fractie size (biggest first), then activity, then name.
    order = sorted(appear, key=lambda s: (-seats.get(s, 0), -appear[s], name_by_slug[s].lower()))
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  types: {by_type}")
    return {"parties": [{"slug": s, "name": name_by_slug[s]} for s in order], "moties": items}


# --- Eerste Kamer (HTML) adapter ----------------------------------------------
# The Eerste Kamer has NO machine API (no OData/opendata host) — see data-sources.md §9. But the
# "stemmingen per vergaderdag" pages embed, per stemming, the structured per-fractie breakdown:
#   <strong>voor:</strong> A, B en C<br /><strong>tegen:</strong> D en E<br />
# Both sides are named (no "overige fracties" inference, unlike NH), but there are no seat counts
# (the EK votes bij zitten en opstaan) -> faction-level V/T, tier B. Pages are 25 stemmingen each;
# we follow the "eerdere stemmingen" link back to term start. Hamerstukken (passed without a vote;
# only an optional "aantekening gevraagd") carry no voor/tegen and are skipped.
EK_MONTHS = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
             "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12}


def ek_date(s):
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", (s or "").lower())
    if not m:
        return None
    mon = EK_MONTHS.get(m.group(2))
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def ek_parties(text):
    """Split a 'A, B, C en D' fractie list into display names. Names are already canonical on the
    EK site (e.g. 'GroenLinks-PvdA', 'Fractie-Van de Sanden', '50PLUS') — no alias map needed."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip(" .")
    if not text:
        return []
    text = re.sub(r"\s+en\s+", ", ", text)   # the last separator is " en " -> normalize to comma
    return [c.strip(" .") for c in text.split(",") if c.strip(" .")]


def ek_side(block, label):
    """Fracties listed after a <strong>{label}:</strong> tag, up to the next <br>/<strong>."""
    m = re.search(r"<strong>\s*" + label + r"\s*:\s*</strong>(.*?)(?:<br|<strong|$)", block, re.I | re.S)
    return ek_parties(m.group(1)) if m else []


def ek_type(title, dossier_href):
    low = (title or "").lower()
    if "/wetsvoorstel/" in (dossier_href or ""):
        return "wetsvoorstel"
    if "motie" in low:
        return "motie"
    return "overig"


def ek_result(type_result):
    tr = (type_result or "").lower()
    if "verworpen" in tr:
        return "rejected", "Verworpen"
    if "gestaakt" in tr or "staken" in tr:
        return "tie", "Staken van stemmen"
    if "aangenomen" in tr or "aanvaard" in tr:
        return "accepted", "Aangenomen"
    return None, (type_result or None)


def ek_normkey(fr):
    """Normalize a fractie name for matching: drop a leading 'Fractie-' and all spaces/hyphens.
    So the fractie-level 'Fractie-Van de Sanden' and the member-paren form 'Van de Sanden' map to
    one key ('vandesanden'); 'GroenLinks-PvdA' -> 'groenlinkspvda'; 'PVV' -> 'pvv'."""
    return re.sub(r"[\s\-]", "", re.sub(r"^fractie[-\s]+", "", fr.strip().lower()))


def ek_member_fractie(tok):
    """Map a member/person reference to its fractie name, or None for a plain fractie token.
    Two member forms occur: a *hoofdelijke* stemming lists 'Mei Li Vos (GroenLinks-PvdA)' (the
    fractie is in parentheses), and a one-member fractie is sometimes written 'het lid Eric
    Kemperman' (drop the first name -> the surname, which matches 'Fractie-Kemperman')."""
    m = re.match(r"^.*\S\s*\(([^()]+)\)\s*$", tok)
    if m:
        return m.group(1).strip()
    m = re.match(r"^(?:het lid|de leden|de heer|mevrouw|mevr\.?|dhr\.?)\s+(.+)$", tok, re.I)
    if m:
        parts = m.group(1).split()
        return " ".join(parts[1:]) if len(parts) > 1 else parts[0]   # drop the first name
    return None


def ek_parse_item(chunk, d, base):
    """One stemming <li> -> a raw dict (votes resolved later), or None for hamerstukken / no
    breakdown. Keeps the voor/tegen token lists verbatim (they may be fracties OR members)."""
    if d is None:
        return None
    mt = re.search(r'<div class="opsomtekst">(.*?)(?:<br|<ul)', chunk, re.S)
    dossier = re.search(r'href="(/(?:wetsvoorstel|kamerstukdossier)/[^"]+)"', chunk)
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", mt.group(1) if mt else "")).strip()
    title = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", title))
    mr = re.search(r'js-expandmore.*?<a href="([^"]+)">\s*(.*?)\s*</a>', chunk, re.S)
    mb = re.search(r'js-to_expand[^>]*>(.*?)</div>', chunk, re.S)
    block = mb.group(1) if mb else ""
    voor, tegen = ek_side(block, "voor"), ek_side(block, "tegen")
    if not voor and not tegen:
        return None   # hamerstuk / aantekening-only / no recorded vote -> skip
    return {
        "date": d.isoformat(),
        "title": title,
        "dossier_href": dossier.group(1) if dossier else None,
        "type_result": re.sub(r"\s+", " ", mr.group(2)).strip() if mr else "",
        "verslag_href": mr.group(1) if mr else None,
        "voor": voor,
        "tegen": tegen,
    }


def ek_parse_page(html, base):
    """Parse one 'per vergaderdag' page into raw items: walk day-headers and stemming <li>s in
    document order, carrying the current date forward."""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S)
    token = re.compile(
        r'<h2>\s*<a id="p\d+"></a>(.*?)</h2>'
        r'|<li class="opsomitem met_image image_breed">(.*?)'
        r'(?=<li class="opsomitem met_image image_breed">|</ul>)', re.S)
    cur_date, items = None, []
    for m in token.finditer(body):
        if m.group(1) is not None:
            cur_date = ek_date(re.sub(r"<[^>]+>", " ", m.group(1)))
        else:
            it = ek_parse_item(m.group(2), cur_date, base)
            if it:
                items.append(it)
    return items


def ek_next_url(base, html):
    """The site's own 'eerdere stemmingen' (older) pagination link. Pick it by anchor TEXT — a
    'recentere stemmingen' (newer) link with the same start_006 param appears from page 2 on, and
    grabbing the wrong one makes the walk oscillate."""
    for href, txt in re.findall(
            r'<a[^>]+href="(/stemmingen_per_vergaderdag\?filter=alles[^"]*start_006[^"]*)"[^>]*>(.*?)</a>',
            html, re.S):
        if "eerdere" in re.sub(r"<[^>]+>", "", txt).lower():
            return base + href.replace("&#38;", "&").replace("&amp;", "&")
    return None


def collect_ek(p):
    """Eerste Kamer. Page through /stemmingen_per_vergaderdag (25/page, following the site's own
    'eerdere stemmingen' link) back to term start, then resolve members to fracties and assemble the
    faction-level matrix. Hoofdelijke (per-member) stemmingen are aggregated to the fractie."""
    base = p["base"].rstrip("/")
    term_start = date(*p["term_start"])
    url = base + "/stemmingen_per_vergaderdag?filter=alles"
    raw, seen_urls, pages = [], set(), 0
    while url and url not in seen_urls and pages < 120:
        seen_urls.add(url)
        html = try_text(url)
        if not html:
            break
        pages += 1
        oldest = None
        for it in ek_parse_page(html, base):
            dd = date.fromisoformat(it["date"])
            oldest = dd if oldest is None or dd < oldest else oldest
            if dd >= term_start:
                raw.append(it)
        if oldest and oldest < term_start:   # walked past the term -> stop
            break
        url = ek_next_url(base, html)
        time.sleep(SLEEP)
    if not raw:
        return None

    # Build the canonical fractie registry from fractie-level (non-member) tokens, then resolve
    # every token — member tokens via their parenthetical fractie — to one canonical display name.
    canon = {}
    for it in raw:
        for tok in it["voor"] + it["tegen"]:
            if ek_member_fractie(tok):
                continue
            k = ek_normkey(tok)
            if k not in canon or len(tok) > len(canon[k]):
                canon[k] = tok

    def resolve(tok):
        fr = ek_member_fractie(tok) or tok
        return canon.get(ek_normkey(fr), fr)

    by_id, name_by_slug, appear = {}, {}, {}
    for it in raw:
        sides = {}
        for tok in it["voor"]:
            sides.setdefault(resolve(tok), set()).add("voor")
        for tok in it["tegen"]:
            sides.setdefault(resolve(tok), set()).add("tegen")
        if not sides:
            continue
        votes = {}
        for disp, s in sides.items():
            slug = slugify(disp)
            name_by_slug.setdefault(slug, disp)
            # A fractie whose members split on a hoofdelijke vote lands on both sides -> real split.
            votes[slug] = {"agree": int("voor" in s), "disagree": int("tegen" in s), "abstain": 0}
        result, label = ek_result(it["type_result"])
        vk = lambda side: ",".join(sorted(slugify(d) for d, s in sides.items() if side in s))
        key = f'{it["date"]}|{it["title"]}|{vk("voor")}|{vk("tegen")}'
        iid = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:12], 16)
        if iid in by_id:
            continue
        by_id[iid] = {
            "id": iid,
            "date": it["date"],
            "title": it["title"],
            "type": ek_type(it["title"], it["dossier_href"]),
            "result": result,
            "resultLabel": label,
            "source": base + it["verslag_href"] if it["verslag_href"] else base,
            "votes": votes,
        }

    items = list(by_id.values())
    for it in items:
        for slug in it["votes"]:
            appear[slug] = appear.get(slug, 0) + 1
    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(1 for v in m["votes"].values() if v["agree"] > v["disagree"]),
                       "disagree": sum(1 for v in m["votes"].values() if v["disagree"] > v["agree"])}
    order = sorted(appear, key=lambda s: (-appear[s], name_by_slug[s].lower()))
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  fetched {pages} page(s); {len(items)} stemmingen; {len(appear)} fracties; {by_type}")
    return {"parties": [{"slug": s, "name": name_by_slug[s]} for s in order], "moties": items}


# --- Europees Parlement (HowTheyVote.eu API) adapter --------------------------
# HowTheyVote.eu compiles the EP's roll-call open data into a clean JSON API. The unit is the
# EUROPEAN POLITICAL GROUP: GET /api/votes/{id} -> stats.by_group gives exact per-group MEP counts
# (FOR/AGAINST/ABSTENTION/DID_NOT_VOTE) -> our {agree,disagree,abstain}, tier A. The /api/votes list
# is is_main (final) votes only, newest first, across the 9th+10th terms -> date-filter to the current
# term. See data-sources.md §10. License: ODbL (attribution + share-alike).
#
# Display names + stable slugs per group code (the API `label` is occasionally mojibaked, so we map
# explicitly). Slug = code lowercased with '_' -> '-' (independent of the display name).
EP_GROUPS = {
    "EPP": "EPP", "SD": "S&D", "RENEW": "Renew", "GREEN_EFA": "Greens/EFA", "ECR": "ECR",
    "PFE": "PfE", "GUE_NGL": "The Left", "ESN": "ESN", "NI": "Niet-fractiegebonden",
}
EP_TYPE = {"COD": "wetgeving", "NLE": "wetgeving", "APP": "wetgeving", "SYN": "wetgeving",
           "INI": "initiatiefverslag", "INL": "initiatiefverslag",
           "RSP": "resolutie", "BUD": "begroting", "BUI": "begroting"}


def ep_group(code, label):
    name = EP_GROUPS.get(code) or label or code
    slug = (code or slugify(name)).lower().replace("_", "-")
    return slug, name


# Dutch MEP (HowTheyVote/EP id) -> national party, for the "Nederlandse afvaardiging" breakout.
# Resolved once from the EP Open Data Portal (each MEP's NATIONAL_POLITICAL_GROUP membership ->
# corporate-body label); the 10th-term NL delegation is 31 MEPs. The collector WARNS on any NL MEP
# id not in this map (e.g. a mid-term replacement) so it can be topped up. See data-sources.md §10.
EP_NL_PARTY = {
    "125023": "PvdD", "256990": "Volt", "257438": "VVD", "103246": "PVV", "197780": "VVD",
    "96725": "GL-PvdA", "197773": "SGP", "256976": "D66", "257437": "GL-PvdA", "97399": "NSC",
    "96940": "D66", "256968": "CDA", "257003": "VVD", "95074": "CDA", "256983": "BBB",
    "197870": "GL-PvdA", "5392": "GL-PvdA", "197781": "VVD", "192254": "PVV", "91636": "GL-PvdA",
    "130881": "PVV", "197782": "GL-PvdA", "256998": "PVV", "256970": "D66", "256978": "Volt",
    "125325": "BBB", "256996": "PVV", "218347": "GL-PvdA", "197772": "GL-PvdA", "256981": "PVV",
    "276060": "CDA",
    # Former MEPs who voted earlier this term before being replaced (not in the current-MEP list):
    "197778": "CDA",   # Tom Berendsen
    "256991": "PVV",   # Sebastiaan Stöteler
}
# Column order for the NL breakout: by 2024 EP-election seats (the adapter falls back to activity).
EP_NL_ORDER = ["GL-PvdA", "PVV", "VVD", "D66", "CDA", "BBB", "Volt", "PvdD", "SGP", "NSC"]

_EP_CACHE = {}   # base -> {"metas": [...], "details": {id: detail}} — shared across the two EP scopes


def ep_load(base, term_start):
    """Fetch (and cache) the term's is_main votes + their details once. Both EP scopes (Europese
    fracties / Nederlandse afvaardiging) run in the same process, so the second reuses the cache
    instead of re-fetching ~545 details."""
    if base in _EP_CACHE:
        return _EP_CACHE[base]["metas"], _EP_CACHE[base]["details"]
    metas, page = [], 1
    while page <= 60:   # 1) stemming index: page newest-first until we cross the term boundary
        data = try_json(f"{base}/api/votes?page_size=100&page={page}")
        results = data.get("results") if isinstance(data, dict) else None
        if not results:
            break
        stop = False
        for r in results:
            try:
                d = date.fromisoformat((r.get("timestamp") or "")[:10])
            except ValueError:
                continue
            if d < term_start:
                stop = True
                continue
            metas.append(r)
        if stop or not data.get("has_next"):
            break
        page += 1
        time.sleep(SLEEP)
    # 2) details: the API is ~1.5s/request, so 545 sequential calls take ~15 min; a small thread pool
    #    keeps wall-time and load reasonable (~8 concurrent against a CDN-backed API).
    def _detail(r):
        return r["id"], try_json(f"{base}/api/votes/{r['id']}")
    details = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for vid, det in ex.map(_detail, metas):
            details[vid] = det
    _EP_CACHE[base] = {"metas": metas, "details": details}
    return metas, details


def ep_item(r, det, votes):
    """One normalized stemming dict, shared by both EP breakdowns (same vote metadata)."""
    proc = det.get("procedure") or {}
    res = (r.get("result") or "").upper()
    result = "accepted" if res == "ADOPTED" else "rejected" if res == "REJECTED" else None
    return {
        "id": int(r["id"]),
        "date": (r.get("timestamp") or "")[:10],
        "title": r.get("display_title") or proc.get("title") or "",
        "type": EP_TYPE.get((proc.get("type") or "").upper(), "overig"),
        "result": result,
        "resultLabel": "Aangenomen" if result == "accepted" else "Verworpen" if result == "rejected" else (r.get("result") or None),
        "source": f"https://howtheyvote.eu/votes/{r['id']}",
        "votes": votes,
    }


def ep_finalize(items, appear, name_by_slug, seats, order_hint=None, members=None):
    """Shared tail: per-item totals, newest-first sort, column order, optional MEP rosters."""
    if not items:
        return None
    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(v["agree"] for v in m["votes"].values()),
                       "disagree": sum(v["disagree"] for v in m["votes"].values())}

    def rank(s):
        hint = order_hint.index(name_by_slug[s]) if order_hint and name_by_slug[s] in order_hint else 99
        return (hint, -seats.get(s, 0), -appear.get(s, 0), name_by_slug[s].lower())
    parties = []
    for s in sorted(appear, key=rank):
        party = {"slug": s, "name": name_by_slug[s]}
        if members and members.get(s):
            party["members"] = sorted(members[s])
        parties.append(party)
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  kept {len(items)} stemmingen; {len(appear)} fracties; {by_type}")
    return {"parties": parties, "moties": items}


def ep_assemble_groups(metas, details):
    """Default view: per European political group, from stats.by_group (exact MEP counts)."""
    items, appear, name_by_slug, seats = [], {}, {}, {}
    for r in metas:
        det = details.get(r["id"])
        if not det:
            continue
        votes = {}
        for gb in ((det.get("stats") or {}).get("by_group") or []):
            g, st = gb.get("group") or {}, gb.get("stats") or {}
            agree, disagree, abstain = st.get("FOR", 0), st.get("AGAINST", 0), st.get("ABSTENTION", 0)
            if not (agree or disagree or abstain):   # whole group did not vote -> afwezig (blank)
                continue
            slug, name = ep_group(g.get("code"), g.get("short_label") or g.get("label"))
            name_by_slug[slug] = name
            votes[slug] = {"agree": agree, "disagree": disagree, "abstain": abstain}
            seats[slug] = max(seats.get(slug, 0), agree + disagree + abstain + st.get("DID_NOT_VOTE", 0))
        if not votes:
            continue
        items.append(ep_item(r, det, votes))
        for slug in votes:
            appear[slug] = appear.get(slug, 0) + 1
    return ep_finalize(items, appear, name_by_slug, seats)


def ep_assemble_nl(metas, details):
    """Dutch-delegation view: group the NL MEPs (member_votes, country NLD) by national party
    (EP_NL_PARTY) -> exact per-party MEP counts. Same vote set as the group view; carries MEP rosters."""
    items, appear, name_by_slug, seats, members = [], {}, {}, {}, {}
    unknown = {}
    for r in metas:
        det = details.get(r["id"])
        if not det:
            continue
        tally, roster = {}, {}
        for mv in (det.get("member_votes") or []):
            m = mv.get("member") or {}
            if (m.get("country") or {}).get("code") != "NLD":
                continue
            party = EP_NL_PARTY.get(str(m.get("id")))
            if not party:
                unknown[str(m.get("id"))] = m.get("full_name") or ""
                continue
            t = tally.setdefault(party, {"agree": 0, "disagree": 0, "abstain": 0, "n": 0})
            pos = mv.get("position")
            if pos == "FOR":
                t["agree"] += 1
            elif pos == "AGAINST":
                t["disagree"] += 1
            elif pos == "ABSTENTION":
                t["abstain"] += 1
            t["n"] += 1   # all NL members of the party (incl. did-not-vote) -> party size for ordering
            roster.setdefault(party, set()).add(m.get("full_name") or "")
        votes = {}
        for party, t in tally.items():
            if not (t["agree"] or t["disagree"] or t["abstain"]):
                continue   # party present but all did-not-vote -> afwezig (blank)
            slug = slugify(party)
            name_by_slug[slug] = party
            votes[slug] = {"agree": t["agree"], "disagree": t["disagree"], "abstain": t["abstain"]}
            seats[slug] = max(seats.get(slug, 0), t["n"])
            members.setdefault(slug, set()).update(roster.get(party, ()))
        if not votes:
            continue
        items.append(ep_item(r, det, votes))
        for slug in votes:
            appear[slug] = appear.get(slug, 0) + 1
    if unknown:
        print(f"  WARN: {len(unknown)} NL MEP(s) not in EP_NL_PARTY (update the map): "
              + ", ".join(f"{k} {v}" for k, v in list(unknown.items())[:8]))
    return ep_finalize(items, appear, name_by_slug, seats, order_hint=EP_NL_ORDER, members=members)


def collect_ep(p):
    """Europees Parlement. Two breakdowns of the same roll-call votes (term >= term_start): by
    European political group (default) or by Dutch national party (breakout='nl'). The fetched vote
    details are cached and shared between the two scopes, so the second adds no extra requests."""
    metas, details = ep_load(p["base"].rstrip("/"), date(*p["term_start"]))
    if not metas:
        return None
    return ep_assemble_nl(metas, details) if p.get("breakout") == "nl" else ep_assemble_groups(metas, details)


# --- Notubiz adapter ----------------------------------------------------------
# Notubiz powers 5 PS provinces. No token is needed (data-sources.md §11). Three public surfaces:
#   1. events API   GET api.notubiz.nl/events?organisation_id=&date_from=&date_to=&page=&version=1.21
#                   -> meetings; filter gremium.id to the plenary "Provinciale Staten" gremium and
#                      agenda_item_count>0. (version=1.21 is mandatory; date_* = "YYYY-MM-DD HH:MM:SS".)
#   2. votings API  GET api.notubiz.nl/agenda_items/votings?meeting_id=&version=1.21
#                   -> per stemming: id, title, voting_result, and per-MEMBER votes (role_id only).
#   3. portal HTML  https://<slug>.notubiz.nl/vergadering/<mid>
#                   -> per stemming a <div id="chart_<id>"> + a votes_parties block listing each fractie
#                      with its members tagged <li class="in_favor|against">. chart_<id> == the votings
#                      API `id` (NOT voting_id), so the HTML blocks join to the API votings 1:1.
# The role_id -> fractie join is auth-walled, but the portal already names the fractie + members, so we
# don't need it. We use the API for discovery + metadata (title/result) and the portal for the exact
# per-fractie counts (members aggregated to the fractie) -> granularity "member", tier A.
NOTUBIZ_API = "https://api.notubiz.nl"

# Merge spelling variants / pure mid-term renames into one column (the portal occasionally writes a
# fractie's full name where it elsewhere uses the abbreviation, and a renamed fractie keeps voting as
# the same group). Early-term fracties that genuinely existed separately before a merger (e.g. ZH's
# GroenLinks + PvdA before they fused into GroenLinks-PvdA) are NOT merged — they cast separate votes.
NOTUBIZ_ALIASES = {
    "PRO": "GroenLinks-PvdA",          # Zuid-Holland: GroenLinks-PvdA renamed itself "PRO" mid-term
    "Partij voor de Dieren": "PvdD",   # Zuid-Holland: full name vs abbreviation -> one column
}
# Labels that are not a real fractie (the absence of one) -> not a voting column. "Geen partij" is
# how the portal tags a member mid-afsplitsing who has no fractie yet (Overijssel, één lid, één dag).
NOTUBIZ_SKIP = {"Geen partij", "Gedeputeerde Staten"}


def notubiz_classify(title, voting_type):
    """Item type. Prefer the API's explicit `voting_type` (motion/amendment/council_proposal/
    initiative_proposal); it's reliable for Fryslân/Overijssel but null for Gelderland and many ZH
    votings, so fall back to the title. Titles embed the type as a code prefix that varies per province
    — "M 1567"/"A 873"/"SV …" (ZH), "26M45"/"36A12" (Gelderland), "PS26-M52"/"PS26-MV9" (Overijssel) —
    or in Frisian on Fryslân ("Moasje"/"Amendemint")."""
    vt = (voting_type or "").lower()
    if vt == "motion":
        return "motie"
    if vt == "amendment":
        return "amendement"
    if vt in ("council_proposal", "initiative_proposal"):
        return "besluit"
    low = re.sub(r"\s+", " ", title or "").strip().lower()
    if "ordevoorstel" in low or "oarderfoarstel" in low:
        return "ordevoorstel"
    if ("amendement" in low or "amendemint" in low
            or re.match(r"^(?:ps\s?\d+[-\s])?a\s?\d", low) or re.match(r"^\d{1,3}\s?a\d", low)):
        return "amendement"
    if ("motie" in low or "moasje" in low
            or re.match(r"^(?:ps\s?\d+[-\s])?m\s?v?\s?\d", low) or re.match(r"^\d{1,3}\s?m\s?v?\d", low)):
        return "motie"
    if ("statenvoorstel" in low or low.startswith("sv") or "besluit" in low
            or "voordracht" in low or "voarstel" in low):
        return "besluit"
    return "overig"


def notubiz_result(s):
    s = (s or "").lower()
    if s in ("adopted", "accepted"):
        return "accepted", "Aangenomen"
    if s == "rejected":
        return "rejected", "Verworpen"
    if s in ("equal", "tie", "tied", "staken"):
        return "tie", "Staken van stemmen"
    return None, (s or None)


def notubiz_events(org_id, gremium_id, term_start, end):
    """Page the public events API over the term window; return [(meeting_id, date)] for the plenary
    gremium's meetings that actually carry agenda items (recesses etc. have agenda_item_count 0)."""
    meetings, page = [], 1
    while page <= 60:
        qs = urllib.parse.urlencode(
            {"organisation_id": org_id,
             "date_from": term_start.isoformat() + " 00:00:00",
             "date_to": end.isoformat() + " 23:59:59",
             "page": page, "format": "json", "version": "1.21"})
        data = try_json(f"{NOTUBIZ_API}/events?{qs}")
        if not data:
            break
        for e in data.get("events", []):
            if (e.get("gremium") or {}).get("id") != gremium_id:
                continue
            if not (e.get("event_type_data") or {}).get("agenda_item_count"):
                continue
            mid = e.get("id")
            d = ((e.get("plannings") or [{}])[0].get("start_date") or "")[:10]
            if mid and re.match(r"\d{4}-\d{2}-\d{2}$", d):
                meetings.append((mid, d))
        if not (data.get("pagination") or {}).get("has_more_pages"):
            break
        page += 1
        time.sleep(SLEEP)
    return meetings


def notubiz_parse_meeting(html):
    """Parse a portal vergadering page into {chart_id: {fractie_name: {agree,disagree,abstain}}}.
    Each stemming is a <div ... id="chart_<id>"> followed by a votes_parties block; within it each
    fractie is a <li>NAME<ul> ...member <li class="in_favor|against">... </ul></li>. The member li
    class is that member's own vote, so counting them gives exact per-fractie tallies and a fractie in
    the 'verdeeld' (divided) side yields a real split (agree>0 and disagree>0). Member/Leden <li>s
    carry a class or a <p>, so only the bare <li>NAME<ul> fractie rows match."""
    out = {}
    for m in re.finditer(r'id="chart_(\d+)"[^>]*></div>(.*?)'
                         r'(?=<div class="votes_chart"|id="chart_\d+"|$)', html, re.S):
        cid, seg, votes = int(m.group(1)), m.group(2), {}
        for fm in re.finditer(r'<li>\s*([^<]+?)\s*<ul>(.*?)</ul>\s*</li>', seg, re.S):
            name = re.sub(r"\s+", " ", fm.group(1)).strip()
            inner = fm.group(2)
            agree = len(re.findall(r'class="in_favor"', inner))
            disagree = len(re.findall(r'class="against"', inner))
            if not name or not (agree or disagree):
                continue
            v = votes.setdefault(name, {"agree": 0, "disagree": 0, "abstain": 0})
            v["agree"] += agree
            v["disagree"] += disagree
        if votes:
            out[cid] = votes
    return out


def collect_notubiz(p):
    """Notubiz PS province. Discover plenary meetings (events API), then per meeting join the votings
    API metadata (title/result) to the portal page's per-fractie breakdown (exact member counts)."""
    org_id, gremium_id, slug = p["organisation_id"], p["gremium_id"], p["slug"]
    portal = f"https://{slug}.notubiz.nl"
    term_start = date(*p["term_start"])
    meetings = notubiz_events(org_id, gremium_id, term_start, date.today())
    print(f"  {len(meetings)} plenaire vergadering(en) met agendapunten in termijn")

    items, appear, seats, name_by_slug, seen = [], {}, {}, {}, set()
    mismatch = 0
    for mid, mdate in meetings:
        vdata = try_json(f"{NOTUBIZ_API}/agenda_items/votings?meeting_id={mid}&format=json&version=1.21")
        time.sleep(SLEEP)
        votings = (vdata or {}).get("votings") or []
        if not votings:
            continue
        breakdown = notubiz_parse_meeting(try_text(f"{portal}/vergadering/{mid}") or "")
        time.sleep(SLEEP)
        for v in votings:
            cid = v.get("id")
            if cid in seen:
                continue
            fr_votes = breakdown.get(cid)
            if not fr_votes:
                continue   # no per-fractie breakdown on the portal -> can't attribute the role_ids; skip
            seen.add(cid)
            td = v.get("type_data") or {}
            # Cross-check the parsed per-fractie totals against the API's own per-member votes.
            api_for = sum(1 for x in (td.get("votes") or []) if x.get("vote") == "in_favor")
            api_ag = sum(1 for x in (td.get("votes") or []) if x.get("vote") == "against")
            if (sum(fv["agree"] for fv in fr_votes.values()),
                    sum(fv["disagree"] for fv in fr_votes.values())) != (api_for, api_ag):
                mismatch += 1
            votes = {}
            for name, fv in fr_votes.items():
                name = NOTUBIZ_ALIASES.get(name, name)
                if name in NOTUBIZ_SKIP:
                    continue
                s = slugify(name)
                name_by_slug.setdefault(s, name)
                cell = votes.setdefault(s, {"agree": 0, "disagree": 0, "abstain": 0})
                cell["agree"] += fv["agree"]
                cell["disagree"] += fv["disagree"]
                cell["abstain"] += fv["abstain"]
            for s, cell in votes.items():
                appear[s] = appear.get(s, 0) + 1
                seats[s] = max(seats.get(s, 0), cell["agree"] + cell["disagree"])
            title = (td.get("title") or "").strip()
            result, label = notubiz_result(td.get("voting_result"))
            items.append({
                "id": cid,
                "date": mdate,
                "title": title,
                "type": notubiz_classify(title, td.get("voting_type")),
                "result": result,
                "resultLabel": label,
                "source": f"{portal}/vergadering/{mid}",
                "votes": votes,
            })
    if mismatch:
        print(f"  WARN: {mismatch} stemming(en) waar portal- en API-totalen verschillen")
    if not items:
        return None

    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(v["agree"] for v in m["votes"].values()),
                       "disagree": sum(v["disagree"] for v in m["votes"].values())}
    # Columns ordered by fractie size (biggest first), then activity, then name.
    order = sorted(appear, key=lambda s: (-seats.get(s, 0), -appear[s], name_by_slug[s].lower()))
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  {len(items)} stemmingen; {len(appear)} fracties; {by_type}")
    return {"parties": [{"slug": s, "name": name_by_slug[s]} for s in order], "moties": items}


def province_granularity(p):
    """Vote detail level, for the frontend: "member" = real per-fractie counts (GO, Limburg
    "stemmen") so "ruwe getallen" are meaningful; "fractie" = faction-level V/T only
    (NH "stemverhouding"), where counts are just 1/0 and must not be shown as tallies."""
    if p["vendor"] == "ek":   # faction-level voor/tegen, no seat counts
        return "fractie"
    if p["vendor"] == "ibabs" and p.get("votes", "stemverhouding") == "stemverhouding":
        return "fractie"
    return "member"


ADAPTERS = {"go": collect_go, "ibabs": collect_ibabs, "tk": collect_tk, "ek": collect_ek,
            "ep": collect_ep, "notubiz": collect_notubiz}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # ONLY=key1,key2 re-collects just those scopes and reuses the existing data file (availability +
    # style) for the rest — fast iteration without re-fetching/overwriting the other scopes. The
    # weekly Action runs with no ONLY, so it does the full refresh.
    only = {k.strip() for k in os.environ.get("ONLY", "").split(",") if k.strip()}
    scopes_by_cat = {}   # category key -> list of {key, name, available}
    default = None
    for p in SOURCES:
        catkey = p.get("category", "provinciale-staten")
        if only and p["key"] not in only:
            available = (DATA_DIR / f"{p['key']}.json").exists()
            print(f"== {p['name']} == (skipped; reuse existing data: {available})")
            scopes_by_cat.setdefault(catkey, []).append(
                {"key": p["key"], "name": p["name"], "available": available, "style": p.get("style", {})})
            if available and default is None:
                default = {"category": catkey, "scope": p["key"]}
            continue
        print(f"== {p['name']} ({p['vendor']}) ==")
        adapter = ADAPTERS.get(p["vendor"])
        res = None
        if adapter:
            try:
                res = adapter(p)
            except Exception as e:
                print(f"  ERROR: {e}")
        available = bool(res and res["moties"])
        if available:
            out = {
                "meta": {
                    "province": p["name"],
                    "body": p.get("body", "Provinciale Staten"),
                    "term": p["term_label"],
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": p.get("public", p["base"]),
                    "sourceName": p.get("sourceName", ""),   # overrides the "Bron:" label (e.g. EP via HowTheyVote)
                    "license": p.get("license", ""),
                    "style": p.get("style", {}),
                    "note": p.get("note", ""),
                    "granularity": province_granularity(p),
                    "counts": {"moties": len(res["moties"]), "parties": len(res["parties"])},
                },
                "parties": res["parties"],
                "moties": res["moties"],
            }
            # Large datasets (TK) write minified to keep the static file small.
            dump = (json.dumps(out, ensure_ascii=False, separators=(",", ":")) if p.get("compact")
                    else json.dumps(out, ensure_ascii=False, indent=2))
            (DATA_DIR / f"{p['key']}.json").write_text(dump, encoding="utf-8")
            by_type = {}
            for m in res["moties"]:
                by_type[m["type"]] = by_type.get(m["type"], 0) + 1
            print(f"  wrote {p['key']}.json: {len(res['moties'])} stemmingen, "
                  f"{len(res['parties'])} fracties, {by_type}")
        else:
            print("  (no data — marked unavailable)")
        scopes_by_cat.setdefault(catkey, []).append(
            # style travels in the index so the frontend can theme the header *before* the (large)
            # data file finishes loading — avoids a flash of the previous/default colour.
            {"key": p["key"], "name": p["name"], "available": available, "style": p.get("style", {})})
        if available and default is None:
            default = {"category": catkey, "scope": p["key"]}

    # catalog.json — the frontend's "pick category -> pick scope" index.
    categories = []
    for catkey in CATEGORY_ORDER:
        scopes = scopes_by_cat.get(catkey)
        if not scopes:
            continue
        meta = CATEGORY_META[catkey]
        categories.append({"key": catkey, "name": meta["name"], "scopeNoun": meta["scope_noun"],
                           "blurb": meta["blurb"], "scopes": scopes})
    (DATA_DIR / "catalog.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "default": default, "categories": categories},
        ensure_ascii=False, indent=2), encoding="utf-8")
    avail = [s["key"] for c in categories for s in c["scopes"] if s["available"]]
    print(f"\nWrote catalog.json: categories = {[c['key'] for c in categories]}; available = {avail}")


if __name__ == "__main__":
    sys.exit(main())
