"""
Full text of the Moasje/Amendemint PDFs, so the site's search box also finds words in the document
itself and not only in its title.

Every stemming that collect.py joined to a document carries its portal URL in `document`
(https://fryslan.notubiz.nl/document/<id>/1/<titel>). This module fetches each of those PDFs once,
pulls the text layer out with pypdf and keeps it in data/teksten.json:

    {"generated_at": "...", "docs": {"<document id>": "<text>", ...}, "noText": ["<id>", ...]}

* Incremental: a document already in `docs` or `noText` is never fetched again (a motion's PDF does
  not change once it has been voted on). The first run fills the file; after that a daily run only
  fetches the handful of new documents.
* `noText` holds documents without a usable text layer (a scan). They are reported, not OCR'd.
* A document that could not be fetched is left out, so the next run simply tries again.
* Ids no longer referenced by any stemming are dropped.
* A time budget (TEKSTEN_BUDGET seconds, default 1200) stops a long first run cleanly; whatever was
  read is written and the next run picks up where this one stopped.

pypdf is one of the optional dependencies in collector/requirements-pdf.txt; without it the existing
file is left untouched.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

MAX_CHARS = 30000          # a motion is 1-3 pages; this only guards against an odd huge attachment
MIN_CHARS = 40             # less than this from a whole PDF = no real text layer (a scan)
BUDGET = float(os.environ.get("TEKSTEN_BUDGET", "1200"))

_DOC_ID = re.compile(r"/document/(\d+)")


def doc_id(url):
    """Document id from a portal URL, or None."""
    m = _DOC_ID.search(url or "")
    return m.group(1) if m else None


def clean(text):
    """Searchable plain text: words broken over a line end rejoined, whitespace collapsed."""
    text = (text or "").replace("­", "")                  # soft hyphens
    text = re.sub(r"(\w)-\s*\n\s*(?=[a-zà-ÿ])", r"\1", text)   # "stikstof-\nuitstoot" -> one word
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]


def extract(raw):
    """Text of a PDF (bytes), cleaned; "" when it has no usable text layer."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    text = clean("\n".join((page.extract_text() or "") for page in reader.pages))
    return text if len(text) >= MIN_CHARS else ""


def available():
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def load(path):
    try:
        j = json.loads(path.read_text(encoding="utf-8"))
        return dict(j.get("docs") or {}), set(j.get("noText") or [])
    except (OSError, ValueError):
        return {}, set()


def wanted(moties):
    """{document id: url} for every stemming with a document."""
    out = {}
    for m in moties:
        i = doc_id(m.get("document"))
        if i and i not in out:
            out[i] = m["document"]
    return out


def update(moties, path, fetch_bytes, sleep=0.3, budget=BUDGET, log=print):
    """Bring `path` up to date for `moties`. Returns (read, no_text, failed, left_for_next_run)."""
    if not available():
        log("  teksten: pypdf ontbreekt — data/teksten.json niet bijgewerkt")
        return 0, 0, 0, 0
    docs, no_text = load(path)
    want = wanted(moties)
    docs = {k: v for k, v in docs.items() if k in want}
    no_text &= set(want)
    todo = [(i, u) for i, u in want.items() if i not in docs and i not in no_text]

    read = failed = 0
    new_no_text = []
    start = time.monotonic()
    left = 0
    for n, (i, url) in enumerate(todo):
        if time.monotonic() - start > budget:
            left = len(todo) - n
            break
        raw = fetch_bytes(url)
        if not raw:
            failed += 1
            continue
        try:
            text = extract(raw)
        except Exception as e:   # noqa: BLE001 — one broken PDF must not stop the rest
            log(f"  WARN teksten: document {i} niet leesbaar ({type(e).__name__}: {e})")
            failed += 1
            continue
        if text:
            docs[i] = text
            read += 1
        else:
            no_text.add(i)
            new_no_text.append(i)
        if (n + 1) % 100 == 0:
            log(f"  teksten: {n + 1}/{len(todo)} …")
        time.sleep(sleep)

    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "docs": dict(sorted(docs.items(), key=lambda kv: int(kv[0]))),
           "noText": sorted(no_text, key=int)}
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  wrote {path.name}: {len(docs)} documenten met tekst ({read} nieuw), "
        f"{len(no_text)} zonder tekstlaag, {failed} niet opgehaald"
        + (f", {left} voor de volgende run (tijdslimiet)" if left else ""))
    for i in new_no_text:
        log(f"  WARN teksten: document {i} heeft geen tekstlaag (scan?) — niet doorzoekbaar")
    return read, len(new_no_text), failed, left
