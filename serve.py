#!/usr/bin/env python3
"""
Local dev server for symposium display pages.
Proxies /proxy/schedule to the symposium site with the bypass header,
and serves static files from the current directory.

Usage: python3 serve.py [port]
Default port: 8000
"""

import http.server
import urllib.request
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SOURCE_URL = "https://symposium.orfe.princeton.edu"
BYPASS_HEADER = ("x-wdsoit-bot-bypass", "true")

# Cache the fetched HTML for 60 seconds to avoid hammering upstream
_cache = {"html": None, "ts": 0}
CACHE_TTL = 60


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def do_GET(self):
        if self.path == "/proxy/schedule":
            self._proxy_schedule()
        else:
            super().do_GET()

    def _proxy_schedule(self):
        import time

        now = time.time()
        if _cache["html"] and (now - _cache["ts"]) < CACHE_TTL:
            html = _cache["html"]
        else:
            try:
                req = urllib.request.Request(SOURCE_URL, headers={
                    BYPASS_HEADER[0]: BYPASS_HEADER[1],
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html = resp.read()
                _cache["html"] = html
                _cache["ts"] = now
            except Exception as e:
                self.send_error(502, f"Upstream fetch failed: {e}")
                return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, format, *args):
        # Quieter logging
        if "/proxy/" in str(args[0]):
            super().log_message(format, *args)


if __name__ == "__main__":
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print(f"Serving on http://localhost:{PORT}")
        print(f"  Display (all rooms): http://localhost:{PORT}/display.html")
        print(f"  Ground floor:        http://localhost:{PORT}/display.html?floor=ground")
        print(f"  1st floor:           http://localhost:{PORT}/display.html?floor=1")
        print()
        httpd.serve_forever()
