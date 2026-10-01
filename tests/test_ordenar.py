"""Carpetas, mapa, IA opcional y barra de progreso, sin internet:
Apple Maps falso (tools/fake_geo.py) y Gemini falso (selftest.FakeGemini) en 127.0.0.1.

  .venv/bin/python -m unittest discover -s tests -v
"""
import json
import logging
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ["GUARDADOS_SELFTEST"] = "unittest"
os.environ["GUARDADOS_GEO_BIN"] = str(HERE / "tools" / "fake_geo.py")

import carpetas  # noqa: E402
import completar  # noqa: E402
import db as dbmod  # noqa: E402
import ia  # noqa: E402
import progreso  # noqa: E402
import selftest  # noqa: E402
import sitios  # noqa: E402

FAKE_KEY = "AIzaFAKEtest_" + "x" * 26


class TestCarpetas(unittest.TestCase):
    def test_arbol_igual_que_ig_saved(self):
        src = (Path.home() / "Projects" / "ig-saved" / "carpetas.py")
        if not src.exists():
            self.skipTest("sin ig-saved")
        ns = {}
        code = src.read_text()
        # SUB y CARPETA de ig-saved (sin ejecutar el resto: importa ig/jev)
        start = code.index("SUB = {")
        end = code.index("# Ideas no es una carpeta")
        exec(code[start:end], ns)
        self.assertEqual({k: list(v) for k, v in ns["SUB"].items()}, carpetas.SUB)

    def test_ejemplos(self):
        r, _ = carpetas.rutas("Receta de tarta de queso al horno, el mejor postre", "", "cocinaconana")
        self.assertEqual(r[0], "recetas/postres")
        r, ci = carpetas.rutas("El mejor sushi de Madrid 📍 @sushi_gin_madrid, ticket medio 30€", "", "foodie")
        self.assertEqual(r[0], "sitios/asiatico")
        self.assertEqual(ci, "Madrid")
        r, _ = carpetas.rutas("Cómo automatizar tu email con n8n y un agente de IA", "", "")
        self.assertEqual(r[0], "tecnologia/automatizaciones")
        r, _ = carpetas.rutas("", "", "")
        self.assertEqual(r, ["otros"])
        for x in r:
            self.assertIn(x, carpetas.VALIDAS)


