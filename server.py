"""Mostrador local: sirve el panel y la web de guardados en http://127.0.0.1:PUERTO.

Por qué un servidor y no file://: la web (store.js) es un módulo ES y guarda en
IndexedDB; ambas cosas necesitan un origen http estable. El puerto es fijo para
que el IndexedDB (que va por origen) no se pierda entre aperturas.

- /panel/…            el panel (única página con js_api), con CSP estricta
- /guardados/…        copia de la web de ~/Projects/ig-saved/app (sin datos)
- /guardados/demo/posts.json  vacío: la muestra de Nacho NO viaja en la app
- /feed/<token>/…     los datos de esta persona (items.json y portadas). El token
                      cambia en cada arranque y solo lo conocen el panel y «Mis guardados».
- /mac/…              lo que «Mis guardados» tiene solo en el Mac (asignar carpetas a mano).
                      Se engancha a /guardados/index.html al servirlo, con el token en un
                      <meta>: otra web (Instagram, TikTok) no puede leerlo (mismo origen).
- /api/<token>/…      carpetas a mano: GET carpetas, GET/POST post/<code>. Los POST solo con
                      Origin de aquí y JSON (una web ajena no puede mandarlos ni sabe el token).
Solo escucha en 127.0.0.1 y rechaza cualquier Host que no sea el suyo (DNS rebinding).
"""
import http.server
import json
import mimetypes
import re
import secrets
import threading
import urllib.parse
from pathlib import Path

PANEL_CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
             "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
             "frame-ancestors 'none'; form-action 'none'")
SAFE = re.compile(r"^[A-Za-z0-9_.\-/]+$")


class Server:
    def __init__(self, web: Path, media: Path, feed, port=47613, db=None, on_change=None):
        self.web, self.media, self.feed = web, media, feed
        self.db, self.on_change = db, on_change or (lambda: None)
        self.token = secrets.token_urlsafe(24)
        srv = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def do_HEAD(self):
                self.do_GET()

            def _json(self, code, obj):
                return self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

            def _api(self, parts):
                """/api/<token>/carpetas · /api/<token>/post/<code> (GET lee, POST escribe)."""
                if len(parts) < 4 or not secrets.compare_digest(parts[2], srv.token) or srv.db is None:
                    return self._send(404)
                if self.command == "POST":
                    if self.headers.get("Origin") != srv.base or \
                            not (self.headers.get("Content-Type") or "").startswith("application/json"):
                        return self._send(403, b"origin")
                    n = int(self.headers.get("Content-Length") or 0)
                    if not 0 < n <= 8192:
                        return self._send(413)
                    try:
                        body = json.loads(self.rfile.read(n))
                    except ValueError:
                        return self._send(400)
                if parts[3] == "carpetas" and len(parts) == 4 and self.command == "GET":
                    import carpetas
                    arbol = [{"k": c, "n": carpetas.NOMBRES.get(c, c),
                              "subs": [{"k": f"{c}/{s}", "n": carpetas.NOMBRES.get(s, s)} for s in carpetas.SUB.get(c, [])]}
                             for c in carpetas.CARPETAS]
                    return self._json(200, {"arbol": arbol, "propias": srv.db.carpetas_propias()})
                if parts[3] == "post" and len(parts) == 5:
                    code = urllib.parse.unquote(parts[4])
                    if self.command == "POST":
                        rutas = None if body.get("auto") is True else body.get("rutas")
                        if rutas is not None and not isinstance(rutas, list):
                            return self._send(400)
                        try:
                            out = srv.db.set_manual(code, rutas)
                        except ValueError as e:
                            return self._json(400, {"ok": False, "error": str(e)})
                        if out is None:
                            return self._send(404)
                        srv.on_change()
                    r = srv.db.rutas_de(code)
                    if r is None:
                        return self._send(404)
                    return self._json(200, {"ok": True, "rutas": r[0], "manual": r[1]})
                return self._send(404)

            def do_POST(self):
                if self.headers.get("Host") != f"127.0.0.1:{srv.port}":
                    return self._send(403, b"host")
                path = self.path.split("?", 1)[0]
                if not path.startswith("/api/") or ".." in path or not SAFE.match(path):
                    return self._send(404)
                return self._api(path.split("/"))

            def do_GET(self):
                if self.headers.get("Host") != f"127.0.0.1:{srv.port}":
                    return self._send(403, b"host")
                path = self.path.split("?", 1)[0].split("#", 1)[0]
                if ".." in path or not SAFE.match(path):
                    return self._send(404)
                if path.startswith("/api/"):
                    return self._api(path.split("/"))
                if path.startswith("/feed/"):
                    parts = path.split("/")
                    if len(parts) < 4 or not secrets.compare_digest(parts[2], srv.token):
                        return self._send(404)
                    if parts[3] == "items.json":
                        body = json.dumps(srv.feed(f"{srv.base}/feed/{srv.token}/m/"), ensure_ascii=False).encode()
                        return self._send(200, body, "application/json")
                    if parts[3] == "m" and len(parts) == 5 and re.match(r"^[A-Za-z0-9_-]+\.jpg$", parts[4]):
                        f = srv.media / parts[4]
                        if f.is_file():
                            return self._send(200, f.read_bytes(), "image/jpeg")
                    return self._send(404)
                if path == "/guardados/demo/posts.json":
                    return self._send(200, b'{"posts":[]}', "application/json")
                if path in ("/", "/panel", "/guardados"):
                    return self._send(302, b"", extra={"Location": path.rstrip("/") + "/" if path != "/" else "/panel/"})
                if not (path.startswith("/panel/") or path.startswith("/guardados/") or path.startswith("/mac/")):
                    return self._send(404)
                f = (srv.web / path.lstrip("/"))
                if path.endswith("/"):
                    f = f / "index.html"
                try:
                    f.resolve().relative_to(srv.web.resolve())
                except ValueError:
                    return self._send(404)
                if not f.is_file():
                    return self._send(404)
                ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                    ctype += "; charset=utf-8"
                if f.suffix == ".js":
                    ctype = "text/javascript; charset=utf-8"
                extra = {"Content-Security-Policy": PANEL_CSP} if path.startswith("/panel/") else {}
                body = f.read_bytes()
                if path in ("/guardados/", "/guardados/index.html") and srv.db is not None:
                    # «Mis guardados» en el Mac: + asignar carpetas a mano (web/mac/asignar.js)
                    body = body.replace(b"</body>", (f'<meta name="guardados-mac" content="{srv.token}">'
                                                     '<link rel="stylesheet" href="/mac/asignar.css">'
                                                     '<script type="module" src="/mac/asignar.js"></script></body>').encode())
                return self._send(200, body, ctype, extra)

        self.port = port
        try:
            self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        except OSError as e:
            raise RuntimeError(f"El puerto {port} está ocupado: ¿la app ya está abierta?") from e
        self.httpd.daemon_threads = True

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"
