"""Authenticated, loopback-only bridge. No third-party packages required."""
import json
import math
import re
from collections import deque
import queue
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORT = 17373
MAX_BODY = 256_000
MAX_TEXT = 24_000


def clean_url(value, maximum=2048):
    if not isinstance(value, str):
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ""
        host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        if parts.port:
            host += ":"+str(parts.port)
        return f"{parts.scheme}://{host}{parts.path}"[:maximum]
    except ValueError:
        return ""


def feed_keys(value):
    if "session_id" not in value and "sequence" not in value:
        return {}
    session, sequence = value.get("session_id"), value.get("sequence")
    if not isinstance(session, str) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", session):
        raise ValueError("Invalid browser feed session")
    if type(sequence) is not int or not 0 < sequence <= 1_000_000_000_000:
        raise ValueError("Invalid browser feed sequence")
    return {"session_id": session, "sequence": sequence}


class BrowserFeed:
    """Reject delayed snapshots after tab/focus changes or extension restarts."""
    def __init__(self):
        self.session = None
        self.sequence = 0
        self.retired = deque(maxlen=8)

    def accept(self, value):
        session = value.get("session_id")
        if not session:
            return True  # Single-share snapshots and older clients.
        if session in self.retired:
            return False
        if session != self.session:
            if self.session:
                self.retired.append(self.session)
            self.session, self.sequence = session, 0
        if value["sequence"] <= self.sequence:
            return False
        self.sequence = value["sequence"]
        return True


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
    targets = []
    for item in (value.get("targets") if isinstance(value.get("targets"), list) else [])[:12]:
        if not isinstance(item, dict) or not isinstance(item.get("label"), str):
            continue
        if not all(type(item.get(key)) in (int, float) and math.isfinite(item[key]) and 0 <= item[key] <= 1 for key in ("x", "y")):
            continue
        targets.append({"label": item["label"][:80], "x": item["x"], "y": item["y"]})
    viewport = value.get("viewport", {})
    viewport = {key: viewport[key] for key in ("width", "height", "outerWidth", "outerHeight")
                if isinstance(viewport, dict) and type(viewport.get(key)) in (int, float)
                and math.isfinite(viewport[key]) and 1 <= viewport[key] <= 100000}
    def text(value, maximum):
        return value[:maximum] if isinstance(value, str) else ""
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
    metadata = {key: text(metadata.get(key), maximum) for key, maximum in
                (("description",600),("author",160),("site_name",160),("page_type",80),("language",40))}
    metadata["canonical_url"] = clean_url((value.get("metadata") or {}).get("canonical_url")) if isinstance(value.get("metadata"), dict) else ""
    headings = [item[:160] for item in value.get("headings", [])[:12] if isinstance(item, str)] if isinstance(value.get("headings"), list) else []
    links = []
    for item in (value.get("links") if isinstance(value.get("links"), list) else [])[:20]:
        if isinstance(item, dict) and clean_url(item.get("url"), 512):
            links.append({"label": text(item.get("label"),100), "url": clean_url(item.get("url"),512)})
    media = []
    for item in (value.get("media") if isinstance(value.get("media"), list) else [])[:4]:
        if not isinstance(item, dict) or item.get("kind") not in ("video", "audio"):
            continue
        entry = {"kind": item["kind"], **{key: item.get(key) is True for key in ("paused","ended","muted")}}
        for key in ("current_time","duration","playback_rate"):
            number = item.get(key)
            entry[key] = number if type(number) in (int,float) and math.isfinite(number) and 0 <= number <= 1_000_000_000 else None
        media.append(entry)
    reading = value.get("reading") if isinstance(value.get("reading"), dict) else {}
    reading = {key: number for key, maximum in (("scroll_y",100_000_000),("progress",1))
               if type(number := reading.get(key)) in (int,float) and math.isfinite(number) and 0 <= number <= maximum}
    return {"title": value["title"][:300], "url": url[:2048],
            "text": value["text"][:MAX_TEXT], "automatic": value.get("automatic") is True,
            "targets": targets, "viewport": viewport, "metadata": metadata, "headings": headings, "links": links,
            "media": media, "captions": text(value.get("captions"),2000), "page_text": text(value.get("page_text"),12000),
            "reading": reading, "browser": "firefox" if value.get("browser") == "firefox" else "",
            **feed_keys(value)}


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
        if origin:
            try:
                parts = urlsplit(origin)
            except ValueError:
                return False
            if parts.scheme not in ("chrome-extension", "moz-extension") or not parts.hostname or parts.path not in ("", "/") or parts.query or parts.fragment or parts.username or parts.password:
                return False
        supplied = self.headers.get("Authorization", "")
        return secrets.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode())

    def do_POST(self):
        if not self.authorized():
            self.reply(403, {"error": "Pairing code rejected. Copy it again from Home Settings."})
            return
        if self.path not in ("/page", "/browser-state", "/browser-event"):
            self.reply(404, {"error": "Unknown endpoint"})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Expected JSON"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                # Drain a bounded oversized body so Windows can deliver the 413
                # response instead of resetting a socket with unread request data.
                if length > MAX_BODY:
                    self.rfile.read(min(length, MAX_BODY+1))
                self.reply(413, {"error": "Page payload is too large"})
                return
            value = json.loads(self.rfile.read(length))
            if self.path == '/browser-event':
                if not isinstance(value,dict) or value.get('event') not in ('tab-opened','tab-closed','tab-switched','page-changed'):
                    raise ValueError('Invalid browser event')
                if not isinstance(value.get('event_id'),str) or not re.fullmatch(r'[a-zA-Z0-9:_-]{1,100}',value['event_id']):
                    raise ValueError('Invalid event identity')
                count = value.get('count',1)
                if type(count) is not int or not 1<=count<=1_000_000:
                    raise ValueError('Invalid event count')
                page = {'kind':'browser-event','source':'browser','event':value['event'],'event_id':value['event_id'],
                        'title':value.get('title','')[:160] if isinstance(value.get('title',''),str) else '',
                        'url':clean_url(value.get('url','')),'app':'Firefox','count':count,**feed_keys(value)}
            elif self.path == "/browser-state":
                if not isinstance(value, dict) or value.get("state") not in ("inactive", "blocked", "paused", "loading"):
                    raise ValueError("Invalid browser state")
                page = {"kind": "browser-state", "state": value["state"], **feed_keys(value)}
            else:
                page = validate_page(value)
            self.server.inbox.put_nowait(page)
        except queue.Full:
            self.reply(429, {"error": "The house is busy. Try again shortly."})
            return
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "Invalid page data"})
            return
        self.reply(200, {"ok": True, "characters": len(page.get("text", ""))})

    def do_GET(self):
        if not self.authorized():
            self.reply(403, {"error": "Pairing code rejected"})
        elif self.path == "/status":
            self.reply(200, {"awake": self.server.awake})
        else:
            self.reply(404, {"error": "Unknown endpoint"})
