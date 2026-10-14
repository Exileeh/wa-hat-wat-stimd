#!/usr/bin/env python3
"""
Vergaderstukken — fetch the agenda and documents of ONE Notubiz meeting as plain text.

Used to prepare a foarsittersmemo: the workflow .github/workflows/vergaderstukken.yml runs this
for a meeting the griffier picks, and commits the result to the branch `vergaderstukken`, where
it can be read without access to Notubiz (which blocks cloud machines, see docs/notubiz.md §4).

    python collector/vergaderstukken.py <meeting id | https://fryslan.notubiz.nl/vergadering/<id>> [--out DIR]

Writes DIR/<meeting id>/ (default DIR: ./stukken):
    agenda.md      date, time, gremium, every agenda item with its description and documents
    meeting.json   the raw events/meetings/<id> answer (for anything agenda.md leaves out)
    NN-<title>.txt the text of each document (PDF via pypdf, .docx via its XML); a document whose
                   text cannot be read is listed in agenda.md with the reason

Requests go through the same http()/relay as collect.py (NOTUBIZ_RELAY + RELAY_KEY), or straight
out when those are unset. Needs pypdf for PDFs; without it the PDFs are listed but not read.
"""

import argparse
import html
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (http helpers, relay, api())

PORTAL = collect.SOURCE["public"]


def meeting_id(arg):
    """'1501613', '.../vergadering/1501613' or '.../vergadering/1501613/titel' -> 1501613."""
    m = re.search(r"vergadering/(\d+)", arg) or re.fullmatch(r"\s*(\d+)\s*", arg)
    if not m:
        raise SystemExit(f"Geen vergadering-ID gevonden in {arg!r}")
    return int(m.group(1))


def strip_html(s):
    s = re.sub(r"<\s*(br|/p|/li|/div|/h\d)\s*/?>", "\n", str(s), flags=re.I)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def attributes(node):
    """[(label, text, id)] of the non-empty text attributes of a Notubiz node; id 1 is the title."""
    out = []
    for a in (node.get("type_data") or node).get("attributes") or []:
        v = a.get("value")
        if not isinstance(v, str) or not v.strip():
            continue
        out.append((a.get("label") or a.get("name") or f"attribuut {a.get('id')}",
                    strip_html(v), a.get("id")))
    return out


def title_of(node):
    for _label, text, aid in attributes(node):
        if aid == 1:
            return re.sub(r"\s+", " ", text)
    return ""


def safe_name(s, limit=80):
    s = re.sub(r"[^\w\-. ]+", "", s, flags=re.UNICODE).strip().replace(" ", "_")
    return (s[:limit] or "document").rstrip("._")


def document_url(doc):
    url = doc.get("url") or ""
    if url.startswith("https://") and re.match(r"https://(api|fryslan)\.notubiz\.nl/", url):
        return url
    return collect.document_url(PORTAL, doc)


def text_of(data):
    """(text, None) or (None, reason)."""
    if data[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "pypdf niet geïnstalleerd"
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [(p.extract_text() or "").strip() for p in reader.pages]
        except Exception as e:  # noqa: BLE001 — a broken PDF must not stop the other documents
            return None, f"PDF niet leesbaar ({type(e).__name__})"
        text = "\n\n".join(f"--- pagina {i} ---\n{t}" for i, t in enumerate(pages, 1))
        if not any(pages):
            return None, "PDF zonder tekstlaag (scan of afbeeldingen)"
        return text, None
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
        except (KeyError, zipfile.BadZipFile):
            return None, "zip-bestand, geen Word-document"
        xml = re.sub(r"</w:p>", "\n", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml)).strip(), None
    return None, "onbekend bestandstype"


def walk(items, depth=0):
    """Agenda items in order, nested ones included: (depth, node)."""
    for it in items or []:
        yield depth, it
        yield from walk(it.get("agenda_items"), depth + 1)


def first(*values):
    for v in values:
        if v:
            return v
    return ""


def run(mid, out_dir):
    data = collect.try_json(collect.api(f"events/meetings/{mid}"))
    if not data or not data.get("meeting"):
        print(f"FOUT: vergadering {mid} niet opgehaald ({collect.http_log_summary() or 'leeg antwoord'})")
        return 1
    m = data["meeting"]
    target = out_dir / str(mid)
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.txt"):
        old.unlink()
    (target / "meeting.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")

    plan = (m.get("plannings") or [{}])[0]
    gremium = (m.get("gremium") or {}).get("name") or ""
    lines = [
        f"# {first(title_of(m), gremium, f'Vergadering {mid}')}",
        "",
        f"- Vergadering-ID: {mid}",
        f"- Gremium: {gremium or 'onbekend'}",
        f"- Begin: {plan.get('start_date') or 'onbekend'}",
        f"- Einde: {plan.get('end_date') or 'onbekend'}",
        f"- Portaal: {PORTAL}/vergadering/{mid}",
        "",
    ]
    for label, text, aid in attributes(m):
        if aid != 1:
            lines += [f"**{label}:** {text}", ""]

    n, fetched, failed = 0, 0, 0

    def documents(node, indent):
        nonlocal n, fetched, failed
        for d in node.get("documents") or []:
            if not d.get("id"):
                continue
            n += 1
            title = re.sub(r"\s+", " ", d.get("title") or f"document {d['id']}").strip()
            url = document_url(d)
            raw = collect.try_bytes(url)
            time.sleep(collect.SLEEP)
            if raw is None:
                failed += 1
                lines.append(f"{indent}- 📄 {title} — NIET OPGEHAALD ({url})")
                continue
            text, why = text_of(raw)
            if text is None:
                failed += 1
                lines.append(f"{indent}- 📄 {title} — {why} ({url})")
                continue
            fname = f"{n:02d}-{safe_name(title)}.txt"
            (target / fname).write_text(f"{title}\n{url}\n\n{text}\n", "utf-8")
            fetched += 1
            lines.append(f"{indent}- 📄 {title} → `{fname}`")

    if m.get("documents"):
        lines += ["## Stukken bij de vergadering", ""]
        documents(m, "")
        lines.append("")

    lines += ["## Wurklist", ""]
    for depth, it in walk(m.get("agenda_items")):
        indent = "  " * depth
        prefix = str((it.get("type_data") or {}).get("title_prefix") or "").strip()
        title = title_of(it) or "(zonder titel)"
        lines.append(f"{indent}- **{prefix + ' ' if prefix else ''}{title}**")
        for label, text, aid in attributes(it):
            if aid != 1:
                body = text.replace("\n", f"\n{indent}  > ")
                lines.append(f"{indent}  > _{label}:_ {body}")
        documents(it, indent + "  ")

    (target / "agenda.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(f"Vergadering {mid}: {n} document(en), {fetched} als tekst, {failed} niet → {target}")
    if collect.http_log_summary():
        print(f"  mislukte requests: {collect.http_log_summary()}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("vergadering", help="vergadering-ID of Notubiz-link")
    ap.add_argument("--out", default="stukken", help="map voor de uitvoer (standaard: stukken)")
    args = ap.parse_args()
    if collect.RELAY:
        print(f"Requests via de relay op {collect.urllib.parse.urlparse(collect.RELAY).netloc}")
    return run(meeting_id(args.vergadering), Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
