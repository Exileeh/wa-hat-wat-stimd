#!/usr/bin/env python3
"""
Collector — Provinciale Staten van Fryslân ("Wa hat wat stimd?").

Pulls every hoofdelijke stemming of the plenary Provinsjale Steaten from Notubiz, aggregates the
per-member votes to exact per-fractie counts, joins each stemming to its Moasje/Amendemint document
and its indieners, and writes two static files the site reads:

  data/fryslan.json   {meta, parties, moties}   — the snapshot the page loads first
  data/roles.json     {roles: {role_id: slug}}  — lets the browser aggregate NEW meetings live
                                                  straight from api.notubiz.nl (CORS is open there)

Three public Notubiz surfaces, no token (see ../docs/notubiz.md):
  1. events API    GET api.notubiz.nl/events?organisation_id=&date_from=&date_to=&page=&version=1.21
                   -> meetings; keep gremium.id == the plenary gremium with agenda_item_count > 0.
  2. votings API   GET api.notubiz.nl/agenda_items/votings?meeting_id=&version=1.21
                   -> per stemming: id, title, voting_type, voting_result, per-MEMBER votes (role_id).
  3. portal HTML   https://fryslan.notubiz.nl/vergadering/<mid>
                   -> per stemming (<div id="chart_<id>">, id == votings API `id`) each fractie with
                      its members tagged <li class="in_favor|against">. Names are used in memory only
                      (to learn role_id -> fractie) and never written: the dataset is party-level.
  4. module items  GET api.notubiz.nl/modules/6/items?organisation_id=  (the "Moasjes en amendeminten"
                   module) -> per motion: title, PDF document, agenda item, indienende partijen.
     parties       GET api.notubiz.nl/organisations/<id>/parties -> party id -> name.
  5. uitslag PDF   GET api.notubiz.nl/events/meetings/<mid> -> the document "Útslach stimming <datum>"
                   under the agenda item "Stimming". Since 2026-05-27 the griffie no longer registers
                   votes in Notubiz's voting module (2. and 3. are empty); this PDF holds one
                   screenshot of the voting display per stemming and is read by uitslag_pdf.py.

The API path is stdlib only. Reading the PDFs needs the optional packages in
collector/requirements-pdf.txt; without them those meetings are reported and skipped.

NOTE: api.notubiz.nl silently drops connections from GitHub's cloud runners (geo/datacenter
filtering, no exceptions — 2026-09). From a Dutch connection everything works. When a run cannot
reach the source it keeps the previous data file, prints KNOWN ISSUE and exits 0; only a NEW
problem, or data older than STALE_AFTER_DAYS, turns the run red.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import uitslag_pdf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "fryslan.json"
ROLES_FILE = DATA_DIR / "roles.json"

SOURCE = {
    "key": "fryslan",
    "name": "Fryslân",
    "body": "Provinciale Staten",
    "organisation_id": 822,
    "gremium_id": 430,             # "Provinsjale Steaten" = the plenary gremium (commissies excluded)
    "module_id": 6,                # "Moties" module, on the portal "Moasjes en amendeminten"
    "slug": "fryslan",             # portal host: fryslan.notubiz.nl
    "public": "https://fryslan.notubiz.nl",
    "term_start": (2023, 3, 29),   # PS election 15 March 2023, geïnstalleerd 29 March
    "term_label": "2023-2027",
    "style": {"accent": "#c8102e", "headerBg": "#2a0a0c"},   # Frysk read (pompeblêd-rood)
    "license": "Open data - Provincie Fryslân (Notubiz vergaderportaal)",
    "note": "Stemmen zijn hoofdelijk (per lid) geregistreerd en hier per fractie met exacte "
            "aantallen samengevat (aangenomen én verworpen). Agendapunten zonder hoofdelijke "
            "stemming (bijv. bij acclamatie) en leden die niet deelnamen, staan niet in de telling.",
    # Shown on the page only once the snapshot is older than NOTICE_AFTER_DAYS.
    "known_issue": "De dagelijkse verversing kon de bron een tijd niet bereiken (Notubiz blokkeert "
                   "cloudservers). Hieronder staat de laatste stand; nieuwere stemmingen worden "
                   "waar mogelijk live bijgeladen.",
}

NOTUBIZ_API = "https://api.notubiz.nl"
API_VERSION = "1.21"   # mandatory: other versions silently reject every parameter

# Merge spelling variants into one column (the portal writes "Partij voor de Dieren" where the
# stemmingen use "PvdD"). Fracties that genuinely existed separately are NOT merged.
NOTUBIZ_ALIASES = {
    "Partij voor de Dieren": "PvdD",
    # One member: elected for FVD (listed as indiener under that name until mid-2024), votes registered
    # as "Steatelid Van Dijk" throughout the term. One column, one name.
    "FVD": "Van Dijk (FvD)",
    "Steatelid Van Dijk": "Van Dijk (FvD)",
}
# Labels that are not a real fractie (the absence of one) -> not a voting column.
NOTUBIZ_SKIP = {"Geen partij", "Gedeputeerde Staten"}

HEADERS = {
    "User-Agent": "wa-hat-wat-stimd collector (open-data overview; contact via GitHub)",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}
SLEEP = 0.3  # be polite between requests


# --- HTTP ---------------------------------------------------------------------------------------

# Notubiz blocks GitHub's cloud runners (docs/notubiz.md section 4), so the workflow points
# NOTUBIZ_RELAY at a small Vercel function in Frankfurt that fetches on our behalf
# (api/notubiz.py). Unset — a local run, refresh-local.ps1 — and every request goes straight out,
# byte for byte as before.
RELAY = os.environ.get("NOTUBIZ_RELAY", "").strip()
RELAY_KEY = os.environ.get("RELAY_KEY", "")


def open_url(url, timeout, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    if RELAY:
        url = f"{RELAY}?u={urllib.parse.quote(url, safe='')}"
        headers["X-Relay-Key"] = RELAY_KEY
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def range_total(response):
    """Total size behind a 206, or None when the whole body already arrived."""
    if response.status != 206:
        return None
    header = (response.headers.get("Content-Range") or "").rsplit("/", 1)
    return int(header[1]) if len(header) == 2 and header[1].isdigit() else None


def http(url, binary=False):
    timeout = 90 if binary else 30
    if RELAY:
        timeout += 60          # one hop more, and the relay re-reads the source for every chunk
    with open_url(url, timeout) as r:
        data = r.read()
        total = range_total(r)

    # A Vercel response body is capped at 4.5 MB, so the relay hands anything larger (the Útslach
    # PDFs; one day the module list, now at 3.4 MB) over in pieces.
    while total is not None and len(data) < total:
        with open_url(url, timeout, {"Range": f"bytes={len(data)}-"}) as r:
            part = r.read()
            total = range_total(r) or total
        if not part:
            raise urllib.error.URLError(f"relay sent an empty chunk at {len(data)} of {total} bytes")
        data += part

    return data if binary else data.decode("utf-8", "replace")


# Why requests failed, so a run that collects nothing names its own cause ("Network is
# unreachable" = blocked runner) instead of printing a bare "no data".
_HTTP_LOG = {}


def note_failure(kind):
    _HTTP_LOG[kind] = _HTTP_LOG.get(kind, 0) + 1


def http_log_summary():
    return ", ".join(f"{k} x{v}" for k, v in sorted(_HTTP_LOG.items(), key=lambda kv: -kv[1]))


RETRY_STATUS = {429, 500, 502, 503, 504}


def fetch(url, tries=3, binary=False):
    """GET with retries on transient errors; None on a permanent 4xx or after `tries` failures."""
    for attempt in range(tries):
        try:
            return http(url, binary)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or attempt + 1 == tries:
                note_failure(f"HTTP {e.code}")
                return None
            try:
                wait = min(float(e.headers.get("Retry-After") or 0), 30.0)
            except (TypeError, ValueError):
                wait = 0.0
            time.sleep(max(wait, 2.0 * (attempt + 1)))
        except OSError as e:   # URLError, TimeoutError, dropped connections, …
            if attempt + 1 == tries:
                reason = getattr(e, "reason", None)
                note_failure(f"{type(e).__name__} ({reason})" if reason else type(e).__name__)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def try_json(url):
    txt = fetch(url)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        note_failure("HTTP 200 but not JSON")
        return None


def try_text(url):
    return fetch(url)


def try_bytes(url):
    return fetch(url, binary=True)


def api(path, **params):
    params.update(format="json", version=API_VERSION)
    return f"{NOTUBIZ_API}/{path}?{urllib.parse.urlencode(params)}"


# --- Helpers ------------------------------------------------------------------------------------

def slugify(name):
    """Party slug (column key). Kept byte-identical to the original site so pinned ids and
    external links stay valid: accents are dropped ("Fryslân" -> "frysln")."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s


