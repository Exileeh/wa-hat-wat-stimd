"""Throwaway diagnostic: can a Vercel function reach Notubiz?

api.notubiz.nl blocks GitHub's Azure runners (see docs/notubiz.md section 4). Whether it also
blocks a European AWS datacenter -- which is what a Vercel function runs on -- decides whether
the daily refresh can be routed through Vercel at all. This endpoint answers that question and
nothing else; it is meant to be deleted again.

Open <deployment>/api/probe in the browser (preview deployments sit behind Vercel
Authentication, so curl gets a 401). The region is set in vercel.json.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import time
import urllib.error
import urllib.request

# Same identification the collector uses: the portal's Cloudflare rules let this UA through
# while they challenge a bare curl.
UA = "wa-hat-wat-stimd collector (open-data overview; contact via GitHub)"

TARGETS = {
    # The three API surfaces the collector needs, plus the portal page (a separate gate: the API
    # is plain AWS, the portal sits behind Cloudflare and can block on its own).
    "api_events": (
        "https://api.notubiz.nl/events?organisation_id=822"
        "&date_from=2026-01-01%2000:00:00&date_to=2026-12-31%2000:00:00"
        "&page=1&format=json&version=1.21"
    ),
    "api_meeting": "https://api.notubiz.nl/events/meetings/1488191?format=json&version=1.21",
    "api_modules": (
        "https://api.notubiz.nl/modules/6/items?organisation_id=822&format=json&version=1.21"
    ),
    "portal_html": "https://fryslan.notubiz.nl/vergadering/1488191",
    "egress_ip": "https://ipinfo.io/json",
}

# The module list is ~3.5 MB and needs well over the default here even on a fast line -- give it
# room, so a slow download is not mistaken for the block we are testing for.
TIMEOUTS = {"api_modules": 45}
DEFAULT_TIMEOUT = 12


def probe(url, timeout=DEFAULT_TIMEOUT):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*", "X-Requested-With": "XMLHttpRequest"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {
                "status": r.status,
                "bytes": len(body),
                "ms": int((time.monotonic() - started) * 1000),
                "head": body[:120].decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as e:
        # 403 here means Cloudflare saw the origin and said no -- a block, not a network fault.
        return {"status": e.code, "ms": int((time.monotonic() - started) * 1000)}
    except Exception as e:  # URLError / timeout: the silent TCP drop we are hunting
        return {
            "error": f"{type(e).__name__}: {getattr(e, 'reason', e)}",
            "ms": int((time.monotonic() - started) * 1000),
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        out = {
            "region": os.environ.get("VERCEL_REGION"),
            "results": {
                name: probe(url, TIMEOUTS.get(name, DEFAULT_TIMEOUT))
                for name, url in TARGETS.items()
            },
        }
        payload = json.dumps(out, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)
