"""
Fallback source: the griffie's "Útslach stimming <datum>" PDF.

Since the plenary meeting of 27 May 2026 the Provinsjale Steaten no longer register their
hoofdelijke stemmingen in Notubiz's voting module: `agenda_items/votings` is empty for those
meetings and the portal page carries no per-fractie charts. What the griffie does publish, under
the agenda item "Stimming", is a PDF with one screenshot of the voting display per stemming:

    title on top
    one dark header bar per fractie, below it one coloured row per member
        green = foar (in favour), red = tsjin (against), yellow = ûnthâlding (abstain),
        grey = ôfwêzich (absent)
    "Voor: N  Tegen: N  Onthouding: N" at the bottom

This module turns such a PDF into the same per-fractie counts the API path produces:
  * pypdf extracts the page images (JPEG screenshots, 1280x800),
  * the grid is read from pixel colours — the counts themselves never depend on OCR,
  * RapidOCR (a small local ONNX model, no network) reads the title, the fractie names in the
    header bars and the totals line.
Every page is cross-checked: the rows counted per colour must equal the OCR'd totals and every
header must resolve to a known fractie; otherwise the page is rejected, never guessed.

Optional dependencies (collector/requirements-pdf.txt): pypdf, Pillow, numpy,
rapidocr_onnxruntime. Without them `available()` is False and collect.py reports which meetings
it had to skip. Member names are read for nothing and never stored.
"""

import difflib
import io
import re
import unicodedata
from collections import Counter

ROW = 31           # pixel pitch of header bars and member rows in the 1280x800 screenshots
GRID_WIDTH = 1280  # every page image is normalised to this width before reading
GRID_TOP = 120     # header bars start below the title
COLUMN_BAND = (130, 680)   # y-band used to find the columns (above the totals line)
MIN_COLUMN_WIDTH = 100
PARTY_MATCH_MIN = 0.75     # fuzzy ratio an OCR'd header needs to count as a known fractie

# Abbreviations the voting display uses where Notubiz uses the full name.
HEADER_ALIASES = {
    "pbf": "Provinciaal Belang Fryslân",
    "gl": "GrienLinks",
    "cu": "ChristenUnie",
    # Both resolve to one column via collect.NOTUBIZ_ALIASES ("Van Dijk (FvD)").
    "fvd": "FVD",
    "vandijk": "Steatelid Van Dijk",
    "steatelidvandijk": "Steatelid Van Dijk",
}

_OPTIONAL = ("pypdf", "PIL", "numpy", "rapidocr_onnxruntime")


def missing():
    """Names of the optional packages that are not importable."""
    out = []
    for name in _OPTIONAL:
        try:
            __import__(name)
        except ImportError:
            out.append("Pillow" if name == "PIL" else name)
    return out


def available():
    return not missing()


# --- text helpers ---------------------------------------------------------------------------------

def squash(s):
    """Lower-case ASCII letters and digits only. OCR drops spaces unpredictably, so every
    comparison in this module is done on space-less text."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def similarity(a, b):
    return difflib.SequenceMatcher(None, squash(a), squash(b)).ratio()


def _digits(s):
    """OCR reads 0 as o/O in numbers: "4o" -> 40."""
    return int(re.sub(r"[oO]", "0", s))


TOTALS_RE = re.compile(
    r"Voor\W{0,3}([0-9oO]+)\W{0,3}Tegen\W{0,3}([0-9oO]+)\W{0,3}Onthouding\W{0,3}([0-9oO]+)", re.I)


def parse_totals(text):
    """(voor, tegen, onthouding) from the OCR'd page text, or None."""
    m = TOTALS_RE.search(text or "")
    return tuple(_digits(g) for g in m.groups()) if m else None


AGENDA_RE = re.compile(r"^\s*(?=[\dOo]{0,2}\d)([\dOo]{1,3})")
NUMBER_RE = re.compile(r"(?:moasje|moasie|motie|amendemint|amendement)(?:frjemd|fremd)?0*(\d+)")