def party_slug(name):
    name = NOTUBIZ_ALIASES.get(name, name)
    return None if name in NOTUBIZ_SKIP else slugify(name)


def norm_text(s):
    """Lower-case ASCII, punctuation stripped — for fuzzy title matching."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def title_tokens(s):
    return {t for t in norm_text(s).split() if len(t) > 2}


TITLE_NUMBER = re.compile(
    r"^\s*(?:moasje|moasie|amendemint|motie|amendement)\s*(?:frjemd|fremd)?\s*\(?(?:\d+-[MA]-)?0*(\d+)\)?",
    re.I)


def title_number(title):
    """The motion number embedded in a title: "Moasje 9 (CDA en BBB): …" -> "9",
    "03 Moasje 09 - …" -> "9", "Moasje 6-M-21: …" -> "21", "Motie (26): …" -> "26"."""
    m = TITLE_NUMBER.match(re.sub(r"^\s*\d+\s+", "", title or ""))
    return m.group(1) if m else None


FRJEMD_RE = re.compile(r"^\s*(?:\d+[a-z]?\s+)?(?:moasje|moasie|motie)\s*(?:frjemd|fremd)\b", re.I)


def notubiz_classify(title, voting_type):
    """Item type. A "Moasje frjemd" (a motion on a subject not on the agenda) is its own type and is
    recognised from the title first — the API files it as a plain motion or even a council proposal.
    Otherwise prefer the API's explicit `voting_type` (reliable for Fryslân); fall back to the
    (Frisian) title: "Moasje"/"Amendemint"/"Oarderfoarstel"."""
    if FRJEMD_RE.match(title or ""):
        return "frjemd"
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
    if "amendement" in low or "amendemint" in low:
        return "amendement"
    if "motie" in low or "moasje" in low or "moasie" in low:
        return "motie"
    if "statenvoorstel" in low or "besluit" in low or "voordracht" in low or "voarstel" in low:
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


# --- Notubiz: meetings, votes, portal ---------------------------------------------------------------

def notubiz_events(org_id, gremium_id, term_start, end):
    """Page the events API over the term window; return [(meeting_id, date)] for the plenary
    gremium's meetings that carry agenda items (recesses etc. have agenda_item_count 0)."""
    meetings, page = [], 1
    while page <= 60:
        data = try_json(api("events", organisation_id=org_id,
                            date_from=term_start.isoformat() + " 00:00:00",
                            date_to=end.isoformat() + " 23:59:59", page=page))
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
    """Parse a portal vergadering page into {chart_id: {fractie: {agree, disagree, abstain,
    members: {name: vote}}}}. Each stemming is a <div id="chart_<id>"> followed by a votes block in
    which each fractie is <li>NAME<ul> …<li class="in_favor|against">member</li>… </ul></li>.
    Counting the member classes gives exact per-fractie tallies; a fractie in the 'verdeeld' side
    yields a real split. Member names stay in memory (role learning) and are never written."""
    out = {}
    for m in re.finditer(r'id="chart_(\d+)"[^>]*></div>(.*?)'
                         r'(?=<div class="votes_chart"|id="chart_\d+"|$)', html, re.S):
        cid, seg, votes = int(m.group(1)), m.group(2), {}
        for fm in re.finditer(r'<li>\s*([^<]+?)\s*<ul>(.*?)</ul>\s*</li>', seg, re.S):
            name = re.sub(r"\s+", " ", fm.group(1)).strip()
            inner = fm.group(2)
            members = {re.sub(r"\s+", " ", mm.group(2)).strip(): mm.group(1)
                       for mm in re.finditer(r'<li class="(in_favor|against)">([^<]+)</li>', inner)}
            agree = sum(1 for v in members.values() if v == "in_favor")
            disagree = sum(1 for v in members.values() if v == "against")
            if not name or not (agree or disagree):
                continue
            v = votes.setdefault(name, {"agree": 0, "disagree": 0, "abstain": 0, "members": {}})
            v["agree"] += agree
            v["disagree"] += disagree
            v["members"].update(members)
        if votes:
            out[cid] = votes
    return out


