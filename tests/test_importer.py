"""Pruebas del recadero sin internet: ventanas falsas que contestan como
Instagram/TikTok (paginación, 429, "Load failed", HTML, cortes).

  python3 -m unittest discover -s tests -v
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db as dbmod  # noqa: E402
import importer  # noqa: E402


def ig_item(n):
    return {"code": f"Code{n:05d}", "pk": str(1000 + n), "user": f"cuenta{n}", "name": f"Nombre {n}",
            "caption": f"Receta rápida de pasta número {n} para cenar hoy en casa", "taken_at": 1700000000 + n,
            "type": 2, "plays": n, "video_url": None, "thumb": None, "cols": ["123"]}


class FakeIG:
    """Feed de guardados: lista de items de más nuevo a más viejo, 50 por página."""

    def __init__(self, items, script=None):
        self.items, self.script, self.calls = items, script or {}, []

    def run(self, js, timeout=90):
        m = re.search(r'max_id=([^"&]+)', js)
        start = int(m.group(1)) if m else 0
        self.calls.append(start)
        act = self.script.get((start, self.calls.count(start)))
        if act:
            return act
        page = self.items[start:start + 50]
        more = start + 50 < len(self.items)
        return {"status": 200, "json": True, "items": page, "more": more, "next": str(start + 50) if more else None}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = dbmod.DB(Path(self.tmp.name) / "g.db")
        self.sleeps = []

    def tearDown(self):
        self.tmp.cleanup()

    def imp(self, pages):
        return importer.Importer(self.db, pages, sleep=self.sleeps.append)


class TestInstagram(Base):
    def test_full_with_429_and_load_failed(self):
        items = [ig_item(i) for i in range(120)]
        fake = FakeIG(items, {(50, 1): {"status": 429}, (100, 1): {"neterr": "Load failed"}})
        r = self.imp({"ig": fake}).instagram()
        self.assertEqual(r["new"], 120)
        self.assertEqual(self.db.counts()["instagram"]["n"], 120)
        self.assertIn(60, self.sleeps)   # 429 -> 1 min
        self.assertIn(10, self.sleeps)   # Load failed -> 10 s
        pauses = [s for s in self.sleeps if s < 5]
        self.assertTrue(pauses and all(1 <= s <= 3 for s in pauses), pauses)
        self.assertIsNone(self.db.get("ig.run"))
        self.assertTrue(self.db.get("ig.last_ok"))

    def test_incremental_stops_after_15_known(self):
        items = [ig_item(i) for i in range(200)]
        self.imp({"ig": FakeIG(items)}).instagram()
        fresh = [ig_item(i) for i in range(500, 505)]
        fake = FakeIG(fresh + items)
        r = self.imp({"ig": fake}).instagram()
        self.assertEqual(r["new"], 5)
        self.assertEqual(fake.calls, [0])   # una sola página: no relee los 200
        self.assertEqual(self.db.counts()["instagram"]["n"], 205)

    def test_resume_after_cut(self):
        items = [ig_item(i) for i in range(150)]
        dead = {(50, k): {"neterr": "Load failed"} for k in range(1, 7)}
        with self.assertRaises(importer.Blocked):
            self.imp({"ig": FakeIG(items, dead)}).instagram()
        self.assertEqual(self.db.counts()["instagram"]["n"], 50)
        self.assertEqual(self.db.get("ig.run")["cursor"], "50")
        fake = FakeIG(items)
        r = self.imp({"ig": fake}).instagram()
        self.assertTrue(r["resumed"])
        self.assertEqual(fake.calls[0], 50)    # empieza donde se cortó
        self.assertEqual(self.db.counts()["instagram"]["n"], 150)

    def test_html_means_no_session(self):
        fake = FakeIG([], {(0, 1): {"status": 200, "ctype": "text/html", "html": True}})
        with self.assertRaises(importer.NoSession):
            self.imp({"ig": fake}).instagram()

    def test_login_required_json(self):
        fake = FakeIG([], {(0, 1): {"status": 401, "json": True, "msg": "login_required", "items": []}})
        with self.assertRaises(importer.NoSession):
            self.imp({"ig": fake}).instagram()

    def test_hostile_codes_rejected_captions_kept_raw(self):
        bad = ig_item(1)
        bad["code"] = '"><img src=x onerror=alert(1)>'
        evil = ig_item(2)
        evil["caption"] = '<img src=x onerror="window.__pwned=1"> receta de pasta'
        evil["name"] = "<script>alert(1)</script>"
        self.imp({"ig": FakeIG([bad, evil])}).instagram()
        codes = {r["code"] for r in self.db.recent(10)}
        self.assertEqual(codes, {"Code00002"})
        self.assertIn("<img", self.db.recent(1)[0]["caption"])  # se guarda tal cual; se escapa al pintar


class FakeTT:
    def __init__(self, n, script=None, subs=True):
        self.items = [{"id": str(7000000000000000000 + i), "user": f"tt.user{i}", "name": f"TT {i}",
                       "caption": f"Truco de Excel número {i} para finanzas", "taken_at": 1700000000 + i,
                       "photo": False, "plays": i, "thumb": None, "lang": "es",
                       "subs": [{"u": f"https://v16.tiktokcdn.com/sub{i}.vtt", "l": "spa-ES", "s": "ASR"}] if subs and i % 2 == 0 else []}
                      for i in range(n)]
        self.script, self.calls, self.subcalls = script or {}, [], 0

    def run(self, js, timeout=90):
        if "__UNIVERSAL_DATA_FOR_REHYDRATION__" in js:
            return {"host": "www.tiktok.com", "sec": "MS4wLjABAAAA_fake"}
        if "vtt" in js:
            self.subcalls += 1
            ids = re.findall(r'"(tt_\d+)"', js)
            return {i: f"hola esto es el subtitulo de {i}" for i in ids}
        m = re.search(r"cursor=(\d+)", js)
        cur = int(m.group(1))
        self.calls.append(cur)
        act = self.script.get((cur, self.calls.count(cur)))
        if act:
            return act
        page = self.items[cur:cur + 30]
        more = cur + 30 < len(self.items)
        return {"status": 200, "json": True, "code": 0, "items": page, "more": more, "next": str(cur + 30)}


class TestTikTok(Base):
    def test_full_with_subtitles(self):
        fake = FakeTT(70, {(30, 1): {"status": 429}})
        r = self.imp({"tt": fake}).tiktok()
        self.assertEqual(r["new"], 70)
        c = self.db.counts()["tiktok"]
        self.assertEqual(c["n"], 70)
        self.assertEqual(c["tr"], 35)  # los pares traen subtítulos de TikTok
        self.assertIn(60, self.sleeps)
        urls = {p["code"]: p for p in self.db.recent(1)}
        self.assertTrue(all(k.startswith("tt_") for k in urls))

    def test_unsigned_empty_body_is_reported(self):
        fake = FakeTT(5, {(0, 1): {"status": 200, "empty": True}})
        with self.assertRaises(importer.Blocked) as cm:
            self.imp({"tt": fake}).tiktok()
        self.assertIn("firma", str(cm.exception))

    def test_resume(self):
        dead = {(30, k): {"neterr": "Load failed"} for k in range(1, 7)}
        with self.assertRaises(importer.Blocked):
            self.imp({"tt": FakeTT(80, dead)}).tiktok()
        self.assertEqual(self.db.get("tt.run")["cursor"], "30")
        fake = FakeTT(80)
        r = self.imp({"tt": fake}).tiktok()
        self.assertTrue(r["resumed"])
        self.assertEqual(fake.calls[0], 30)
        self.assertEqual(self.db.counts()["tiktok"]["n"], 80)

    def test_bad_username_not_in_url(self):
        fake = FakeTT(1)
        fake.items[0]["user"] = 'x"/><script>'
        self.imp({"tt": fake}).tiktok()
        row = self.db.c.execute("SELECT url, username FROM posts").fetchone()
        self.assertTrue(row[0].startswith("https://www.tiktok.com/@_/video/"), row[0])
        self.assertEqual(row[1], "")


if __name__ == "__main__":
    unittest.main()
