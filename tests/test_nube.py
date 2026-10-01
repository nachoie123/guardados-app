"""Pruebas del buzón del móvil (nube.py) contra un buzón falso en memoria, sin red.

  python3 -m unittest discover -s tests -v

Necesita build/sello (el candado AES-GCM; lo compila build.sh antes de las pruebas).
"""
import gzip
import hashlib
import http.server
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db as dbmod  # noqa: E402
import nube  # noqa: E402


class FakeBuzon:
    """Lo mínimo del Worker de cloud/: crear, subir, bajar, borrar, con hashes de los tokens."""

    def __init__(self):
        self.meta, self.objs, self.log = {}, {}, []
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _tok(self, which):
                a = self.headers.get("Authorization", "")
                m = fake.meta.get(self.path.split("/")[2])
                return m and a.startswith("Bearer ") and hashlib.sha256(a[7:].encode()).hexdigest() == m[which]

            def _send(self, code, body=b""):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                p = self.path.split("/")
                fake.log.append(("PUT", "/".join(p[3:]) or "buzon"))
                if len(p) == 3:
                    if p[2] in fake.meta:
                        return self._send(409)
                    fake.meta[p[2]] = json.loads(body)
                    return self._send(201)
                if p[2] not in fake.meta:
                    return self._send(404)
                if not self._tok("w"):
                    return self._send(401)
                fake.objs[(p[2], p[3])] = body
                self._send(201)

            def do_DELETE(self):
                p = self.path.split("/")
                fake.log.append(("DELETE", "/".join(p[3:]) or "buzon"))
                if p[2] not in fake.meta:
                    return self._send(404)
                if not self._tok("w"):
                    return self._send(401)
                if len(p) == 3:
                    del fake.meta[p[2]]
                    for k in [k for k in fake.objs if k[0] == p[2]]:
                        del fake.objs[k]
                else:
                    fake.objs.pop((p[2], p[3]), None)
                self._send(200)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"


def abrir(raw, blob):
    p = subprocess.run([nube.sello_bin(), "abrir"], input=raw + blob, capture_output=True)
    assert p.returncode == 0
    return p.stdout


@unittest.skipUnless(nube.sello_bin(), "falta build/sello (./build.sh lo compila)")
class TestNube(unittest.TestCase):
    def setUp(self):
        self.fake = FakeBuzon()
        os.environ["GUARDADOS_BUZON_URL"] = self.fake.url
        os.environ["GUARDADOS_WEB_URL"] = "http://127.0.0.1:8781/"
        self.d = Path(tempfile.mkdtemp())
        self.db = dbmod.DB(self.d / "guardados.db")
        (self.d / "media").mkdir()
        self.n = nube.Nube(self.d, self.db, self.d / "media")

    def tearDown(self):
        self.fake.srv.shutdown()

    def add(self, i, cover=True):
        code = f"Nube{i:04d}"
        self.db.add({"code": code, "caption": f"Receta {i}", "user": f"u{i}", "taken_at": 1750000000 - i, "type": 2})
        if cover:
            subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", "/System/Library/CoreServices/CoreTypes.bundle/"
                            "Contents/Resources/GenericDocumentIcon.icns", "--out", str(self.d / "media" / f"{code}.jpg")],
                           capture_output=True)
            self.db.set_cover(code, True)
        return code

    def test_sin_movil_no_sube_nada(self):
        self.add(1)
        self.assertEqual(self.n.subir(), {"skip": "sin móvil"})
        self.assertEqual(self.fake.log, [])
        self.assertFalse(self.n.f.exists())

    def test_llave_enlace_y_permisos(self):
        c = self.n.asegurar()
        self.assertEqual(oct(self.n.f.stat().st_mode & 0o777), "0o600")
        link = self.n.enlace()
        self.assertTrue(link.startswith("http://127.0.0.1:8781/#conectar=1."))
        frag = link.split("#", 1)[1]
        self.assertIn(c["k"], frag)           # la llave solo en el fragmento
        self.assertNotIn(c["w"], link)        # el token de escritura no sale nunca del Mac
        self.assertNotIn(c["k"], link.split("#", 1)[0])
        st = json.dumps(self.n.estado())
        for s in c.values():
            if isinstance(s, str):
                self.assertNotIn(s, st)

    def test_sube_cifrado_y_solo_lo_que_cambia(self):
        for i in range(5):
            self.add(i)
        c = self.n.asegurar()
        raw = nube._unb64(c["k"])
        r = self.n.subir()
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["covers"], 5)
        self.assertEqual(self.fake.meta[c["id"]]["w"], hashlib.sha256(c["w"].encode()).hexdigest())
        ix = json.loads(abrir(raw, self.fake.objs[(c["id"], "index.bin")]))
        posts = json.loads(gzip.decompress(abrir(raw, self.fake.objs[(c["id"], ix["posts"])])))["posts"]
        self.assertEqual(len(posts), 5)
        pack = abrir(raw, self.fake.objs[(c["id"], ix["covers"][0]["f"])])
        n = struct.unpack(">I", pack[:4])[0]
        head = json.loads(pack[4:4 + n])
        first = pack[4 + n:4 + n + head[0][1]]
        self.assertEqual(first[:3], b"\xff\xd8\xff")   # dentro, un JPEG
        for blob in self.fake.objs.values():           # fuera, nada legible
            self.assertNotIn(b"Receta", blob)
            self.assertNotIn(b"\xff\xd8\xff\xe0", blob)
        # sin cambios: ni una petición
        self.fake.log.clear()
        self.assertEqual(self.n.subir(), {"skip": "sin cambios"})
        self.assertEqual(self.fake.log, [])
        # uno nuevo: datos nuevos + 1 portada, y el paquete de datos viejo se borra
        self.add(9)
        old = ix["posts"]
        r = self.n.subir()
        self.assertEqual(r["covers"], 1)
        self.assertIn(("DELETE", old), self.fake.log)
        self.assertNotIn((c["id"], old), self.fake.objs)
        ix2 = json.loads(abrir(raw, self.fake.objs[(c["id"], "index.bin")]))
        self.assertEqual(len(ix2["covers"]), 2)

    def test_cambiar_llave_borra_el_buzon_viejo(self):
        self.add(1)
        c1 = self.n.asegurar()
        self.n.subir()
        self.n.cambiar()
        c2 = self.n.cred()
        self.assertNotIn(c1["id"], self.fake.meta)
        self.assertNotEqual(c1["k"], c2["k"])
        self.assertNotEqual(c1["id"], c2["id"])
        self.assertTrue(self.n.subir().get("ok"))
        self.assertIn(c2["id"], self.fake.meta)

    def test_url_solo_cambia_a_loopback(self):
        os.environ["GUARDADOS_BUZON_URL"] = "https://evil.example"
        self.assertEqual(nube.Nube(self.d, self.db, self.d / "media").base, nube.BUZON_URL)


if __name__ == "__main__":
    unittest.main()