# --- Notubiz: Moasjes en amendeminten module (documents + indieners) --------------------------------

def module_attr(item, attr_id):
    for a in item.get("attributes", []):
        if a.get("id") == attr_id:
            return [v.get("content") for v in a.get("values", [])]
    return []


def load_module_items(p):
    """All items of the motions module, grouped by the agenda item they were handled under, plus
    the party id -> name map. Returns (by_agenda_item, by_date, party_names) — empty on failure,
    in which case the stemmingen simply get no document/indieners this run."""
    data = try_json(api(f"modules/{p['module_id']}/items", organisation_id=p["organisation_id"]))
    parties = try_json(api(f"organisations/{p['organisation_id']}/parties"))
    time.sleep(SLEEP)
    items = (data or {}).get("items") or []
    party_names = {pt["id"]: pt["name"] for pt in (parties or {}).get("parties", []) if pt.get("id")}
    by_agenda, by_date = {}, {}
    for it in items:
        rec = {
            "id": it.get("id"),
            "title": (module_attr(it, 1) or [""])[0] or "",
            "type": ((module_attr(it, 45) or [""])[0] or "").strip().lower(),
            "date": ((module_attr(it, 15) or [""])[0] or "")[:10],
            "number": str((module_attr(it, 26) or [""])[0] or "").lstrip("0"),
            "parties": [x for x in module_attr(it, 37) if isinstance(x, int)],
            "document": None,
        }
        for d in module_attr(it, 2):
            doc = (d or {}).get("document") if isinstance(d, dict) else None
            if doc and doc.get("id"):
                rec["document"] = {"id": doc["id"], "title": doc.get("title") or rec["title"]}
                break
        for ag in module_attr(it, 54):
            if isinstance(ag, int):
                by_agenda.setdefault(ag, []).append(rec)
        if rec["date"]:
            by_date.setdefault(rec["date"], []).append(rec)
    print(f"  module 'Moasjes en amendeminten': {len(items)} items, {len(party_names)} partijen")
    return by_agenda, by_date, party_names


