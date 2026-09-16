#!/usr/bin/env python3
"""Home-server endpoint serving the rs4t profile card in real time.

Computes the current ASCII art frame from the wall clock (a 30-second
slot shared by every viewer, unlike a client-side animation which only
tracks time-since-page-load and resets on every reload) and renders it
with live-ish GitHub stats, refreshed periodically in the background so
requests don't hit the GitHub API directly.

Run with: GITHUB_TOKEN=... python3 server.py [port]
Put a reverse proxy (nginx/Caddy/Cloudflare Tunnel) in front for TLS and
the public domain (e.g. card.zegg.me). The proxy or this script's own
Cache-Control header should be configured to serve stale content if this
process is down, since it isn't always on.
"""
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cardlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_REFRESH_SECONDS = 600

_state_lock = threading.Lock()
_state = {"sections": None, "ascii_art_sets": None, "error": None}


def refresh_stats():
    headers = cardlib.make_headers(os.environ.get("GITHUB_TOKEN"))
    try:
        ascii_art_sets = cardlib.load_ascii_art_sets(REPO_ROOT)
        user = cardlib.get_user(headers)
        repos = cardlib.get_repos(headers)
        sections = cardlib.build_sections(user, repos, headers)
        with _state_lock:
            _state["sections"] = sections
            _state["ascii_art_sets"] = ascii_art_sets
            _state["error"] = None
    except Exception as exc:
        with _state_lock:
            _state["error"] = str(exc)


def refresh_loop():
    while True:
        refresh_stats()
        time.sleep(STATS_REFRESH_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] != "/profile-card.svg":
            self.send_response(404)
            self.end_headers()
            return

        with _state_lock:
            sections = _state["sections"]
            ascii_art_sets = _state["ascii_art_sets"]

        if sections is None or ascii_art_sets is None:
            self.send_response(503)
            self.send_header("Retry-After", "5")
            self.end_headers()
            return

        art_index = cardlib.current_art_index(len(ascii_art_sets))
        svg = cardlib.build_svg_frame(ascii_art_sets, sections, art_index)
        body = svg.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        # A viewer's browser/proxy revalidates every 30s (so it picks up
        # the next art on schedule) but keeps serving its last cached copy
        # for up to a day if this server stops responding entirely.
        self.send_header(
            "Cache-Control",
            f"public, max-age={cardlib.ART_CYCLE_SECONDS}, "
            "stale-while-revalidate=30, stale-if-error=86400",
        )
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    refresh_stats()
    if _state["sections"] is None:
        print(f"warning: initial stats fetch failed: {_state['error']}", file=sys.stderr)
    threading.Thread(target=refresh_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"serving profile-card.svg on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
