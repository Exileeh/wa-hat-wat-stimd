"""Egress relay: fetches one Notubiz URL on behalf of the collector.

Notubiz blocks GitHub's Azure runners (docs/notubiz.md section 4), but a Vercel function in
fra1 (AWS eu-central-1) reaches every surface -- measured 2026-09-19. So the collector keeps
running in GitHub Actions, where it has the OCR packages, unbounded runtime and a git push, and
only its outbound requests come through here.

    GET /api/notubiz?u=<urlencoded notubiz url>      header X-Relay-Key: <RELAY_KEY>

This sits on a public domain, so two things keep it from being an open proxy: the shared key,
and a host allowlist. Without a matching key it answers 404 -- an unauthenticated caller learns
nothing about what lives here.

Vercel caps a response body at 4.5 MB. Anything bigger is served in chunks: the relay answers
206 with a Content-Range, and the caller asks for the rest with a Range header (collect.py's
http() does this). The relay slices the body itself instead of forwarding Range upstream, so it
does not matter whether Notubiz honours Range.
"""

from http.server import BaseHTTPRequestHandler
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ALLOWED_HOSTS = {"api.notubiz.nl", "fryslan.notubiz.nl"}

# Same identification the collector sends directly; the portal's Cloudflare rules accept it.
UA = "wa-hat-wat-stimd collector (open-data overview; contact via GitHub)"

# Under Vercel's 4.5 MB body cap with room for headers. The module list is ~3.4 MB and fits in
# one response today; the Útslach PDFs are what may need more than one.
MAX_CHUNK = 3_800_000

UPSTREAM_TIMEOUT = 50   # below the function's maxDuration, so a hang returns a 502, not a 504

RANGE_RE = re.compile(r"^bytes=(\d+)-(\d*)$")


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*", "X-Requested-With": "XMLHttpRequest"},
    )
    with urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT) as r:
        return r.status, r.headers.get("Content-Type", "application/octet-stream"), r.read()


def wanted_range(header):
    """Start offset the caller asked for, or None for 'from the beginning'."""
    if not header:
        return None
    m = RANGE_RE.match(header.strip())
    return int(m.group(1)) if m else None


class handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        key = os.environ.get("RELAY_KEY", "")
        if not key:
            self.reply(503, json.dumps({"error": "RELAY_KEY is not configured"}))
            return
        if not hmac.compare_digest(self.headers.get("X-Relay-Key", ""), key):
            self.reply(404, json.dumps({"error": "not found"}))
            return

        query = urllib.parse.urlparse(self.path).query
        target = (urllib.parse.parse_qs(query).get("u") or [""])[0]
        parsed = urllib.parse.urlparse(target)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            self.reply(400, json.dumps({"error": "url must be https and one of "
                                                 + ", ".join(sorted(ALLOWED_HOSTS))}))
            return

        try:
            status, content_type, body = fetch(target)
        except urllib.error.HTTPError as e:
            # Pass the upstream status through untouched: collect.py retries 429/5xx and gives up
            # on a 4xx, and that decision belongs to the collector, not to this relay.
            self.reply(e.code, e.read()[:MAX_CHUNK],
                       e.headers.get("Content-Type", "text/plain"), {"X-Relay-Upstream": "1"})
            return
        except Exception as e:
            self.reply(502, json.dumps({"error": f"{type(e).__name__}: {getattr(e, 'reason', e)}"}))
            return

        start = wanted_range(self.headers.get("Range")) or 0
        total = len(body)
        if start >= total and total:
            self.reply(416, json.dumps({"error": "range beyond body", "size": total}))
            return

        chunk = body[start:start + MAX_CHUNK]
        if start == 0 and len(chunk) == total:
            self.reply(status, chunk, content_type)
            return
        end = start + len(chunk) - 1
        self.reply(206, chunk, content_type,
                   {"Content-Range": f"bytes {start}-{end}/{total}", "Accept-Ranges": "bytes"})