def title_info(title):
    """What a page title says about the stemming: {agenda, type, number, withdrawn, revote}.
    "07Moasje01-Pragmatischherbestemmen-BBB" -> agenda 7, motie, number "1"
    "1o Moasje frjemd - Underhâld rykswegen"  -> agenda 10, frjemd, no number
    "05Amendemint 02-Geen spaarpot naast de VAR" -> agenda 5, amendement, "2"
    "YNLUTSEN03Moasje25-…"                    -> withdrawn
    "14b-Werstimming: PS 6 maaie 2026, wurklistpunt 03 Moasje 19-…" -> revote, motie, "19"."""
    t = squash(title)
    m = AGENDA_RE.match(title or "")
    agenda = _digits(m.group(1)) if m else None
    if "finalebeslut" in t or "finalebesluit" in t or "eindstemming" in t:
        itype = "besluit"     # the vote on the proposal itself, e.g. "… moasjes en tasizzings - Finale beslút"
    elif "amendemint" in t or "amendement" in t:
        itype = "amendement"
    elif re.search(r"(?:moasje|moasie|motie)(?:frjemd|fremd)", t):
        itype = "frjemd"
    elif "moasje" in t or "moasie" in t or "motie" in t:
        itype = "motie"
    elif "oarderfoarstel" in t or "ordevoorstel" in t:
        itype = "ordevoorstel"
    else:
        itype = "besluit"
    m = NUMBER_RE.search(t) if itype in ("motie", "frjemd", "amendement") else None
    return {
        "agenda": agenda,
        "type": itype,
        "number": m.group(1) if m else None,
        "withdrawn": "ynlutsen" in t or "ingetrokken" in t,
        "revote": "werstimming" in t or "herstemming" in t,
    }


def match_party(text, primary, secondary=()):
    """Resolve an OCR'd header bar to a known fractie name. `primary` are the fracties already
    seen this term (preferred), `secondary` the organisation's full party list. None when
    nothing is close enough — the caller then rejects the page rather than guessing."""
    key = squash(text)
    if not key:
        return None
    if key in HEADER_ALIASES:
        return HEADER_ALIASES[key]
    for names in (primary, secondary):
        best = None
        for n in names:
            r = difflib.SequenceMatcher(None, key, squash(n)).ratio()
            if best is None or r > best[0]:
                best = (r, n)
        if best and best[0] >= PARTY_MATCH_MIN:
            return best[1]
    return None


# --- pixel grid -----------------------------------------------------------------------------------

def pixel_class(rgb):
    """H header bar, F in favour, A against, O abstain, X absent, '.' background, '?' other
    (text, logo, JPEG ringing)."""
    r, g, b = rgb[:3]
    if r < 90 and g < 90 and b < 90:
        return "H"
    if r > 235 and g > 235 and b > 235:
        return "."
    if g > 150 and r < 170 and b < 170 and g - r > 40:
        return "F"
    if r > 200 and g < 170 and b < 170:
        return "A"
    if r > 220 and g > 200 and b < 170:
        return "O"
    if abs(r - g) < 14 and abs(g - b) < 14 and 150 < r < 225:
        return "X"
    return "?"


