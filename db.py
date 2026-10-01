"""La libreta de la app: una base SQLite por persona, en su Mac.

  ~/Library/Application Support/Guardados/guardados.db

posts  un guardado de Instagram o un favorito de TikTok (code "tt_<id>").
kv     estado pequeño: por dónde iba cada importación (para reanudar) y cuándo
       terminó bien la última.
manual las carpetas que la persona puso A MANO a un guardado (01/10/2026). Van en su
       propia tabla para que nada automático las pise: ni re-importar, ni las reglas,
       ni la IA. Si un guardado tiene fila aquí, feed() usa esa lista y no la de posts.rutas.

Los títulos salen de rules.py (el mismo de ~/Projects/ig-saved). Las carpetas
y subcarpetas, de carpetas.py (reglas); los sitios del mapa, de sitios.py
(descripción + Apple Maps). Si la persona pone su clave de Gemini, ia.py los
rehace y marca ia=1 (las reglas ya no los pisan).
"""
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
import rules  # copia de ~/Projects/ig-saved/rules.py (tools/copiar_web.py): solo `re`, sin IA  # noqa: E402
import carpetas  # noqa: E402
import sitios  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  code TEXT PRIMARY KEY, src TEXT NOT NULL, pk TEXT, username TEXT, fullname TEXT,
  caption TEXT, taken_at INTEGER, media_type INTEGER, product TEXT, likes INTEGER,
  plays INTEGER, url TEXT, video_url TEXT, thumb TEXT, cover INTEGER DEFAULT 0,
  tr TEXT DEFAULT '', lang TEXT DEFAULT '', title TEXT, category TEXT,
  cols TEXT DEFAULT '[]', added_at INTEGER
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS geo_cache (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS manual (code TEXT PRIMARY KEY, rutas TEXT NOT NULL, at INTEGER);
"""
# columnas nuevas (01/10/2026): carpetas/subcarpetas, ciudad y sitios del mapa
NEW_COLS = {"rutas": "TEXT DEFAULT '[]'", "ciudad": "TEXT DEFAULT ''", "lug": "TEXT DEFAULT '[]'",
            "geo": "INTEGER DEFAULT 0", "ia": "INTEGER DEFAULT 0"}

# Lo que la app acepta como identificador. Va dentro de HTML (data-id="...")
# y de rutas de fichero, así que nada de comillas, barras ni puntos.
IG_CODE = re.compile(r"^[A-Za-z0-9_-]{5,40}$")
TT_CODE = re.compile(r"^tt_\d{6,30}$")
TT_USER = re.compile(r"^[A-Za-z0-9._]{1,40}$")


def valid_code(code):
    return isinstance(code, str) and bool(IG_CODE.match(code) or TT_CODE.match(code))


def _s(v, n=20000):
    return v[:n] if isinstance(v, str) else ""


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class DB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.c = sqlite3.connect(str(self.path), check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        have = {r[1] for r in self.c.execute("PRAGMA table_info(posts)")}
        for col, typ in NEW_COLS.items():
            if col not in have:
                self.c.execute(f"ALTER TABLE posts ADD COLUMN {col} {typ}")
        # guardados de una versión anterior (sin carpetas): se ordenan ya, con reglas
        viejos = self.c.execute("SELECT code, caption, tr, username, fullname FROM posts"
                                " WHERE ia=0 AND (rutas IS NULL OR rutas='[]')").fetchall()
        for code, cap, tr, user, full in viejos:
            rs, ci = carpetas.rutas(cap or "", tr or "", user or "", full or "", hay_sitio=bool(sitios.candidatos(cap or "")))
            self.c.execute("UPDATE posts SET rutas=?, ciudad=? WHERE code=?", (json.dumps(rs, ensure_ascii=False), ci, code))
        self.c.commit()
        os.chmod(self.path, 0o600)

    # ---------- estado ----------
    def get(self, k, default=None):
        with self.lock:
            r = self.c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def put(self, k, v):
        with self.lock:
            if v is None:
                self.c.execute("DELETE FROM kv WHERE k=?", (k,))
            else:
                self.c.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, json.dumps(v)))
            self.c.commit()

    # ---------- guardados ----------
    def known(self, src):
        with self.lock:
            return {r[0] for r in self.c.execute("SELECT code FROM posts WHERE src=?", (src,))}

    def add(self, item):
        """Mete un guardado ya validado. Devuelve True si era nuevo."""
        code = item.get("code")
        if not valid_code(code):
            return False
        src = "tiktok" if code.startswith("tt_") else "instagram"
        caption, tr, user = _s(item.get("caption")), _s(item.get("tr"), 6000), _s(item.get("user"), 60)
        title, cat, _ = rules.rule_title(caption, tr, user, "")
        rutas, ciudad = carpetas.rutas(caption, tr, user, _s(item.get("name"), 200),
                                       hay_sitio=bool(sitios.candidatos(caption)))
        cols = [str(c) for c in (item.get("cols") or []) if str(c).isdigit()][:50]
        with self.lock:
            old = self.c.execute("SELECT 1 FROM posts WHERE code=?", (code,)).fetchone()
            self.c.execute(
                "INSERT INTO posts (code, src, pk, username, fullname, caption, taken_at, media_type, product,"
                " likes, plays, url, video_url, thumb, tr, title, category, cols, added_at, rutas, ciudad)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(code) DO UPDATE SET caption=excluded.caption, plays=excluded.plays,"
                " thumb=COALESCE(excluded.thumb, posts.thumb), video_url=COALESCE(excluded.video_url, posts.video_url),"
                " tr=CASE WHEN excluded.tr != '' THEN excluded.tr ELSE posts.tr END,"
                " title=excluded.title, category=excluded.category,"
                " geo=CASE WHEN excluded.caption != posts.caption THEN 0 ELSE posts.geo END,"
                " rutas=CASE WHEN posts.ia=1 THEN posts.rutas ELSE excluded.rutas END,"
                " ciudad=CASE WHEN posts.ia=1 THEN posts.ciudad ELSE excluded.ciudad END",
                (code, src, _s(item.get("pk"), 40), user, _s(item.get("name"), 200), caption,
                 _i(item.get("taken_at")), _i(item.get("type")), _s(item.get("product"), 40),
                 _i(item.get("likes")), _i(item.get("plays")), _s(item.get("url"), 300),
                 _s(item.get("video_url"), 4000) or None, _s(item.get("thumb"), 4000) or None,
                 tr, title, cat, json.dumps(cols), int(time.time()), json.dumps(rutas, ensure_ascii=False), ciudad))
            self.c.commit()
        return not old

    def set_cover(self, code, ok):
        with self.lock:
            self.c.execute("UPDATE posts SET cover=? WHERE code=?", (1 if ok else -1, code))
            self.c.commit()

    def set_transcript(self, code, text, lang):
        with self.lock:
            row = self.c.execute("SELECT caption, username, fullname, ia, lug FROM posts WHERE code=?", (code,)).fetchone()
            if not row:
                return
            title, cat, _ = rules.rule_title(row[0], text, row[1], lang)
            self.c.execute("UPDATE posts SET tr=?, lang=?, title=?, category=? WHERE code=?",
                           (text, lang, title, cat, code))
            if not row[3]:  # sin IA: con el texto nuevo, las reglas vuelven a elegir carpeta
                rutas, ciudad = carpetas.rutas(row[0], text, row[1], row[2] or "",
                                               hay_sitio=bool(sitios.candidatos(row[0])) or row[4] not in (None, "", "[]"))
                rutas = _con_sitio(rutas, json.loads(row[4] or "[]"), row[0], text)
                self.c.execute("UPDATE posts SET rutas=?, ciudad=CASE WHEN ?='' THEN ciudad ELSE ? END WHERE code=?",
                               (json.dumps(rutas, ensure_ascii=False), ciudad, ciudad, code))
            self.c.commit()

    def counts(self):
        with self.lock:
            rows = self.c.execute("SELECT src, COUNT(*), SUM(cover=1), SUM(tr!='') FROM posts GROUP BY src").fetchall()
        return {r[0]: {"n": r[1], "covers": r[2] or 0, "tr": r[3] or 0} for r in rows}

    def recent(self, n=12):
        with self.lock:
            rows = self.c.execute("SELECT code, src, username, fullname, caption, title, category FROM posts"
                                  " ORDER BY added_at DESC, rowid DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]

    def pending_covers(self):
        with self.lock:
            return [tuple(r) for r in self.c.execute(
                "SELECT code, thumb FROM posts WHERE cover=0 AND thumb IS NOT NULL")]

    def pending_transcripts(self):
        with self.lock:
            return [tuple(r) for r in self.c.execute(
                "SELECT code, video_url FROM posts WHERE src='instagram' AND tr='' AND lang='' AND video_url IS NOT NULL"
                " AND media_type=2 ORDER BY added_at DESC")]

    def covers_ok(self):
        """Los codes con portada bajada (para el buzón del móvil, nube.py)."""
        with self.lock:
            return {r[0] for r in self.c.execute("SELECT code FROM posts WHERE cover=1")}

    # ---------- mapa y carpetas ----------
    def pending_geo(self, limit=None):
        """Guardados cuya descripción aún no se ha mirado en busca de sitios (sin IA)."""
        with self.lock:
            rows = self.c.execute("SELECT code, caption, tr, username, rutas FROM posts WHERE geo=0 AND ia=0"
                                  " ORDER BY added_at DESC" + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        return [tuple(r) for r in rows]

    def set_lug(self, code, lug, ia=False, rutas=None, ciudad=None):
        lug = [x for x in (valid_lug(l) for l in lug or []) if x]
        with self.lock:
            row = self.c.execute("SELECT rutas, caption, tr FROM posts WHERE code=?", (code,)).fetchone()
            if not row:
                return
            rs = rutas if rutas is not None else json.loads(row[0] or "[]")
            if not ia:
                rs = _con_sitio(rs, lug, row[1], row[2])
            self.c.execute("UPDATE posts SET lug=?, geo=1, rutas=?, ia=CASE WHEN ? THEN 1 ELSE ia END,"
                           " ciudad=COALESCE(?, ciudad) WHERE code=?",
                           (json.dumps(lug, ensure_ascii=False), json.dumps(rs, ensure_ascii=False), 1 if ia else 0,
                            ciudad, code))
            self.c.commit()

    def set_rutas_ia(self, code, rutas, ciudad):
        with self.lock:
            self.c.execute("UPDATE posts SET rutas=?, ciudad=?, ia=1 WHERE code=?",
                           (json.dumps(rutas, ensure_ascii=False), ciudad or "", code))
            self.c.commit()

    def pending_ia(self):
        with self.lock:
            return [tuple(r) for r in self.c.execute(
                "SELECT code, caption, tr, username FROM posts WHERE ia=0 ORDER BY added_at DESC")]

    def ia_counts(self):
        with self.lock:
            r = self.c.execute("SELECT SUM(ia=1), COUNT(*) FROM posts").fetchone()
        return {"done": r[0] or 0, "total": r[1] or 0}

    def geo_cache(self):
        with self.lock:
            return {k: json.loads(v) for k, v in self.c.execute("SELECT k, v FROM geo_cache")}

    def put_geo_cache(self, d):
        with self.lock:
            self.c.executemany("INSERT OR REPLACE INTO geo_cache VALUES (?,?)",
                               [(k, json.dumps(v, ensure_ascii=False)) for k, v in d.items()])
            self.c.commit()

    # ---------- carpetas a mano ----------
    def rutas_de(self, code):
        """(rutas que se ven, puestas a mano?) de un guardado; None si no existe."""
        with self.lock:
            r = self.c.execute("SELECT p.rutas, m.rutas FROM posts p LEFT JOIN manual m USING(code) WHERE p.code=?",
                               (code,)).fetchone()
        if not r:
            return None
        return _rutas_ok(r[1] if r[1] is not None else r[0]), r[1] is not None

    def set_manual(self, code, rutas):
        """Lo que la persona eligió para este guardado (manda sobre todo lo automático).
        rutas=None: vuelve a lo automático. Devuelve las rutas que quedan, o None si no existe."""
        if not valid_code(code):
            return None
        with self.lock:
            if not self.c.execute("SELECT 1 FROM posts WHERE code=?", (code,)).fetchone():
                return None
            if rutas is None:
                self.c.execute("DELETE FROM manual WHERE code=?", (code,))
            else:
                limpias = []
                for r in rutas if isinstance(rutas, list) else []:
                    x = carpetas.limpia_ruta(r)
                    if x is None:
                        raise ValueError("Ese nombre de carpeta no vale: usa letras, números, espacios o emojis.")
                    if x not in limpias:
                        limpias.append(x)
                limpias = [x for x in limpias if x != "otros"] or ["otros"]
                if len(limpias) > carpetas.MAX_RUTAS:
                    raise ValueError(f"Como mucho {carpetas.MAX_RUTAS} carpetas por vídeo.")
                self.c.execute("INSERT OR REPLACE INTO manual VALUES (?,?,?)",
                               (code, json.dumps(limpias, ensure_ascii=False), int(time.time())))
            self.c.commit()
        return self.rutas_de(code)[0]

    def carpetas_propias(self):
        """Las carpetas que ha creado la persona (no están en el árbol), en uso."""
        with self.lock:
            rows = self.c.execute("SELECT rutas FROM manual").fetchall()
        return sorted({x for r in rows for x in _rutas_ok(r[0]) if x not in carpetas.VALIDAS})

    def feed(self, media_base):
        """Lo que se le da a la web: el formato de export.py de ig-saved ({built, posts}), el mismo
        con el que Nacho mete sus carpetas de Gemini: store.js lo importa con carpeta (cat), subcarpetas
        (sub), ciudad y sitios (lug). media_base: URL absoluta de las portadas (o "" = sin portadas)."""
        with self.lock:
            rows = self.c.execute("SELECT p.*, m.rutas AS man FROM posts p LEFT JOIN manual m USING(code)"
                                  " ORDER BY p.taken_at DESC").fetchall()
        posts = []
        for r in rows:
            rutas = _rutas_ok(r["man"] if r["man"] is not None else r["rutas"])   # lo puesto a mano manda
            lug = [x for x in (valid_lug(l) for l in json.loads(r["lug"] or "[]")) if x]
            cat = list(dict.fromkeys(x.split("/")[0] for x in rutas))
            if lug and "sitios" not in cat:
                lug = []  # la web solo pinta sitios de la carpeta Sitios
            posts.append({
                "id": r["code"], "src": r["src"], "u": r["username"] or "", "n": r["fullname"] or "",
                "c": r["caption"] or "", "d": r["taken_at"], "v": r["media_type"] == 2,
                "p": r["plays"] or 0, "url": r["url"], "tr": r["tr"] or "",
                "cat": cat, "sub": [x for x in rutas if "/" in x], "ciudad": r["ciudad"] or "", "lug": lug,
                "cov": f"{media_base}{r['code']}.jpg" if media_base and r["cover"] == 1 else None,
            })
        return {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "demo": False, "posts": posts}


def valid_lug(l):
    """Un sitio del mapa, validado: lo que no sea número o texto corto se tira (va a la web)."""
    if not isinstance(l, dict):
        return None
    try:
        lat, lng = float(l.get("lat")), float(l.get("lng"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or lat != lat or lng != lng:
        return None
    n = _s(l.get("n"), 80).strip()
    if not n:
        return None
    t = l.get("t") if l.get("t") in sitios.TIPOS else "planes"
    out = {"n": n, "t": t, "ci": _s(l.get("ci"), 40), "lat": round(lat, 6), "lng": round(lng, 6), "a": _s(l.get("a"), 120)}
    if l.get("aprox"):
        out["aprox"] = 1
    return out


def _rutas_ok(txt):
    """Las rutas guardadas, solo las que valen (del árbol o carpetas a mano con nombre limpio)."""
    try:
        rs = json.loads(txt or "[]")
    except ValueError:
        rs = []
    return [x for x in rs if isinstance(x, str) and carpetas.ruta_valida(x)] or ["otros"]


def _con_sitio(rutas, lug, caption, tr):
    """Si Apple Maps encontró sitios y el vídeo no estaba en Sitios, entra en Sitios (primero)."""
    if not lug or any(r.startswith("sitios/") for r in rutas):
        return rutas
    r = sitios.sub_de_sitio(lug, rutas, rules._blob([caption, tr]))
    return ([r] + [x for x in rutas if x != "otros"])[:3]
