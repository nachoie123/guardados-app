"""Guardados (app de Mac): tus guardados de Instagram y favoritos de TikTok, solos.

Cuatro ventanas:
- Panel (la única con js_api): estado, botones y progreso.
- Instagram y TikTok: las webs oficiales. La persona inicia sesión ahí; la app
  nunca ve ni guarda contraseñas. Las llamadas se hacen con fetch() DENTRO de
  esas ventanas, con su sesión (patrón de ~/Projects/ig-limpieza).
- Mis guardados: la web de guardados de siempre, servida desde el Mac, + poner un
  vídeo en una carpeta a mano (web/mac/asignar.js, por /api/ de server.py).

Datos de cada persona: ~/Library/Application Support/Guardados (base SQLite y
portadas). Las cookies de Instagram/TikTok las guarda WebKit en
~/Library/WebKit/<bundle id> y ~/Library/HTTPStorages/<bundle id>: en macOS
pywebview usa el almacén por defecto y no admite otra carpeta.
"""
import json
import logging
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import webview

import completar
import db as dbmod
import ia
import importer
import media
import nube
import progreso
import transcribir
from server import Server

BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
DATA = Path(os.environ.get("GUARDADOS_DATA") or Path.home() / "Library" / "Application Support" / "Guardados")
WEB = BUNDLE / "web"
PORT = int(os.environ.get("GUARDADOS_PORT", "47613"))
IG_URL = os.environ.get("GUARDADOS_IG_URL", "https://www.instagram.com/")
TT_URL = os.environ.get("GUARDADOS_TT_URL", "https://www.tiktok.com/")
AUTO_EVERY = 12 * 3600   # importación automática si la última buena tiene más de 12 h