def module_type_matches(rec_type, item_type):
    """Module attribute 45 ("Moasje", "Moasje frjemd", "Amendemint", spelling variants) vs our type.
    The module is not consistent about "frjemd", so both motion types accept any moasje record;
    `prefer_frjemd` narrows that when it can."""
    if item_type in ("motie", "frjemd"):
        return rec_type.startswith("moasje") or rec_type.startswith("motie")
    if item_type == "amendement":
        return rec_type.startswith("amendem")
    return False


def is_frjemd_type(rec_type):
    return "frjemd" in rec_type or "fremd" in rec_type


def prefer_frjemd(cands, item_type):
    """For a frjemd stemming keep only the module records typed frjemd, when there are any."""
    if item_type != "frjemd":
        return cands
    return [c for c in cands if is_frjemd_type(c["type"])] or cands


def match_module_item(title, item_type, candidates):
    """Pick the module item for a stemming: same type, then the same motion number, else the unique
    best title-token overlap (>= 2 shared tokens). None when nothing is convincing."""
    cands = [c for c in candidates if module_type_matches(c["type"], item_type)] or list(candidates)
    cands = prefer_frjemd(cands, item_type)
    if not cands:
        return None
    n = title_number(title)
    if n:
        by_n = [c for c in cands if c["number"] == n or title_number(c["title"]) == n]
        if len(by_n) == 1:
            return by_n[0]
        if by_n:
            cands = by_n
    want = title_tokens(title)
    scored = sorted(((len(want & title_tokens(c["title"])), c) for c in cands),
                    key=lambda x: -x[0])
    if scored and scored[0][0] >= 2 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def document_url(portal, doc):
    """Portal URL of a document: https://fryslan.notubiz.nl/document/<id>/1/<title-slug>."""
    slug = urllib.parse.quote(re.sub(r"\s+", "+", (doc.get("title") or "document").strip()), safe="+")
    return f"{portal}/document/{doc['id']}/1/{slug}"


# --- Notubiz: "Útslach stimming" PDF (meetings without digital votes) ------------------------------------

def is_uitslag_doc(title):
    t = uitslag_pdf.squash(title)
    return "tslachstimming" in t or "uitslagstemming" in t


def notubiz_meeting_detail(mid):
    """From events/meetings/<mid>:
      * the "Útslach stimming" document {id, title} or None,
      * {agenda point number (int): title} — names the besluit votes read from the PDF,
      * {agenda item id: {"nr": title_prefix, "title": …}} for every numbered agenda point — the
        votings API's `parent.id` points at these, so each stemming can be filed under its
        wurklistpunt. Nodes without a number or title (section headers, the votings themselves) are
        skipped."""
    data = try_json(api(f"events/meetings/{mid}"))
    found = {"doc": None}
    titles, by_id = {}, {}

    def walk(items):
        for it in items or []:
            td = it.get("type_data") or {}
            prefix = str(td.get("title_prefix") or "").strip()
            title = ""
            for a in td.get("attributes") or []:
                if a.get("id") == 1 and a.get("value"):
                    title = re.sub(r"\s+", " ", str(a["value"])).strip()
                    break
            if prefix and title and it.get("id"):
                by_id[it["id"]] = {"nr": prefix, "title": title}
                if prefix.isdigit():
                    titles.setdefault(int(prefix), title)
            for d in it.get("documents") or []:
                if found["doc"] is None and d.get("id") and is_uitslag_doc(d.get("title") or ""):
                    found["doc"] = {"id": d["id"], "title": d.get("title") or ""}
            walk(it.get("agenda_items"))

    walk(((data or {}).get("meeting") or {}).get("agenda_items"))
    return found["doc"], titles, by_id


