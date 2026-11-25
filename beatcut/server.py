"""שרת מקומי לדשבורד: מגיש את הפרויקט, המדיה (עם Range לצפייה), שמירה, יצירה מחדש ורנדר."""
import json
import mimetypes
import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

from . import project as P, render as R

DASH = Path(__file__).resolve().parent.parent / "dashboard"


def serve(proj_dir, port=8765):
    proj_dir = Path(proj_dir).resolve()
    state = {"render": {"status": "idle", "log": []}}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def _file(self, path):
            path = Path(path)
            if not path.is_file():
                self.send_error(404); return
            size = path.stat().st_size
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            if rng and rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else size - int(b)
                end = int(b) if a and b else size - 1
                self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1)); self.end_headers()
            with open(path, "rb") as f:
                f.seek(start); left = end - start + 1
                try:
                    while left > 0:
                        chunk = f.read(min(1 << 16, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk); left -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _allowed(self, p):
            proj = P.load(proj_dir)
            ok = {proj["song"]["path"]} | {c["path"] for c in proj["clips"]}
            return str(p) in ok

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                return self._file(DASH / "index.html")
            if u.path == "/api/project":
                return self._json(P.load(proj_dir))
            if u.path == "/api/render/status":
                return self._json(state["render"])
            if u.path == "/media":
                p = unquote(parse_qs(u.query).get("p", [""])[0])
                if not self._allowed(p):
                    return self.send_error(403)
                return self._file(p)
            rel = (proj_dir / u.path.lstrip("/")).resolve()
            if str(rel).startswith(str(proj_dir)):
                return self._file(rel)
            self.send_error(404)

        def do_POST(self):
            u = urlparse(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0)
            data = json.loads(body or b"{}")
            if u.path == "/api/project":
                P.save(data, proj_dir); return self._json({"ok": True})
            if u.path == "/api/replan":
                proj = P.replan(data); P.save(proj, proj_dir); return self._json(proj)
            if u.path == "/api/render":
                P.save(data, proj_dir)
                if state["render"]["status"] == "running":
                    return self._json({"error": "רנדר כבר רץ"}, 409)
                state["render"] = {"status": "running", "log": []}

                def job():
                    try:
                        out = R.render(data, proj_dir / "final.mp4", log=state["render"]["log"].append)
                        state["render"].update(status="done", file="final.mp4")
                    except Exception as e:  # noqa
                        state["render"].update(status="error", error=str(e))
                threading.Thread(target=job, daemon=True).start()
                return self._json({"ok": True})
            self.send_error(404)

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print(f"Dashboard: http://localhost:{port}")
    srv.serve_forever()
