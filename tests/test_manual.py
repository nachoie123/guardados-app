"""Carpetas puestas a mano: se guardan aparte, mandan sobre todo lo automático y los
nombres hostiles no pasan. Sin internet: base de datos y servidor local temporales.

  .venv/bin/python -m unittest tests.test_manual -v
"""
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ["GUARDADOS_SELFTEST"] = "unittest"

import carpetas  # noqa: E402
import db as dbmod  # noqa: E402
from server import Server  # noqa: E402

HOSTILES = ['<img src=x onerror=alert(1)>', 'a" onmouseover="x', "Regalos'); alert(1);//", "constructor", "__proto__",
            "toString", "ideas", "todo", "src:instagram", "col:x", "a/b/c", "x" * 41, "", "   ", "‮evil",
            "nul\x00x", "&amp;", "ok`x`", None, 42, ["recetas"]]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = dbmod.DB(Path(self.tmp.name) / "g.db")
        self.db.add({"code": "Abcdef001", "caption": "Receta de brownie fácil", "user": "dulces"})
        self.db.add({"code": "Abcdef002", "caption": "Las mejores copas 📍 @bar_trampa Madrid", "user": "x"})

    def tearDown(self):
        self.tmp.cleanup()

    def feed(self, code):
        return next(p for p in self.db.feed("")["posts"] if p["id"] == code)


class TestManual(Base):
    def test_manual_manda_y_nada_lo_pisa(self):
        self.assertEqual(self.db.rutas_de("Abcdef001"), (["recetas/postres"], False))
        r = self.db.set_manual("Abcdef001", ["recetas/postres", "Regalos 🎁", "Viajes/Destinos"])
        self.assertEqual(r, ["recetas/postres", "Regalos 🎁", "viajes/destinos"])
        # re-importar (otra descripción), subtítulos nuevos, sitios del mapa, la IA: lo manual sigue
        self.db.add({"code": "Abcdef001", "caption": "Tutorial de Python para principiantes", "user": "dev"})
        self.db.set_transcript("Abcdef001", "programación en python con github", "es")
        self.db.set_lug("Abcdef001", [{"n": "Bar X", "t": "bares", "lat": 40.4, "lng": -3.7}])
        self.db.set_rutas_ia("Abcdef001", ["tecnologia/programacion"], "")
        p = self.feed("Abcdef001")
        self.assertEqual(p["cat"], ["recetas", "Regalos 🎁", "viajes"])
        self.assertEqual(p["sub"], ["recetas/postres", "viajes/destinos"])
        self.assertEqual(p["lug"], [])   # sin Sitios, el mapa no lo pinta
        self.assertEqual(self.db.carpetas_propias(), ["Regalos 🎁"])
        # y al volver a lo automático, lo último que decidieron las reglas/IA
        self.assertEqual(self.db.set_manual("Abcdef001", None), ["tecnologia/programacion"])
        self.assertEqual(self.db.rutas_de("Abcdef001")[1], False)

    def test_quitar_todo_es_otros(self):
        self.assertEqual(self.db.set_manual("Abcdef002", []), ["otros"])
        self.assertEqual(self.feed("Abcdef002")["cat"], ["otros"])

    def test_sobrevive_a_reabrir(self):
        self.db.set_manual("Abcdef001", ["humor/memes"])
        db2 = dbmod.DB(Path(self.tmp.name) / "g.db")
        self.assertEqual(db2.rutas_de("Abcdef001"), (["humor/memes"], True))

    def test_nombres_hostiles_no_pasan(self):
        for h in HOSTILES:
            with self.assertRaises(ValueError, msg=repr(h)):
                self.db.set_manual("Abcdef001", [h])
        self.assertEqual(self.db.rutas_de("Abcdef001"), (["recetas/postres"], False))
        self.assertIsNone(self.db.set_manual("NoExiste1", ["humor/memes"]))
        self.assertIsNone(self.db.set_manual("../../x", ["humor/memes"]))

    def test_basura_en_la_tabla_no_llega_a_la_web(self):
        # aunque alguien escribiera directamente en la base, feed() solo deja pasar nombres limpios
        self.db.c.execute("INSERT INTO manual VALUES (?,?,0)", ("Abcdef001", json.dumps(['<b>x</b>', "humor/memes"])))
        self.db.c.commit()
        self.assertEqual(self.feed("Abcdef001")["sub"], ["humor/memes"])

    def test_nombre_existente_se_reconoce(self):
        self.assertEqual(carpetas.limpia_ruta("Pelis y series/Terror"), "pelis_series/terror")
        self.assertEqual(carpetas.limpia_ruta("  Mis   cosas "), "Mis cosas")