def _runs(flags):
    out, start = [], None
    for i, v in enumerate(list(flags) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def read_grid(im, boxes):
    """Read the vote grid of one page image (PIL, GRID_WIDTH wide).
    Returns a list of blocks in column order: {"header": OCR text of the bar, "rows": "FFAX…"}.
    Header bars are found as dark runs at the right margin of each column; below each bar the
    member rows are walked with a fixed pitch of ROW px and classified by the majority colour of
    a patch near the right margin (where no text is printed)."""
    w, h = im.size
    px = im.load()
    y0, y1 = COLUMN_BAND
    has_bar = [any(pixel_class(px[x, y]) == "H" for y in range(y0, min(y1, h), 3)) for x in range(w)]
    columns = [(a, b) for a, b in _runs(has_bar) if b - a >= MIN_COLUMN_WIDTH]

    blocks = []
    for x0, x1 in columns:
        xs = [x1 - d for d in (5, 11, 17, 23, 29)]

        def klass(y):
            c = Counter(pixel_class(px[x, y]) for x in xs)
            return c.most_common(1)[0][0]

        def row_class(ry):
            band = range(ry + 5, ry + ROW - 5)
            c, n = Counter(klass(y) for y in band).most_common(1)[0]
            return c if c in "FAOX" and n >= 0.6 * len(band) else None

        y = GRID_TOP
        while y < h:
            if klass(y) != "H":
                y += 1
                continue
            top = y
            while y < h and klass(y) == "H":
                y += 1
            if y - top < ROW - 8:
                continue
            rows, ry = [], top + ROW
            while ry + ROW - 5 <= h:
                c = row_class(ry)
                if c is None:
                    break
                rows.append(c)
                ry += ROW
            header = " ".join(b["text"] for b in sorted(boxes, key=lambda b: b["x"])
                              if x0 - 12 <= b["x"] <= x1 and b["y"] < top + ROW and b["y2"] > top)
            blocks.append({"header": header.strip(), "rows": "".join(rows), "x": x0, "x1": x1, "y": top})
            y = ry
    return blocks


def page_title(boxes):
    top = [b for b in boxes if b["y"] < GRID_TOP - 10]
    return " ".join(b["text"] for b in sorted(top, key=lambda b: (b["y"] // 25, b["x"]))).strip()


# --- page / document ----------------------------------------------------------------------------------

_ocr = None


def _ocr_boxes(im):
    """OCR one PIL image -> [{"x","y","y2","text"}]."""
    global _ocr
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    if _ocr is None:
        _ocr = RapidOCR()
    res, _ = _ocr(np.array(im.convert("RGB")))
    out = []
    for box, text, _conf in res or []:
        out.append({"x": int(min(p[0] for p in box)), "y": int(min(p[1] for p in box)),
                    "y2": int(max(p[1] for p in box)), "text": str(text)})
    return out


def header_crop(im, blk):
    """The header bar of a block as an upscaled black-on-white image: the full-page OCR pass
    sometimes skips a short white-on-dark word (typically "VVD"), a second pass on this crop
    does not."""
    from PIL import ImageOps
    x0 = blk["x"]
    x1 = blk.get("x1", x0 + 270)
    crop = im.crop((x0, blk["y"], x1, blk["y"] + ROW))
    return ImageOps.invert(crop.convert("RGB")).resize((crop.size[0] * 3, crop.size[1] * 3))


def read_page(im, boxes, primary, secondary=(), ocr_crop=None):
    """Interpret one page. Returns a dict:
      title, info (title_info), totals, votes {fractie: {agree, disagree, abstain, absent}},
      ok (bool), warning (why not ok).
    `ocr_crop(image) -> text` is used for header bars the page-wide OCR left empty."""
    title = page_title(boxes)
    info = title_info(title)
    totals = parse_totals(" ".join(b["text"] for b in boxes))
    votes, unknown, seen = {}, [], set()
    for blk in read_grid(im, boxes):
        if not blk["header"] and ocr_crop is not None:
            blk["header"] = ocr_crop(header_crop(im, blk)).strip()
        name = match_party(blk["header"], primary, secondary)
        if not name:
            unknown.append(blk["header"] or "<leeg>")
            continue
        if name in seen:
            unknown.append(f"{name} (twee keer)")
        seen.add(name)
        v = votes.setdefault(name, {"agree": 0, "disagree": 0, "abstain": 0, "absent": 0})
        v["agree"] += blk["rows"].count("F")
        v["disagree"] += blk["rows"].count("A")
        v["abstain"] += blk["rows"].count("O")
        v["absent"] += blk["rows"].count("X")
    counted = (sum(v["agree"] for v in votes.values()),
               sum(v["disagree"] for v in votes.values()),
               sum(v["abstain"] for v in votes.values()))
    page = {"title": title, "info": info, "totals": totals, "votes": votes, "counted": counted,
            "ok": True, "warning": ""}
    if info["withdrawn"] or (totals == (0, 0, 0) and counted == (0, 0, 0)):
        page["ok"] = False
        page["warning"] = "ynlutsen"
    elif unknown:
        page["ok"] = False
        page["warning"] = "onbekende fractie(s): " + ", ".join(unknown)
    elif totals is None:
        page["ok"] = False
        page["warning"] = "totaalregel niet leesbaar"
    elif totals != counted:
        page["ok"] = False
        page["warning"] = f"telling {counted} wijkt af van totaalregel {totals}"
    elif not votes:
        page["ok"] = False
        page["warning"] = "geen stemmen gevonden"
    return page


def page_images(pdf_bytes):
    """Yield (page_number, PIL image) for every page that carries a screenshot; images are
    normalised to GRID_WIDTH wide. The cover page (different size) is skipped by the caller
    through the grid checks."""
    from PIL import Image
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for n, pg in enumerate(reader.pages, start=1):
        best = None
        for img in pg.images:
            try:
                im = img.image
            except Exception:   # noqa: BLE001 — a broken embedded image only costs that page
                continue
            if best is None or im.size[0] * im.size[1] > best.size[0] * best.size[1]:
                best = im
        if best is None:
            continue
        im = best.convert("RGB")
        if im.size[0] != GRID_WIDTH:
            im = im.resize((GRID_WIDTH, round(im.size[1] * GRID_WIDTH / im.size[0])),
                           Image.LANCZOS)
        yield n, im


def parse_pdf(pdf_bytes, primary, secondary=()):
    """All pages of an "Útslach stimming" PDF -> [page dict with "page" number]. The cover page
    yields no grid and no totals and comes back as not ok ("geen stemmen gevonden")."""
    pages = []

    def ocr_crop(crop):
        return " ".join(b["text"] for b in sorted(_ocr_boxes(crop), key=lambda b: b["x"]))

    for n, im in page_images(pdf_bytes):
        boxes = _ocr_boxes(im)
        page = read_page(im, boxes, primary, secondary, ocr_crop)
        page["page"] = n
        pages.append(page)
    return pages
