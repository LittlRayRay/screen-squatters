"""Authenticated, loopback-only bridge. No third-party packages required."""
import json
import queue
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORT = 17373
MAX_BODY = 100_000
MAX_TEXT = 24_000


def validate_page(value):
    if not isinstance(value, dict):
        raise ValueError("Expected a page object")
    for key in ("title", "url", "text"):
        if not isinstance(value.get(key), str):
            raise ValueError(f"Missing or invalid {key}")
    parts = urlsplit(value["url"])
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Only HTTP and HTTPS pages are supported")
    # Query strings and fragments often contain private identifiers.
    host = parts.hostname
    if ":" in host:
        host = "[" + host + "]"
    if parts.port:
        host += ":" + str(parts.port)
    url = f"{parts.scheme}://{host}{parts.path}"
    return {"title": value["title"][:300], "url": url[:2048],
            "text": value["text"][:MAX_TEXT], "automatic": value.get("automatic") is True}


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, token, inbox, port=PORT):
        self.token = token
        self.inbox = inbox
        self.awake = False
        super().__init__(("127.0.0.1", port), BridgeHandler)


class BridgeHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_args):
        pass  # Do not log page content or credentials.

    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        expected_host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected_host:
            return False
        origin = self.headers.get("Origin", "")
        if origin and not origin.startswith("chrome-extension://"):
            return False
        supplied = self.headers.get("Authorization", "")
        return secrets.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode())

    def do_POST(self):
        if not self.authorized():
            self.reply(403, {"error": "Pairing code rejected. Copy it again from Home Settings."})
            return
        if self.path != "/page":
            self.reply(404, {"error": "Unknown endpoint"})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Expected JSON"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.reply(413, {"error": "Page payload is too large"})
                return
            page = validate_page(json.loads(self.rfile.read(length)))
            self.server.inbox.put_nowait(page)
        except queue.Full:
            self.reply(429, {"error": "The house is busy. Try again shortly."})
            return
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "Invalid page data"})
            return
        self.reply(200, {"ok": True, "characters": len(page["text"])})

    def do_GET(self):
        if not self.authorized():
            self.reply(403, {"error": "Pairing code rejected"})
        elif self.path == "/status":
            self.reply(200, {"awake": self.server.awake})
        else:
            self.reply(404, {"error": "Unknown endpoint"})