class TestSitios(unittest.TestCase):
    def test_candidatos(self):
        cap = ("if you're flying to tokyo, try these 📍 @yakiniku_jambo 📍 @bar_centifolia\n"
               "Cenamos en @casa_lucio_madrid. #foodie #madrid")
        ns = [c["n"] for c in sitios.candidatos(cap)]
        self.assertIn("Yakiniku Jambo", ns)
        self.assertIn("Bar Centifolia", ns)
        self.assertIn("Casa Lucio", ns)

    def test_direccion_sola(self):
        cs = sitios.candidatos("Brunch top en Madrid ✅\n📍C/del Conde Peñalver, 64\n#madrid")
        self.assertTrue(cs and cs[0].get("solo_dir"))

    def test_sin_sitio_no_inventa(self):
        self.assertEqual(sitios.candidatos("Tutorial de Excel: tablas dinámicas en 5 minutos @excel_tips"), [])

    def test_localizar_con_apple_falso(self):
        cs = sitios.candidatos("Probamos el Bar Trampa 📍 @bar_trampa en Madrid")
        out = sitios.localizar(cs)
        ok = [x for x in out if x]
        self.assertTrue(ok)
        self.assertEqual(ok[0]["t"], "bares")
        self.assertTrue(-90 <= ok[0]["lat"] <= 90)

    def test_sin_apple_no_marca(self):
        os.environ["GUARDADOS_GEO_BIN"] = "/usr/bin/false"
        try:
            with self.assertRaises(sitios.SinRespuesta):
                sitios.localizar([{"n": "Casa Pepe", "ci": ""}])
        finally:
            os.environ["GUARDADOS_GEO_BIN"] = str(HERE / "tools" / "fake_geo.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = dbmod.DB(self.dir / "g.db")
        self.prog = progreso.Progreso()

    def tearDown(self):
        self.tmp.cleanup()


class TestMapaYFeed(Base):
    def test_pasada_geo_rellena_lug_y_sitios(self):
        self.db.add({"code": "Abcdef001", "caption": "Las mejores copas 📍 @bar_trampa Madrid", "user": "x"})
        self.db.add({"code": "Abcdef002", "caption": "Receta de brownie fácil", "user": "y"})
        r = completar.pasada_geo(self.db, self.prog)
        self.assertEqual(r["posts"], 2)
        self.assertGreaterEqual(r["sitios"], 1)
        feed = {p["id"]: p for p in self.db.feed("http://127.0.0.1:1/m/")["posts"]}
        p1 = feed["Abcdef001"]
        self.assertIn("sitios", p1["cat"])
        self.assertTrue(p1["sub"][0].startswith("sitios/"))
        self.assertEqual(set(p1["lug"][0]), {"n", "t", "ci", "lat", "lng", "a"})
        self.assertIn("<img", p1["lug"][0]["n"])  # se guarda tal cual; la web lo escapa al pintar
        self.assertEqual(feed["Abcdef002"]["lug"], [])
        self.assertEqual(self.db.pending_geo(), [])
        g = self.prog.snapshot()[0]
        self.assertEqual((g["k"], g["state"], g["done"], g["total"]), ("geo", "ok", 2, 2))

    def test_sin_red_reintenta(self):
        self.db.add({"code": "Abcdef003", "caption": "Cena en @casa_pepe 📍 Madrid", "user": "x"})
        os.environ["GUARDADOS_GEO_BIN"] = "/usr/bin/false"
        try:
            with self.assertRaises(completar.SinMapa):
                completar.pasada_geo(self.db, self.prog)
        finally:
            os.environ["GUARDADOS_GEO_BIN"] = str(HERE / "tools" / "fake_geo.py")
        self.assertEqual(len(self.db.pending_geo()), 1)   # no se dio por mirado

    def test_base_vieja_se_ordena_al_abrir(self):
        import sqlite3
        f = self.dir / "vieja.db"
        c = sqlite3.connect(f)
        c.executescript(dbmod.SCHEMA.replace("tr TEXT DEFAULT '', lang", "tr TEXT DEFAULT '', lang"))
        c.execute("INSERT INTO posts (code, src, caption, username) VALUES ('Viejo00001','instagram',"
                  "'Receta de brownie de chocolate, el mejor postre','x')")
        c.commit()
        c.close()
        d = dbmod.DB(f)
        p = d.feed("")["posts"][0]
        self.assertEqual(p["sub"], ["recetas/postres"])
        self.assertEqual(len(d.pending_geo()), 1)

    def test_valid_lug_tira_basura(self):
        self.assertIsNone(dbmod.valid_lug({"n": "x", "lat": "nan", "lng": 1}))
        self.assertIsNone(dbmod.valid_lug({"n": "x", "lat": 200, "lng": 1}))
        self.assertIsNone(dbmod.valid_lug({"n": "", "lat": 1, "lng": 1}))
        self.assertEqual(dbmod.valid_lug({"n": "Sitio", "t": "<b>", "lat": 1, "lng": 2})["t"], "planes")


class TestIA(Base):
    def setUp(self):
        super().setUp()
        self.gem = selftest.FakeGemini(0, good_key=FAKE_KEY)
        port = self.gem.srv.server_address[1]
        os.environ["GUARDADOS_GEMINI_URL"] = f"http://127.0.0.1:{port}/v1beta/models/{{m}}:generateContent"

    def tearDown(self):
        self.gem.srv.shutdown()
        os.environ.pop("GUARDADOS_GEMINI_URL", None)
        super().tearDown()

    def test_clave_600_y_no_se_lee_de_vuelta(self):
        c = ia.Clave(self.dir)
        with self.assertRaises(ValueError):
            c.set("hola <script>")
        c.set(FAKE_KEY)
        self.assertEqual(stat.S_IMODE((self.dir / "gemini.key").stat().st_mode), 0o600)
        self.assertEqual(c.get(), FAKE_KEY)
        c.delete()
        self.assertFalse(c.has())

    def test_solo_google_o_localhost(self):
        os.environ["GUARDADOS_GEMINI_URL"] = "https://evil.example/{m}"
        self.assertEqual(ia.url_base(), ia.URL_REAL)

    def test_pasada_ia_con_gemini_falso(self):
        log = logging.getLogger("guardados")
        logf = self.dir / "app.log"
        h = logging.FileHandler(logf)
        log.addHandler(h)
        log.setLevel(logging.INFO)
        try:
            self.db.add({"code": "Abcdef010", "caption": "Pasta en el Bar Trampa", "user": "x"})
            self.db.add({"code": "Abcdef011", "caption": "Webs gratis que te salvan la vida", "user": "y"})
            (self.dir / "media").mkdir()
            (self.dir / "media" / "Abcdef010.jpg").write_bytes(b"\xff\xd8" + b"0" * 500)
            c = ia.Clave(self.dir)
            c.set(FAKE_KEY)
            r = completar.pasada_ia(self.db, c, self.prog, self.dir / "media", sleep=lambda s: None)
            self.assertEqual(r["posts"], 2)
            feed = {p["id"]: p for p in self.db.feed("")["posts"]}
            self.assertEqual(feed["Abcdef010"]["sub"], ["sitios/bares", "humor/memes"])
            self.assertEqual(feed["Abcdef010"]["cat"], ["sitios", "humor"])
            self.assertEqual(feed["Abcdef010"]["ciudad"], "Madrid")
            self.assertEqual(len(feed["Abcdef010"]["lug"]), 1)
            self.assertEqual(feed["Abcdef011"]["sub"], ["tecnologia/webs"])
            # la clave viaja en la cabecera, nunca en la URL
            self.assertTrue(self.gem.seen and all(x["key_in_header"] and not x["key_in_url"] for x in self.gem.seen))
            self.assertTrue(any(x["kind"] == "sitios" and x["imgs"] == 1 for x in self.gem.seen))  # portada
            # las reglas ya no pisan lo de la IA
            self.db.add({"code": "Abcdef011", "caption": "Webs gratis que te salvan la vida!!", "user": "y"})
            self.assertEqual({p["id"]: p for p in self.db.feed("")["posts"]}["Abcdef011"]["sub"], ["tecnologia/webs"])
            self.assertEqual(self.db.pending_ia(), [])
            h.flush()
            self.assertNotIn(FAKE_KEY, logf.read_text())
        finally:
            log.removeHandler(h)

    def test_clave_mala(self):
        self.db.add({"code": "Abcdef020", "caption": "algo", "user": "x"})
        c = ia.Clave(self.dir)
        c.set("AIzaMALAmala_" + "y" * 26)
        with self.assertRaises(ia.ClaveMala):
            completar.pasada_ia(self.db, c, self.prog, self.dir, sleep=lambda s: None)
        self.assertEqual(len(self.db.pending_ia()), 1)

    def test_sin_clave_no_llama(self):
        self.db.add({"code": "Abcdef030", "caption": "algo", "user": "x"})
        r = completar.pasada_ia(self.db, ia.Clave(self.dir), self.prog, self.dir)
        self.assertEqual(r, {"skipped": "sin clave"})
        self.assertEqual(self.gem.seen, [])


class TestProgreso(unittest.TestCase):
    def test_eta_con_ritmo_medido(self):
        t = [1000.0]
        p = progreso.Progreso(clock=lambda: t[0])
        p.start("tt", 2000, 0, "favoritos")
        for k in range(1, 11):
            t[0] += 6          # una página de 30 cada 6 s
            p.update("tt", done=30 * k)
        g = p.snapshot()[0]
        self.assertAlmostEqual(g["rate_min"], 300, delta=1)
        self.assertAlmostEqual(g["eta"], (2000 - 300) / 5, delta=2)
        p.start("ig")
        p.update("ig", done=50)
        ig = [x for x in p.snapshot() if x["k"] == "ig"][0]
        self.assertIsNone(ig["total"])
        self.assertIsNone(ig["eta"])      # sin total no se inventa cuánto falta

    def test_parado_baja_el_ritmo(self):
        t = [0.0]
        p = progreso.Progreso(clock=lambda: t[0])
        p.start("tt", 1000)
        t[0] += 10
        p.update("tt", done=100)
        r1 = p.snapshot()[0]["rate_min"]
        t[0] += 50      # 429: lleva 50 s esperando
        r2 = p.snapshot()[0]["rate_min"]
        self.assertLess(r2, r1)


if __name__ == "__main__":
    unittest.main()
