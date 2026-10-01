"""Portadas: se bajan en cuanto llegan (los enlaces de IG caducan en ~5 días y
los de TikTok en ~2). Solo de los CDN de Instagram/TikTok, solo https, solo
imágenes y como mucho 6 MB. Se guardan tal cual; la web las reduce a 270 px al
importarlas (store.js)."""
import ssl
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import certifi

import db as dbmod

HOSTS = {
    "instagram": (".cdninstagram.com", ".fbcdn.net"),
    "tiktok": (".tiktokcdn.com", ".tiktokcdn-us.com", ".tiktokcdn-eu.com", ".ibyteimg.com",
               ".byteimg.com", ".tiktokv.com", ".muscdn.com"),
}
REFERER = {"instagram": "https://www.instagram.com/", "tiktok": "https://www.tiktok.com/"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
MAX = 6_000_000
SSL = ssl.create_default_context(cafile=certifi.where())


def allowed(url, src):
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host.endswith(h) for h in HOSTS.get(src, ()))


def fetch(url, src, dest: Path, opener=None):
    if not allowed(url, src):
        return False
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": REFERER[src]})
    open_ = opener or (lambda r: urllib.request.urlopen(r, timeout=30, context=SSL))
    with open_(req) as r:
        if not (r.headers.get("Content-Type") or "").startswith("image/"):
            return False
        data = r.read(MAX + 1)
    if len(data) > MAX or len(data) < 200:
        return False
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return True


class Covers:
    def __init__(self, db, folder: Path, prog=None):
        self.db, self.dir, self.prog = db, folder, prog
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(4)
        self.lock = threading.Lock()
        self.sent = self.done = 0   # para la barra: cuántas se han pedido y cuántas han vuelto

    def add(self, items):
        n = 0
        for code, url, src in items:
            if dbmod.valid_code(code) and isinstance(url, str):
                self.pool.submit(self._one, code, url, src)
                n += 1
        if n and self.prog:
            with self.lock:
                if self.sent == self.done:   # tanda nueva
                    self.sent = self.done = 0
                    self.prog.start("covers", 0, 0, "portadas")
                self.sent += n
                self.prog.update("covers", total=self.sent)

    def _one(self, code, url, src):
        try:
            ok = fetch(url, src, self.dir / f"{code}.jpg")
        except Exception:
            ok = False
        self.db.set_cover(code, ok)
        if self.prog:
            with self.lock:
                self.done += 1
                self.prog.update("covers", done=self.done)
                if self.done >= self.sent:
                    self.prog.finish("covers", "ok")

    def wait(self, timeout=180):
        """Espera a que acaben las portadas pedidas (para subirlas al móvil en la misma tanda)."""
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if self.done >= self.sent:
                    return True
            time.sleep(0.5)
        return False

    def retry_pending(self):
        self.add([(c, t, "tiktok" if c.startswith("tt_") else "instagram") for c, t in self.db.pending_covers()])