def _libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestServidor(Base):
    def setUp(self):
        super().setUp()
        self.cambios = []
        self.srv = Server(HERE / "web", Path(self.tmp.name) / "media", self.db.feed, _libre(), db=self.db,
                          on_change=lambda: self.cambios.append(1)).start()

    def tearDown(self):
        self.srv.httpd.shutdown()
        self.srv.httpd.server_close()
        super().tearDown()

    def req(self, path, body=None, origin=True, token=None):
        h = {"Content-Type": "application/json"}
        if origin:
            h["Origin"] = self.srv.base
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(f"{self.srv.base}/api/{token or self.srv.token}/{path}", data=data, headers=h,
                                   method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}") if e.headers.get("Content-Type", "").startswith("application/json") else {}

    def test_api(self):
        st, c = self.req("carpetas")
        self.assertEqual(st, 200)
        self.assertIn({"k": "recetas/postres", "n": "Postres"}, next(x for x in c["arbol"] if x["k"] == "recetas")["subs"])
        self.assertEqual(self.req("post/Abcdef001")[1]["rutas"], ["recetas/postres"])
        st, r = self.req("post/Abcdef001", {"rutas": ["recetas/postres", "Cenas con amigos"]})
        self.assertEqual((st, r["rutas"], r["manual"]), (200, ["recetas/postres", "Cenas con amigos"], True))
        self.assertEqual(self.cambios, [1])   # avisa para subir al móvil
        self.assertEqual(self.req("carpetas")[1]["propias"], ["Cenas con amigos"])
        st, r = self.req("post/Abcdef001", {"auto": True})
        self.assertEqual((st, r["manual"]), (200, False))

    def test_api_cerrada(self):
        self.assertEqual(self.req("carpetas", token="adivinado")[0], 404)
        self.assertEqual(self.req("post/Abcdef001", {"rutas": ["humor/memes"]}, origin=False)[0], 403)
        self.assertEqual(self.req("post/Abcdef001", {"rutas": ["humor/memes"]}, token="adivinado")[0], 404)
        self.assertEqual(self.req("post/NoExiste1", {"rutas": ["humor/memes"]})[0], 404)
        for h in HOSTILES:
            st, r = self.req("post/Abcdef001", {"rutas": [h]})
            self.assertIn(st, (400,), repr(h))
        self.assertEqual(self.db.rutas_de("Abcdef001"), (["recetas/postres"], False))
        # otro origen (una web cualquiera) no escribe aunque supiera el token
        r = urllib.request.Request(f"{self.srv.base}/api/{self.srv.token}/post/Abcdef001", data=b'{"rutas":["humor/memes"]}',
                                   headers={"Content-Type": "application/json", "Origin": "https://www.instagram.com"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(r)
        self.assertEqual(e.exception.code, 403)
        self.assertEqual(self.cambios, [])

    @unittest.skipUnless((HERE / "web" / "guardados" / "index.html").exists(), "sin web copiada")
    def test_mis_guardados_lleva_el_script(self):
        with urllib.request.urlopen(self.srv.base + "/guardados/") as r:
            html = r.read().decode()
        self.assertIn(f'<meta name="guardados-mac" content="{self.srv.token}">', html)
        self.assertIn('src="/mac/asignar.js"', html)
        with urllib.request.urlopen(self.srv.base + "/mac/asignar.js") as r:
            self.assertIn("textContent", r.read().decode())


if __name__ == "__main__":
    unittest.main()
