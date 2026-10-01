"""El buzón del móvil: lo que hay en el Mac llega solo a nachosanbenito.com/guardados.

Es una taquilla de consigna (docs/diseno.md, decisión 9). El Mac mete los
guardados en cajas cerradas con un candado (AES-256-GCM) cuya llave solo tienen
este Mac y los móviles que hayan escaneado el QR. La taquilla (un Worker de
Cloudflare con KV, cloud/) guarda las cajas pero no puede abrirlas.

Qué se guarda en este Mac (~/Library/Application Support/Guardados, carpeta 700):
  movil.json   600  id del buzón, token de escritura, token de lectura y la llave.
               Se crea la primera vez que la persona pide el QR; nunca va al .app ni a app.log.
  media/movil/      portadas reducidas a 270 px (sips, de macOS) para el móvil.
  guardados.db kv "movil.ix"   qué hay subido (para subir solo lo que cambia).

Qué se sube (mismo formato que ig-saved/tools/sync-pack.py, que la web ya sabe leer):
  index.bin    cifrado: {"v":1, "posts": <obj>, "posts_sha", "built", "covers": [{"f", "ids"}]}
  <hex>.bin    cifrado. Los datos: el JSON del feed en gzip. Las portadas: paquetes de
               <= 8 MB: 4 bytes (longitud N) + JSON [[id, bytes], ...] + los JPEG seguidos.
Cada .bin = 12 bytes de iv + texto cifrado con su etiqueta (lo que espera crypto.subtle).
El cifrado lo hace CryptoKit de Apple (tools/sello.swift), sin librerías de Python nativas.

El enlace del QR lleva la llave en el FRAGMENTO, que el navegador no manda nunca:
  https://nachosanbenito.com/guardados/#conectar=1.<id>.<lectura>.<llave>
"""
import base64
import gzip
import hashlib
import json
import logging
import os
import re
import secrets
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

log = logging.getLogger("guardados")

# La dirección del buzón. cloud/deploy.sh cambia esta línea por la URL real tras desplegar.
BUZON_URL = "https://guardados-sync.guardados-sync.workers.dev"  # deploy.sh: BUZON_URL
WEB_URL = "https://nachosanbenito.com/guardados/"
MAX_PACK = 8_000_000
ANCHO = 270          # como store.js: la web reduce sus portadas a 270 px
SSL = ssl.create_default_context(cafile=certifi.where())
LOOPBACK = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d{2,5})?(/.*)?$")


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _url(env, default):
    """Las URL solo se cambian para pruebas en 127.0.0.1 (como la de Gemini); la app real usa las suyas."""
    v = os.environ.get(env, "").strip()
    return v.rstrip("/") + ("/" if default.endswith("/") else "") if v and LOOPBACK.match(v) else default