def agenda_for_number(nr, by_id):
    """{id, nr, title} of the agenda point whose number is `nr` (int, as read from a PDF page
    title), or None."""
    if nr is None:
        return None
    for aid, a in by_id.items():
        if a["nr"].isdigit() and int(a["nr"]) == nr:
            return {"id": aid, **a}
    return None


def match_pdf_module_item(info, title, candidates):
    """Module item for a PDF page (`info` = uitslag_pdf.title_info): same type, then the same
    motion number (and the same agenda point when that still leaves several), else the best
    space-less title similarity. None when nothing is convincing."""
    cands = [c for c in candidates if module_type_matches(c["type"], info["type"])]
    cands = prefer_frjemd(cands, info["type"])
    if not cands:
        return None
    if info["number"]:
        by_n = [c for c in cands if title_number(c["title"]) == info["number"]]
        # A re-vote ("Werstimming … wurklistpunt 03 Moasje 19") names the ORIGINAL agenda point,
        # so only a first vote may be narrowed down by today's agenda number.
        if len(by_n) > 1 and info["agenda"] is not None and not info["revote"]:
            by_n = [c for c in by_n if c["number"] == str(info["agenda"])] or by_n
        if len(by_n) == 1 and not info["revote"]:
            return by_n[0]
        if by_n:
            cands = by_n
    scored = sorted(((uitslag_pdf.similarity(title, c["title"]), c) for c in cands),
                    key=lambda x: -x[0])
    return scored[0][1] if scored[0][0] >= 0.6 else None


def collect_pdf_meeting(p, mid, mdate, doc, by_date, all_recs, agenda_titles, agenda_by_id,
                        party_names, name_by_slug, primary):
    """Stemmingen of one meeting read from its "Útslach stimming" PDF, in the same shape as the
    API path produces. Returns (items, stats); stats["rejected"] lists pages the reader would
    not vouch for (never guessed, see uitslag_pdf.read_page)."""
    portal = p["public"]
    pdf_url = document_url(portal, doc)
    raw = try_bytes(pdf_url)
    if not raw:
        return [], {"error": "pdf niet opgehaald", "pages": 0, "withdrawn": 0, "rejected": [],
                    "matched": 0, "unmatched": 0}
    pages = uitslag_pdf.parse_pdf(raw, primary, list(party_names.values()))
    items, rejected = [], []
    stats = {"pages": len(pages), "withdrawn": 0, "rejected": rejected, "matched": 0, "unmatched": 0}
    for pg in pages:
        if not pg["ok"]:
            if pg["warning"] == "ynlutsen":
                stats["withdrawn"] += 1
            elif pg["votes"] or pg["totals"]:   # the cover page has neither: not a stemming
                rejected.append(pg)
            continue
        info = pg["info"]
        votes = {}
        for name, fv in pg["votes"].items():
            s = party_slug(name)
            if not s or not (fv["agree"] or fv["disagree"] or fv["abstain"]):
                continue   # like the API path: a fractie that was absent gets no cell
            name_by_slug.setdefault(s, NOTUBIZ_ALIASES.get(name, name))
            votes[s] = {"agree": fv["agree"], "disagree": fv["disagree"], "abstain": fv["abstain"]}
        if not votes:
            continue
        voor, tegen, _ = pg["totals"]
        if voor > tegen:
            result, label = "accepted", "Aangenomen"
        elif voor < tegen:
            result, label = "rejected", "Verworpen"
        else:
            result, label = "tie", "Staken van stemmen"
        title = pg["title"]
        item = {
            "id": doc["id"] * 1000 + pg["page"],   # numeric and stable: document id + page
            "date": mdate,
            "meetingId": mid,
            "title": title,
            "type": info["type"],
            "result": result,
            "resultLabel": label,
            "source": f"{portal}/vergadering/{mid}",
            "uitslag": pdf_url,
            "votes": votes,
        }
        agenda = agenda_for_number(info["agenda"], agenda_by_id)
        if agenda:
            item["agenda"] = agenda
        rec = None
        if info["type"] in ("motie", "frjemd", "amendement"):
            # A re-vote concerns a motion from an earlier meeting: search the whole module.
            pool = all_recs if info["revote"] else by_date.get(mdate, [])
            rec = match_pdf_module_item(info, title, pool)
            stats["matched" if rec else "unmatched"] += 1
        if rec:
            item["title"] = ("Werstimming: " if info["revote"] else "") + rec["title"]
            if rec["document"]:
                item["document"] = document_url(portal, rec["document"])
                item["documentTitle"] = rec["document"]["title"]
            ind = []
            for pid in rec["parties"]:
                s = party_slug(party_names.get(pid, ""))
                if s and s not in ind:
                    ind.append(s)
            if ind:
                item["indieners"] = ind
        elif info["type"] == "besluit" and info["agenda"] in agenda_titles:
            final = "finalebeslut" in uitslag_pdf.squash(title)
            item["title"] = f"{info['agenda']:02d} {agenda_titles[info['agenda']]}" + \
                            (" - Finale beslút" if final else "")
        items.append(item)
    return items, stats