DATA.mkdir(parents=True, exist_ok=True)
os.chmod(DATA, 0o700)
logging.basicConfig(filename=str(DATA / "app.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("guardados")
try:
    os.chmod(DATA / "app.log", 0o600)
except OSError:
    pass


# ---------------------------------------------------------------- puente vigilado
# pywebview deja que CUALQUIER ventana mande mensajes al puente. Solo el panel
# puede llamar a funciones de la app; Instagram/TikTok solo pueden devolver el
# resultado de nuestros propios evaluate_js (pywebviewAsyncCallback). Nada con
# "__" (evita trepar por atributos de Python desde JS).
BLOCKED = []
_PANEL = {"w": None}
_INTERNAL = {"pywebviewAsyncCallback"}


def _guard_bridge():
    import webview.platforms.cocoa as cocoa
    orig = cocoa.js_bridge_call

    def guarded(window, func_name, param, value_id):
        name = func_name if isinstance(func_name, str) else repr(func_name)
        if "__" in name or (window is not _PANEL["w"] and name not in _INTERNAL):
            BLOCKED.append({"window": getattr(window, "title", "?"), "func": name[:80], "at": time.time()})
            log.warning("puente: bloqueada %s desde %s", name[:80], getattr(window, "title", "?"))
            return
        return orig(window, func_name, param, value_id)

    cocoa.js_bridge_call = guarded


# ---------------------------------------------------------------- ventana web
class WebWin:
    """fetch() dentro de la ventana (Instagram/TikTok) con su sesión."""

    def __init__(self, win):
        self.win = win

    def run(self, body, timeout=90):
        done, box = threading.Event(), {}

        def cb(res):
            box["r"] = res
            done.set()

        script = "(async()=>{try{%s\n}catch(e){return JSON.stringify({neterr:String(e&&e.message||e)})}})()" % body
        self.win.evaluate_js(script, cb)
        if not done.wait(timeout):
            raise TimeoutError("la ventana no responde")
        r = box.get("r")
        for _ in range(3):
            if not isinstance(r, str):
                break
            r = json.loads(r)
        return r


# ---------------------------------------------------------------- lo que llama el panel
class Api:
    def __init__(self, db, srv):
        self.db, self.srv = db, srv
        self.wins = {}
        self.pages = {}
        self.task = {"running": False, "which": "", "note": "", "error": None, "result": None}
        self.version = 0          # sube cada vez que entra algo: el panel re-importa en la web
        self.prog = progreso.Progreso()
        self.covers = media.Covers(db, DATA / "media", self.prog)
        self.nube = nube.Nube(DATA, db, DATA / "media")   # buzón cifrado para el móvil (docs/diseno.md, decisión 9)
        self.clave = ia.Clave(DATA)   # la clave de Gemini de la persona (opcional): solo un fichero 600 en su Mac
        self.ia_error = None
        self.imp = None
        self.whisper = transcribir.available()
        self._activity = None
        self._last_auto = {}

    # -- estado --
    def status(self):
        c = self.db.counts()
        return {
            "task": self.task, "version": self.version + sum(v["covers"] for v in c.values()),
            "counts": c, "feed": f"/feed/{self.srv.token}/items.json",
            "ig": {"last_ok": self.db.get("ig.last_ok"), "pending": bool(self.db.get("ig.run")),
                   "session": self._session("ig")},
            "tt": {"last_ok": self.db.get("tt.last_ok"), "pending": bool(self.db.get("tt.run")),
                   "session": self._session("tt")},
            "whisper": self.whisper,
            "recent": self.db.recent(8),
            "progress": self.prog.snapshot(),
            # nunca la clave: solo si la hay
            "ia": {"has_key": self.clave.has(), "error": self.ia_error, **self.db.ia_counts()},
            # el móvil: si está conectado y cuándo se subió; nunca la llave, los tokens ni el QR
            "movil": self.nube.estado(),
        }

    # -- el móvil: el QR solo sale por aquí (solo el panel puede llamar, ver _guard_bridge) --
    def movil_qr(self):
        try:
            qr = self.nube.qr()
        except Exception as e:
            log.warning("móvil: no he podido hacer el QR (%s)", type(e).__name__)
            return {"ok": False, "error": "No he podido preparar el código."}
        self._movil_pronto()
        return {"ok": True, "qr": qr}

    def movil_cambiar(self):
        self.nube.cambiar()
        return self.movil_qr()

    def _movil_pronto(self, wait_covers=False):
        def go():
            if wait_covers:
                self.covers.wait()
            self.nube.subir()
        if self.nube.activo():
            threading.Thread(target=go, daemon=True).start()

    # -- IA opcional: la clave entra por aquí y no vuelve a salir --
    def set_gemini_key(self, key):
        try:
            self.clave.set(key if isinstance(key, str) else "")
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except OSError:
            return {"ok": False, "error": "No he podido guardarla en este Mac."}
        self.ia_error = None
        log.info("clave de Gemini guardada (no se apunta cuál)")
        self._kick("ia")
        return {"ok": True}

    def delete_gemini_key(self):
        self.clave.delete()
        self.ia_error = None
        log.info("clave de Gemini borrada")
        return {"ok": True}

    def _session(self, which):
        s = getattr(self, "_sess", {}).get(which)
        return s

    # -- acciones --
    def import_now(self, which="all"):
        return self._kick(which)

    def _kick(self, which):
        if which not in ("ig", "tt", "all", "ia") or self.task["running"]:
            return False
        threading.Thread(target=self._run, args=(which,), daemon=True).start()
        return True

    def stop(self):
        if self.imp:
            self.imp.stop = True
        return True

    def show(self, which):
        w = self.wins.get(which)
        if not w:
            return False
        w.show()
        w.restore()
        return True

    def reload_viewer(self):
        w = self.wins.get("viewer")
        if w:
            w.load_url(self.srv.base + "/guardados/")
        return True

    def export_json(self):
        """Copia en ~/Downloads con el formato de export.py (con carpetas, subcarpetas y mapa): se
        puede importar en la web del móvil (nachosanbenito.com/guardados → Importar). Sin portadas."""
        d = self.db.feed("")
        out = Path.home() / "Downloads" / f"guardados-{datetime.now():%Y-%m-%d}.json"
        out.write_text(json.dumps(d, ensure_ascii=False))
        return str(out.name)

    # -- trabajo --
    def _note(self, s):
        self.task["note"] = s
        log.info(s)

    def _awake(self, on):
        """Que macOS no duerma la app (App Nap) mientras importa."""
        try:
            from Foundation import NSProcessInfo
            pi = NSProcessInfo.processInfo()
            if on and self._activity is None:
                self._activity = pi.beginActivityWithOptions_reason_(0x00FFFFFF, "Importando guardados")
            elif not on and self._activity is not None:
                pi.endActivity_(self._activity)
                self._activity = None
        except Exception:
            pass

    def _run(self, which):
        self.task.update(running=True, which=which, error=None, result=None)
        self._awake(True)
        if time.time() - getattr(self, "_last_end", 0) > 600:
            self.prog.clear()   # una importación nueva; si la anterior acabó hace nada, sus filas se quedan
        res = {}
        self.imp = importer.Importer(self.db, self.pages, note=self._note, on_covers=self._covers, prog=self.prog)
        try:
            for w in (["ig", "tt"] if which == "all" else [] if which == "ia" else [which]):
                try:
                    res[w] = self.imp.instagram() if w == "ig" else self.imp.tiktok()
                    self.version += 1
                except (importer.NoSession, importer.Blocked, InterruptedError) as e:
                    res[w] = {"error": str(e)}
                    log.warning("%s: %s", w, e)
                    if isinstance(e, InterruptedError):
                        break
            self.covers.retry_pending()
            if self.whisper and not self.imp.stop:
                res["whisper"] = transcribir.Transcriber(self.db, self._note).run(lambda: self.imp.stop, self.prog)
                self.version += 1
            # el mapa sin IA: sitios de la descripción, buscados en Apple Maps
            if not self.imp.stop:
                self._note("Buscando sitios para el mapa en Apple Maps…")
                try:
                    res["geo"] = completar.pasada_geo(self.db, self.prog, lambda: self.imp.stop)
                except completar.SinMapa as e:
                    res["geo"] = {"error": str(e)}
                self.version += 1
            # IA opcional: solo si la persona puso su clave
            if not self.imp.stop and self.clave.has():
                self._note("Afinando carpetas y mapa con tu clave de Gemini…")
                try:
                    res["ia"] = completar.pasada_ia(self.db, self.clave, self.prog, DATA / "media", lambda: self.imp.stop)
                    self.ia_error = None
                except ia.ClaveMala as e:
                    self.ia_error = str(e)
                    res["ia"] = {"error": str(e)}
                except Exception as e:
                    self.ia_error = f"Gemini no ha respondido ({type(e).__name__}). Se reintentará."
                    res["ia"] = {"error": self.ia_error}
                self.version += 1
            errs = [f"{k}: {v['error']}" for k, v in res.items() if isinstance(v, dict) and v.get("error")]
            self.task["error"] = " · ".join(errs) or None
            self.task["result"] = res
            self._note("Listo" if not errs else "Terminado con avisos")
        except Exception as e:
            log.exception("import")
            self.task["error"] = str(e)
        finally:
            self._awake(False)
            self._last_end = time.time()
            self.task["running"] = False
            self._movil_pronto(wait_covers=True)   # al móvil, solo si ha cambiado algo

    def _covers(self, items):
        self.covers.add(items)
        self.version += 1

    # -- vigilante: detecta el login y arranca solo --
    def watch(self):
        self._sess = {}
        while True:
            for which, js in (("ig", importer.IG_WHO_JS), ("tt", importer.TT_WHO_JS % {"deep": "false", "hostre": json.dumps(importer.TT_HOST_RE)})):
                try:
                    r = self.pages[which].run(js, timeout=8) or {}
                    self._sess[which] = bool(r.get("uid") and r.get("host") == importer.IG_HOST) if which == "ig" else bool(r.get("sec"))
                except Exception:
                    self._sess[which] = None
            if os.environ.get("GUARDADOS_NO_AUTO") is None and not self.task["running"]:
                for which in ("ig", "tt"):
                    last = self.db.get(f"{which}.last_ok") or 0
                    pending = self.db.get(f"{which}.run")
                    tried = self._last_auto.get(which, 0)
                    if self._sess.get(which) and (pending or time.time() - last > AUTO_EVERY) \
                            and time.time() - tried > 1800:
                        self._last_auto[which] = time.time()
                        self._kick(which)
                        break
            # el móvil, por si una subida falló sin red: cada 10 min (sin cambios no sale ni una petición)
            if time.time() - getattr(self, "_last_movil", 0) > 600 and not self.task["running"]:
                self._last_movil = time.time()
                self._movil_pronto()
            time.sleep(10)


def main():
    db = dbmod.DB(DATA / "guardados.db")
    srv = Server(WEB, DATA / "media", db.feed, PORT, db=db).start()
    api = Api(db, srv)
    srv.on_change = api._movil_pronto   # una carpeta puesta a mano: al móvil, por la subida normal
    _guard_bridge()
    if os.environ.get("GUARDADOS_SELFTEST"):
        import selftest  # Instagram/TikTok falsos y hostiles en 127.0.0.1 (ver selftest.py)
        selftest.serve_fakes(PORT)
    panel = webview.create_window("Guardados", f"{srv.base}/panel/", js_api=api, width=760, height=760,
                                  min_size=(560, 560), text_select=True)
    _PANEL["w"] = panel
    ig = webview.create_window("Instagram", IG_URL, width=460, height=780, x=40, y=60)
    tt = webview.create_window("TikTok", TT_URL, width=460, height=780, x=520, y=60)
    viewer = webview.create_window("Mis guardados", f"{srv.base}/guardados/", width=1100, height=820,
                                   hidden=True)
    api.wins = {"ig": ig, "tt": tt, "viewer": viewer, "panel": panel}
    api.pages = {"ig": WebWin(ig), "tt": WebWin(tt)}

    def started():
        threading.Thread(target=api.watch, daemon=True).start()
        if os.environ.get("GUARDADOS_PROBE"):
            import probe  # solo mira la forma de la respuesta real; no importa nada
            threading.Thread(target=probe.run, args=(os.environ["GUARDADOS_PROBE"], api), daemon=True).start()
        test = os.environ.get("GUARDADOS_SELFTEST")
        if test:
            import selftest
            selftest.run(test, api, srv, db, BLOCKED)

    # private_mode=False: la sesión de Instagram/TikTok se recuerda entre aperturas
    webview.start(started, private_mode=False, storage_path=str(DATA / "webview"))


if __name__ == "__main__":
    main()