def sello_bin():
    """El candado ya compilado (universal2): dentro del .app o en build/ (lo hace build.sh)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for p in (base / "sello", base / "build" / "sello", Path(__file__).resolve().parent / "build" / "sello"):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


class Error(Exception):
    pass


class Nube:
    def __init__(self, data: Path, db, media: Path):
        self.f = Path(data) / "movil.json"
        self.db, self.media = db, Path(media)
        self.small = self.media / "movil"
        self.base = _url("GUARDADOS_BUZON_URL", BUZON_URL)
        self.web = _url("GUARDADOS_WEB_URL", WEB_URL)
        self.lock = threading.Lock()
        self.subiendo = False
        self.error = None

    # ---------- la llave y los resguardos (solo en este Mac) ----------
    def cred(self):
        try:
            d = json.loads(self.f.read_text())
            return d if all(isinstance(d.get(k), str) for k in ("id", "w", "r", "k")) else None
        except (OSError, ValueError):
            return None

    def activo(self):
        return self.cred() is not None

    def _nueva(self):
        d = {"v": 1, "id": _b64(secrets.token_bytes(32)), "w": _b64(secrets.token_bytes(32)),
             "r": _b64(secrets.token_bytes(32)), "k": _b64(secrets.token_bytes(32)), "creado": int(time.time())}
        tmp = self.f.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(d, fh)
        os.chmod(tmp, 0o600)
        tmp.replace(self.f)
        self.db.put("movil.ix", None)
        return d

    def asegurar(self):
        return self.cred() or self._nueva()

    def enlace(self):
        c = self.asegurar()
        frag = f"conectar=1.{c['id']}.{c['r']}.{c['k']}"
        if LOOPBACK.match(self.base):   # solo en pruebas: el móvil no conoce este buzón local
            frag += "&u=" + urllib.parse.quote(self.base, safe="")
        return f"{self.web}#{frag}"

    def qr(self):
        """El QR como imagen SVG (data:), hecho aquí mismo con segno: nada sale a internet."""
        import segno
        return segno.make(self.enlace(), error="m").svg_data_uri(scale=6, border=3, dark="#1c1917", light="#ffffff")

    # ---------- hablar con el buzón ----------
    def _req(self, method, path, body=None, token=None, ctype="application/octet-stream"):
        url = f"{self.base}/v1/{path}"
        h = {"User-Agent": "Guardados-Mac/1"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if body is not None:
            h["Content-Type"] = ctype
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        ctx = SSL if url.startswith("https:") else None
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except (urllib.error.URLError, OSError) as e:
            raise Error(f"No llego al buzón ({type(e).__name__}). Se reintentará.") from None

    def _crear(self, c):
        body = json.dumps({"w": hashlib.sha256(c["w"].encode()).hexdigest(),
                           "r": hashlib.sha256(c["r"].encode()).hexdigest()}).encode()
        st = self._req("PUT", c["id"], body, ctype="application/json")
        if st not in (201, 409):
            raise Error(f"El buzón no se ha podido crear ({st}).")

    def _put(self, c, name, blob):
        st = self._req("PUT", f"{c['id']}/{name}", blob, token=c["w"])
        if st != 201:
            raise Error({413: "Un paquete es demasiado grande.", 507: "El buzón está lleno.",
                         401: "El buzón no acepta esta llave."}.get(st, f"El buzón ha contestado {st}."))

    def _del(self, c, name):
        try:
            self._req("DELETE", f"{c['id']}/{name}", token=c["w"])
        except Error:
            pass   # basura que se queda: no rompe nada (el índice ya no la nombra)

    # ---------- empaquetar ----------
    @staticmethod
    def _seal(raw, data):
        """AES-256-GCM con CryptoKit (tools/sello.swift): 12 bytes de iv + cifrado + etiqueta."""
        b = sello_bin()
        if not b:
            raise Error("Falta el candado (sello) dentro de la app.")
        p = subprocess.run([b, "cerrar"], input=raw + data, capture_output=True, timeout=300)
        if p.returncode != 0 or len(p.stdout) != len(data) + 28:
            raise Error("No he podido cifrar el paquete.")
        return p.stdout

    def _reducir(self, codes):
        """Portadas a 270 px de ancho con sips (viene con macOS). Se hace una vez por portada."""
        self.small.mkdir(parents=True, exist_ok=True)
        todo = [c for c in codes if not (self.small / f"{c}.jpg").exists() and (self.media / f"{c}.jpg").is_file()]
        for i in range(0, len(todo), 150):
            chunk = todo[i:i + 150]
            with tempfile.TemporaryDirectory(dir=self.small) as tmp:
                subprocess.run(["/usr/bin/sips", "--resampleWidth", str(ANCHO), "-s", "format", "jpeg",
                                "-s", "formatOptions", "70", *[str(self.media / f"{c}.jpg") for c in chunk],
                                "--out", tmp], capture_output=True, timeout=600)
                for c in chunk:
                    f = Path(tmp) / f"{c}.jpg"
                    if f.is_file() and f.stat().st_size > 200:
                        f.replace(self.small / f"{c}.jpg")
        return [c for c in codes if (self.small / f"{c}.jpg").is_file()]

    # ---------- subir (solo lo que ha cambiado) ----------
    def subir(self):
        """Sube lo nuevo al buzón. Sin móvil conectado no hace nada; sin cambios, ni una petición."""
        if not self.lock.acquire(blocking=False):
            return {"skip": "ya está subiendo"}
        self.subiendo = True
        try:
            c = self.cred()
            if not c:
                return {"skip": "sin móvil"}
            raw = _unb64(c["k"])
            ix = self.db.get("movil.ix") or {}
            if ix.get("id") != c["id"]:
                ix = {"id": c["id"], "v": 1, "covers": []}
            feed = self.db.feed("")
            body = json.dumps(feed["posts"], ensure_ascii=False, separators=(",", ":")).encode()
            sha = hashlib.sha256(body).hexdigest()[:16]
            have = {i for p in ix["covers"] for i in p["ids"]}
            want = [p["id"] for p in feed["posts"] if p["id"] not in have]
            ok = self.db.covers_ok() if want else set()
            nuevas = self._reducir([x for x in want if x in ok]) if want else []
            if ix.get("posts_sha") == sha and not nuevas and ix.get("subido"):
                self.error = None
                return {"skip": "sin cambios"}
            if not ix.get("creado"):
                self._crear(c)
                ix["creado"] = True
                self.db.put("movil.ix", ix)
            sent = 0
            old_posts = None
            if ix.get("posts_sha") != sha:
                old_posts = ""
                name = secrets.token_hex(8) + ".bin"
                blob = self._seal(raw, gzip.compress(json.dumps({"built": feed["built"], "demo": False, "posts": feed["posts"]},
                                                                ensure_ascii=False, separators=(",", ":")).encode(), 6))
                self._put(c, name, blob)
                sent += len(blob)
                ix["bytes_posts"] = len(blob)
                old_posts, ix["posts"], ix["posts_sha"], ix["built"] = ix.get("posts") or "", name, sha, feed["built"]
            if old_posts is not None or not ix.get("subido"):
                self._index(c, raw, ix)   # los datos primero: el móvil ya puede verlos mientras suben las portadas
                self.db.put("movil.ix", ix)
                if old_posts:
                    self._del(c, old_posts)   # después del índice nuevo: el viejo ya no lo nombra
            pack, size = [], 0
            packs = []
            for code in nuevas:
                b = (self.small / f"{code}.jpg").read_bytes()
                if pack and size + len(b) > MAX_PACK:
                    packs.append(pack)
                    pack, size = [], 0
                pack.append((code, b))
                size += len(b)
            if pack:
                packs.append(pack)
            for pk in packs:
                head = json.dumps([[i, len(b)] for i, b in pk], separators=(",", ":")).encode()
                name = secrets.token_hex(8) + ".bin"
                blob = self._seal(raw, struct.pack(">I", len(head)) + head + b"".join(b for _, b in pk))
                self._put(c, name, blob)
                sent += len(blob)
                ix["covers"].append({"f": name, "ids": [i for i, _ in pk]})
                ix["bytes_covers"] = ix.get("bytes_covers", 0) + len(blob)
                self._index(c, raw, ix)
                self.db.put("movil.ix", ix)   # si se corta aquí, la próxima vez no se repite este paquete
            ix.update(subido=int(time.time()), n_posts=len(feed["posts"]), n_covers=sum(len(p["ids"]) for p in ix["covers"]))
            self.db.put("movil.ix", ix)
            self.error = None
            log.info("móvil: subidos %d KB (%d portadas nuevas)", sent // 1000, len(nuevas))
            return {"ok": True, "bytes": sent, "covers": len(nuevas)}
        except Error as e:
            self.error = str(e)
            log.warning("móvil: %s", e)
            return {"error": str(e)}
        finally:
            self.subiendo = False
            self.lock.release()

    def _index(self, c, raw, ix):
        pub = {"v": 1, "posts": ix.get("posts"), "posts_sha": ix.get("posts_sha"), "built": ix.get("built"),
               "covers": ix["covers"]}
        self._put(c, "index.bin", self._seal(raw, json.dumps(pub, separators=(",", ":")).encode()))

    def cambiar(self):
        """Desconecta todos los móviles: borra el buzón viejo y crea llave e id nuevos."""
        with self.lock:
            c = self.cred()
            if c:
                try:
                    self._req("DELETE", c["id"], token=c["w"])
                except Error:
                    pass   # sin red: el buzón viejo se queda, pero nadie tiene ya la llave nueva
            self._nueva()
            self.error = None
        log.info("móvil: llave cambiada (los móviles anteriores quedan desconectados)")

    def estado(self):
        """Lo que ve el panel. Nunca la llave, los tokens ni el id."""
        ix = self.db.get("movil.ix") or {}
        c = self.cred()
        on = bool(c) and ix.get("id") in (None, c["id"])
        return {"on": bool(c), "subido": ix.get("subido") if on else None, "posts": ix.get("n_posts", 0) if on else 0,
                "covers": ix.get("n_covers", 0) if on else 0,
                "mb": round((ix.get("bytes_covers", 0) + ix.get("bytes_posts", 0)) / 1e6, 1) if on else 0,
                "subiendo": self.subiendo, "error": self.error}