# --- Collect ------------------------------------------------------------------------------------

def collect(p):
    """Discover plenary meetings, join votings API metadata to the portal's per-fractie breakdown,
    attach documents/indieners from the motions module, and learn role_id -> fractie.
    Returns ({parties, moties}, roles) or (None, None) when nothing was collected."""
    org_id, gremium_id, portal = p["organisation_id"], p["gremium_id"], p["public"]
    meetings = notubiz_events(org_id, gremium_id, date(*p["term_start"]), date.today())
    print(f"  {len(meetings)} plenaire vergadering(en) met agendapunten in termijn")
    if not meetings:
        return None, None
    by_agenda, by_date, party_names = load_module_items(p)
    all_recs = [r for recs in by_date.values() for r in recs]

    items, appear, seats, name_by_slug, seen = [], {}, {}, {}, set()
    role_votes = {}      # role_id -> {voting id: vote}
    member_votes = {}    # (fractie slug, member name) -> {voting id: vote}
    mismatch = doc_hits = doc_miss = 0
    pdf_meetings, pdf_skipped = 0, []
    for mid, mdate in meetings:
        # Agenda of the meeting: files every stemming under its wurklistpunt, and (for meetings
        # without digital votes) names the "Útslach stimming" PDF and the besluit titles.
        uitslag_doc, agenda_titles, agenda_by_id = notubiz_meeting_detail(mid)
        time.sleep(SLEEP)
        vdata = try_json(api("agenda_items/votings", meeting_id=mid))
        time.sleep(SLEEP)
        votings = (vdata or {}).get("votings") or []
        before = len(items)
        if votings:
            breakdown = notubiz_parse_meeting(try_text(f"{portal}/vergadering/{mid}") or "")
            time.sleep(SLEEP)
        for v in votings:
            cid = v.get("id")
            if cid in seen:
                continue
            fr_votes = breakdown.get(cid)
            if not fr_votes:
                continue   # no per-fractie breakdown on the portal (acclamatie / no roll-call)
            seen.add(cid)
            td = v.get("type_data") or {}
            api_votes = td.get("votes") or []
            api_for = sum(1 for x in api_votes if x.get("vote") == "in_favor")
            api_ag = sum(1 for x in api_votes if x.get("vote") == "against")
            if (sum(fv["agree"] for fv in fr_votes.values()),
                    sum(fv["disagree"] for fv in fr_votes.values())) != (api_for, api_ag):
                mismatch += 1
            votes = {}
            for name, fv in fr_votes.items():
                s = party_slug(name)
                if not s:
                    continue
                name_by_slug.setdefault(s, NOTUBIZ_ALIASES.get(name, name))
                cell = votes.setdefault(s, {"agree": 0, "disagree": 0, "abstain": 0})
                cell["agree"] += fv["agree"]
                cell["disagree"] += fv["disagree"]
                cell["abstain"] += fv["abstain"]
                for member, vote in fv["members"].items():
                    member_votes.setdefault((s, member), {})[cid] = vote
            for x in api_votes:
                if x.get("role_id") and x.get("vote") in ("in_favor", "against"):
                    role_votes.setdefault(x["role_id"], {})[cid] = x["vote"]
            title = (td.get("title") or "").strip()
            itype = notubiz_classify(title, td.get("voting_type"))
            result, label = notubiz_result(td.get("voting_result"))
            agenda_id = (v.get("parent") or {}).get("id")
            item = {
                "id": cid,
                "date": mdate,
                "meetingId": mid,
                "title": title,
                "type": itype,
                "result": result,
                "resultLabel": label,
                "source": f"{portal}/vergadering/{mid}",
                "votes": votes,
            }
            if agenda_id in agenda_by_id:
                item["agenda"] = {"id": agenda_id, **agenda_by_id[agenda_id]}
            if itype in ("motie", "frjemd", "amendement"):
                rec = match_module_item(title, itype, by_agenda.get(agenda_id, [])) \
                    or match_module_item(title, itype, by_date.get(mdate, []))
                if rec:
                    if rec["document"]:
                        item["document"] = document_url(portal, rec["document"])
                        item["documentTitle"] = rec["document"]["title"]
                    ind = []
                    for pid in rec["parties"]:
                        s = party_slug(party_names.get(pid, ""))
                        if s and s not in ind:
                            ind.append(s)
                    if ind:
                        item["indieners"] = ind
                    doc_hits += 1
                else:
                    doc_miss += 1
            items.append(item)

        if len(items) == before:
            # No digital stemmingen for this meeting: fall back to the griffie's "Útslach stimming"
            # PDF (since 2026-05-27 the only place the hoofdelijke stemmingen are published).
            doc = uitslag_doc
            if doc:
                if not uitslag_pdf.available():
                    pdf_skipped.append(mdate)
                else:
                    new, stats = collect_pdf_meeting(p, mid, mdate, doc, by_date, all_recs,
                                                     agenda_titles, agenda_by_id, party_names,
                                                     name_by_slug, list(name_by_slug.values()))
                    items.extend(new)
                    doc_hits += stats["matched"]
                    doc_miss += stats["unmatched"]
                    pdf_meetings += 1
                    print(f"  {mdate}: {len(new)} stemmingen uit PDF '{doc['title']}' "
                          f"({stats['pages']} pagina's, {stats['withdrawn']} ynlutsen, "
                          f"{len(stats['rejected'])} afgekeurd)")
                    for pg in stats["rejected"]:
                        print(f"    WARN: pagina {pg['page']} afgekeurd: {pg['warning']} | {pg['title'][:70]}")
                    if stats.get("error"):
                        print(f"    WARN: {stats['error']}")

        for item in items[before:]:
            for s, cell in item["votes"].items():
                appear[s] = appear.get(s, 0) + 1
                seats[s] = max(seats.get(s, 0), cell["agree"] + cell["disagree"])
    if mismatch:
        print(f"  WARN: {mismatch} stemming(en) waar portal- en API-totalen verschillen")
    if pdf_meetings:
        print(f"  {pdf_meetings} vergadering(en) via de 'Útslach stimming'-PDF (geen digitale stemmingen in Notubiz)")
    if pdf_skipped:
        print(f"  WARN: {len(pdf_skipped)} vergadering(en) alleen met een 'Útslach stimming'-PDF overgeslagen "
              f"({', '.join(pdf_skipped)}): installeer collector/requirements-pdf.txt "
              f"(ontbreekt: {', '.join(uitslag_pdf.missing())})")
    if not items:
        return None, None

    items.sort(key=lambda m: (m["date"], m["title"]), reverse=True)
    for m in items:
        m["totals"] = {"agree": sum(v["agree"] for v in m["votes"].values()),
                       "disagree": sum(v["disagree"] for v in m["votes"].values())}
    # Columns ordered by fractie size (biggest first), then activity, then name.
    order = sorted(appear, key=lambda s: (-seats.get(s, 0), -appear[s], name_by_slug[s].lower()))
    unknown = sorted({s for m in items for s in m.get("indieners", []) if s not in name_by_slug})
    if unknown:
        print(f"  WARN: indieners zonder eigen kolom (partij zonder stemmen in deze termijn): {unknown}")
    by_type = {}
    for m in items:
        by_type[m["type"]] = by_type.get(m["type"], 0) + 1
    print(f"  {len(items)} stemmingen; {len(appear)} fracties; {by_type}")
    print(f"  documenten/indieners: {doc_hits} gekoppeld, {doc_miss} niet gevonden "
          f"({100 * doc_hits // max(1, doc_hits + doc_miss)}% van moties+amendementen)")
    roles = learn_roles(role_votes, member_votes)
    return {"parties": [{"slug": s, "name": name_by_slug[s]} for s in order], "moties": items}, roles


