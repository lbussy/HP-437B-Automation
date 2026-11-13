"""Loopback-only, single-user operator interface for explicitly fake suite jobs."""

import argparse
import hmac
import html
import secrets
import zipfile
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import operator_jobs as jobs
from . import provenance as p
from . import reporting as r

MAX_REQUEST = 600 * 1024


def server(manager, port=8765):
    token = secrets.token_hex(32)
    assets = resources.files("hp437b") / "operator_web"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, data, media="application/json", *, cookie=False, attachment=False):
            self.send_response(status)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src "
                + (
                    "'self' 'unsafe-inline'"
                    if media.startswith("text/html") and not cookie
                    else "'self'"
                )
                + "; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            if cookie:
                self.send_header(
                    "Set-Cookie", f"hp437b_operator={token}; HttpOnly; SameSite=Strict; Path=/"
                )
            if attachment:
                self.send_header(
                    "Content-Disposition", 'attachment; filename="rf-output-power-package.zip"'
                )
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _host(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            p.require(
                self.headers.get("Host") == expected, "Use the printed 127.0.0.1 operator URL"
            )
            return "http://" + expected

        def _auth(self, *, write=False, api=False):
            origin = self._host()
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            supplied = cookies.get("hp437b_operator")
            p.require(
                supplied is not None and hmac.compare_digest(supplied.value, token),
                "Open the operator page to begin a local session",
            )
            if api:
                p.require(
                    hmac.compare_digest(self.headers.get("X-Operator-Token", ""), token),
                    "Invalid operator session token",
                )
            if write:
                p.require(
                    self.headers.get("Origin") == origin,
                    "Only same-origin operator actions are allowed",
                )

        def do_GET(self):
            try:
                self._host()
                path = unquote(urlsplit(self.path).path)
                if path == "/":
                    body = (
                        (assets / "index.html")
                        .read_text()
                        .replace("__TOKEN__", html.escape(token, quote=True))
                    )
                    self._send(200, body.encode(), "text/html; charset=utf-8", cookie=True)
                    return
                if path == "/favicon.ico":
                    self._send(204, b"", "image/x-icon")
                    return
                if path in ("/app.css", "/app.js"):
                    self._send(
                        200,
                        (assets / path[1:]).read_bytes(),
                        "text/css" if path.endswith(".css") else "text/javascript",
                    )
                    return
                if path == "/api/state":
                    self._auth(api=True)
                    self._send(200, r.encoded(manager.state()))
                    return
                if path.startswith("/artifacts/"):
                    self._auth()
                    parts = path.split("/", 3)
                    p.require(len(parts) == 4, "Invalid artifact route")
                    data, media, attachment = manager.artifact(parts[2], parts[3])
                    self._send(200, data, media, attachment=attachment)
                    return
                self._send(404, r.encoded(dict(error="Page not found")))
            except (
                ValueError,
                KeyError,
                TypeError,
                OSError,
                CookieError,
                zipfile.BadZipFile,
                RuntimeError,
            ) as exc:
                self._send(403, r.encoded(dict(error=str(exc))))

        def do_POST(self):
            try:
                self._auth(write=True, api=True)
                p.require(
                    self.headers.get("Content-Type", "").split(";")[0] == "application/json",
                    "Expected JSON",
                )
                length = int(self.headers.get("Content-Length", "0"))
                p.require(0 < length <= MAX_REQUEST, "Request is missing or too large")
                body = p._json(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path == "/api/profiles":
                    p._keys(body, ("profile_json",))
                    p.require(
                        isinstance(body["profile_json"], str)
                        and len(body["profile_json"].encode()) <= 256 * 1024,
                        "Profile exceeds 256 KiB or is not JSON text",
                    )
                    key = manager.import_profile(p._json(body["profile_json"].encode()))
                    self._send(201, r.encoded(dict(key=key)))
                    return
                if path == "/api/jobs":
                    p._keys(body, ("profile_key", "workflows", "operator"))
                    result = manager.start(body["profile_key"], body["workflows"], body["operator"])
                    self._send(202, r.encoded(result))
                    return
                if path == "/api/cancel":
                    p._keys(body, ("job_id",))
                    self._send(202, r.encoded(manager.cancel(body["job_id"])))
                    return
                self._send(404, r.encoded(dict(error="Action not found")))
            except (
                ValueError,
                KeyError,
                TypeError,
                OSError,
                CookieError,
                zipfile.BadZipFile,
                RuntimeError,
            ) as exc:
                self._send(400, r.encoded(dict(error=str(exc))))

    app = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    app.daemon_threads = True
    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runs-dir", type=Path, default=Path("output/reports/operator-runs"))
    parser.add_argument("--profiles-dir", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    manager = None
    app = None
    try:
        p.require(0 <= args.port <= 65535, "Invalid local port")
        manager = jobs.Jobs(args.runs_dir, profiles_dir=args.profiles_dir, plots=not args.no_plots)
        app = server(manager, args.port)
        print(f"Operator interface: http://127.0.0.1:{app.server_port}", flush=True)
        print("Fakes only. Cancellation takes effect between tests.", flush=True)
        app.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError) as exc:
        print("Operator interface: " + str(exc), flush=True)
        return 2
    finally:
        if app is not None:
            app.server_close()
        if manager is not None:
            manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
