"""Web setup: a small web page for a desktop browser or a phone in the home network, to set
up the panel without typing on the touch screen (settings, rooms and devices).

Off by default (Settings → Web setup). A browser connects once with a six-digit
code the panel shows; it then keeps a token in a cookie. Only hashes of the tokens are kept,
in web_tokens.json next to settings.json (not in backups, not shared).

The server runs in its own thread and knows nothing of Qt: every request goes to `handle`,
which the panel runs on its main thread.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import socket
import tempfile
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)
PAGE = Path(__file__).parent / "web" / "index.html"
FONTS = Path(__file__).parent / "assets" / "fonts"
COOKIE = "panel_token"
CODE_SECONDS = 300
MAX_TRIES = 5
MAX_BODY = 256 * 1024

# (method, path, body, authorized) -> (status, answer); answer is a dict (JSON)
Handler = Callable[[str, str, dict[str, Any], bool], tuple[int, dict[str, Any]]]


def local_address() -> str:
    """The panel's address in the home network (the one used to reach other hosts)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))      # TEST-NET: nothing is sent, only the route is chosen
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


class Pairing:
    """Codes for connecting a browser and the tokens of connected browsers."""

    def __init__(self, path: Path):
        self.path = path
        self.code = ""
        self.expires = 0.0
        self.tries = 0
        self.hashes: set[str] = set()
        self.on_paired: Callable[[], None] | None = None      # a browser has just connected
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.hashes = {str(h) for h in data if isinstance(h, str)}
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            pass

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def new_code(self, now: float | None = None) -> str:
        self.code = f"{secrets.randbelow(10**6):06d}"
        self.expires = (now or time.time()) + CODE_SECONDS
        self.tries = 0
        return self.code

    def pair(self, code: str, now: float | None = None) -> str:
        """A new token if the code is right (and not used up or too old); "" otherwise. A code
        works once; after MAX_TRIES wrong ones it is void."""
        if not self.code or (now or time.time()) > self.expires or self.tries >= MAX_TRIES:
            return ""
        if not secrets.compare_digest(str(code).strip(), self.code):
            self.tries += 1
            return ""
        self.code = ""
        token = secrets.token_urlsafe(32)
        self.hashes.add(self._hash(token))
        self._save()
        if self.on_paired:
            self.on_paired()
        return token

    def valid(self, token: str) -> bool:
        return bool(token) and self._hash(token) in self.hashes

    def forget(self, token: str | None = None) -> None:
        """Signs out one browser, or every browser."""
        if token is None:
            self.hashes.clear()
        else:
            self.hashes.discard(self._hash(token))
        self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".web-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(sorted(self.hashes), fh)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Web tokens not saved: %s", e)


class WebServer:
    def __init__(self, port: int, pairing: Pairing, handle: Handler, host: str = ""):
        self.pairing = pairing
        self.handle = handle
        server = self

        class RequestHandler(BaseHTTPRequestHandler):
            server_version = "SmartHomePanel"

            def log_message(self, fmt: str, *args: Any) -> None:     # quiet: no line per request
                log.debug("web: " + fmt, *args)

            def _token(self) -> str:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return c[COOKIE].value if COOKIE in c else ""

            def _send(self, status: int, body: bytes, ctype: str, cookie: str = "") -> None:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
                if cookie:
                    self.send_header("Set-Cookie", cookie)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, answer: dict[str, Any], cookie: str = "") -> None:
                self._send(status, json.dumps(answer, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                           cookie)

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0].split("#", 1)[0]
                if path in ("/", "/index.html"):
                    self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                elif path.startswith("/fonts/") and path.endswith(".ttf") and "/" not in path[7:]:
                    font = FONTS / path[7:]
                    if font.is_file():
                        self._send(200, font.read_bytes(), "font/ttf")
                    else:
                        self._json(404, {"error": "not found"})
                elif path.startswith("/api/"):
                    self._api("GET", path, {})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                # a header no other site can send without asking first (CORS): no cross-site posts
                if self.headers.get("X-Panel") != "1":
                    self._json(403, {"error": "forbidden"})
                    return
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    self._json(413, {"error": "too large"})
                    return
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    self._json(400, {"error": "bad json"})
                    return
                if not isinstance(body, dict):
                    self._json(400, {"error": "bad json"})
                    return
                if path == "/api/pair":
                    token = server.call(lambda: server.pairing.pair(str(body.get("code", ""))))
                    if not token:
                        self._json(401, {"error": "code"})
                        return
                    cookie = f"{COOKIE}={token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict"
                    self._json(200, {"ok": True}, cookie)
                    return
                if path == "/api/logout":
                    token = self._token()
                    server.call(lambda: server.pairing.forget(token) if server.pairing.valid(token) else None)
                    self._json(200, {"ok": True}, f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")
                    return
                if path == "/api/weather/search":        # waits for Open-Meteo: not on the panel's thread
                    if not server.pairing.valid(self._token()):
                        self._json(401, {"error": "pair"})
                    else:
                        self._json(200, server.search(str(body.get("text", ""))))
                    return
                self._api("POST", path, body)

            def _api(self, method: str, path: str, body: dict[str, Any]) -> None:
                token = self._token()
                try:
                    status, answer = server.call(lambda: server.handle(method, path, body, server.pairing.valid(token)))
                except Exception as e:  # pragma: no cover - keep serving
                    log.exception("Web request failed")
                    status, answer = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)}
                self._json(int(status), answer)

        self._httpd = ThreadingHTTPServer((host, port), RequestHandler)
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="web", daemon=True)
        self.call: Callable[[Callable[[], Any]], Any] = lambda fn: fn()     # set by the panel: run on its thread
        self.search: Callable[[str], dict[str, Any]] = lambda text: {"places": [], "error": ""}

    def start(self) -> None:
        self._thread.start()
        log.info("Web setup on port %d", self.port)

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