ROLE_MIN_SHARED = 20   # a role needs this many votings in common with a member before we trust it


def learn_roles(role_votes, member_votes):
    """role_id -> fractie slug. The API tags each vote with an anonymous role_id; the portal names
    the member per vote. A role's vote pattern over the term matches exactly one member's pattern
    (members of the same fractie may be indistinguishable — that is fine, we only need the fractie).
    Unmapped roles (too few shared votings, or a tie between fracties) are listed, not guessed."""
    roles, unmapped = {}, []
    for rid, rv in role_votes.items():
        best = []
        for (slug, _name), mv in member_votes.items():
            shared = set(rv) & set(mv)
            if len(shared) < ROLE_MIN_SHARED:
                continue
            same = sum(1 for k in shared if rv[k] == mv[k])
            best.append((same / len(shared), len(shared), slug))
        if not best:
            unmapped.append({"role_id": rid, "reason": "te weinig gezamenlijke stemmingen", "n": len(rv)})
            continue
        best.sort(reverse=True)
        top = best[0][0]
        slugs = {b[2] for b in best if b[0] == top}
        if len(slugs) != 1 or top < 0.9:
            unmapped.append({"role_id": rid, "reason": "geen eenduidige fractie", "candidates": sorted(slugs)})
            continue
        roles[str(rid)] = best[0][2]
    sizes = {}
    for s in roles.values():
        sizes[s] = sizes.get(s, 0) + 1
    print(f"  rollen: {len(roles)} gekoppeld aan een fractie, {len(unmapped)} niet; zetels: {sizes}")
    for u in unmapped:
        print(f"  WARN: rol {u['role_id']} niet gekoppeld: {u['reason']}")
    return {"roles": roles, "unmapped": unmapped, "seats": sizes}


# --- Regression guard + write -------------------------------------------------------------------------

STALE_AFTER_DAYS = 45    # an acknowledged breakage turns the run red anyway past this age
NOTICE_AFTER_DAYS = 14   # visitors see the known_issue notice only once the data is this old


def previous_state():
    """What the last good run left behind: (stemmingen count, generated_at) or (0, None)."""
    try:
        j = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return len(j.get("moties", [])), (j.get("meta") or {}).get("generated_at")
    except (OSError, ValueError):
        return 0, None


def data_age_days(generated_at):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(generated_at)).days
    except (TypeError, ValueError):
        return None


def lost_data(prev_n, n):
    """True when a run lost more than a rounding error's worth of stemmingen (a griffie withdraws
    the odd item; a broken source loses far more)."""
    return n < prev_n - max(5, int(prev_n * 0.02))


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = SOURCE
    prev_n, prev_gen = previous_state()
    print(f"== {p['name']} (notubiz) ==")
    if RELAY:
        print(f"  requests go through the relay at {urllib.parse.urlparse(RELAY).netloc}"
              f"{'' if RELAY_KEY else ' — WARNING: RELAY_KEY is empty, it will answer 404'}")
    _HTTP_LOG.clear()
    res, roles = None, None
    try:
        res, roles = collect(p)
    except Exception as e:   # noqa: BLE001 — a crash must still reach the guard below
        print(f"  ERROR: {type(e).__name__}: {e}")
    n = len(res["moties"]) if res and res.get("moties") else 0
    failures = http_log_summary()
    note = f"; failed requests: {failures}" if failures else ""

    # Guard: never let a blocked or throttled source quietly delete or shrink the site. Keep the last
    # good file (the page shows its "bijgewerkt" date and, once old enough, the notice) and only turn
    # the run red for something NEW — or when the acknowledged problem has lasted too long.
    if prev_n and (n == 0 or lost_data(prev_n, n)):
        why = "no data at all" if n == 0 else f"{n} stemmingen, was {prev_n}"
        age = data_age_days(prev_gen)
        acknowledged = bool(p.get("known_issue")) and (age is None or age <= STALE_AFTER_DAYS)
        if acknowledged:
            print(f"  KNOWN ISSUE ({age}d stale): {why}{note}")
            print(f"  keeping the existing {DATA_FILE.name} from the last good run (not overwritten)")
            return 0
        print(f"  REGRESSION: {why}; the last good data is {age} days old{note}")
        print(f"  keeping the existing {DATA_FILE.name} from the last good run (not overwritten)")
        return 1
    if n == 0:
        print(f"  (no data — nothing written){note}")
        return 1

    out = {
        "meta": {
            "province": p["name"],
            "body": p["body"],
            "term": p["term_label"],
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": p["public"],
            "sourceName": "",
            "license": p["license"],
            "style": p["style"],
            "note": p["note"],
            "granularity": "member",
            "counts": {"moties": n, "parties": len(res["parties"]),
                       "fromPdf": sum(1 for m in res["moties"] if m.get("uitslag"))},
            "types": sorted({m["type"] for m in res["moties"]}),
            "organisationId": p["organisation_id"],
            "gremiumId": p["gremium_id"],
            "moduleId": p["module_id"],
            "knownIssue": p.get("known_issue", ""),
            "noticeAfterDays": NOTICE_AFTER_DAYS,
        },
        "parties": res["parties"],
        "moties": res["moties"],
    }
    DATA_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    roles_out = {"generated_at": out["meta"]["generated_at"], "term": p["term_label"],
                 "organisationId": p["organisation_id"], **(roles or {"roles": {}, "unmapped": []})}
    ROLES_FILE.write_text(json.dumps(roles_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  wrote {DATA_FILE.name}: {n} stemmingen, {len(res['parties'])} fracties{note}")
    print(f"  wrote {ROLES_FILE.name}: {len(roles_out['roles'])} rollen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
