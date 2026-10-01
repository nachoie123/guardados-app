"""Prueba de punta a punta SIN internet ni cuentas reales (GUARDADOS_SELFTEST=<fichero>).

Monta un "Instagram" y un "TikTok" falsos en 127.0.0.1 que:
  1. contestan a las mismas rutas de API con guardados de prueba (algunos con
     captions y nombres trampa: <img onerror>, <script>), y
  2. son páginas HOSTILES: intentan llamar a la app por todas las puertas
     (pywebview.api, _jsApiCallback, messageHandlers, dunders, el servidor local).
Luego deja que la app haga lo suyo (detecta la "sesión" e importa sola), mira el
panel y "Mis guardados", y escribe el resultado en JSON. No toca Instagram ni TikTok.

Arranque (lo hace tools/selftest.sh):
  GUARDADOS_SELFTEST=out.json GUARDADOS_DATA=/tmp/x GUARDADOS_IG_URL=http://127.0.0.1:47700/ \
  GUARDADOS_TT_URL=http://127.0.0.1:47701/ python3 app.py
"""
import http.server
import json
import threading
import time
import urllib.request
from pathlib import Path

import importer

EVIL_CAPTION = '<img src=x onerror="window.__pwned=(window.__pwned||0)+1"> Receta de pasta rápida para cenar <b>hoy</b>'
EVIL_NAME = '<script>window.__pwned=1</script>Nombre'

ATTACK_JS = r"""
<script>
document.cookie = 'ds_user_id=4242; path=/';
window.__attack = {done: false, tries: {}};
const T = window.__attack.tries;
async function attack() {
  // espera a que pywebview inyecte su objeto en esta ventana
  for (let i = 0; i < 50 && !(window.pywebview && window.pywebview._jsApiCallback); i++) await new Promise(r => setTimeout(r, 100));
  T.has_pywebview = !!window.pywebview;
  T.api_keys = window.pywebview && window.pywebview.api ? Object.keys(window.pywebview.api) : null;
  for (const f of ['import_now', 'export_json', 'status', 'show', 'stop']) {
    try { const r = await Promise.race([window.pywebview.api[f]('all'), new Promise(r => setTimeout(() => r('sin respuesta'), 3000))]); T['api.' + f] = 'devolvio: ' + JSON.stringify(r); }
    catch (e) { T['api.' + f] = 'error: ' + String(e).slice(0, 80); }
  }
  for (const f of ['export_json', 'import_now', '__class__.__base__.__subclasses__', 'pywebviewMoveWindow', 'pywebviewStateUpdate']) {
    try { window.pywebview._jsApiCallback(f, f === 'pywebviewMoveWindow' ? [0, 0] : (f === 'pywebviewStateUpdate' ? {key: 'x', value: 1} : ['all']), 'id' + Math.random()); T['bridge.' + f] = 'enviado'; }
    catch (e) { T['bridge.' + f] = 'error: ' + String(e).slice(0, 80); }
  }
  try { window.webkit.messageHandlers.jsBridge.postMessage(JSON.stringify({funcName: 'export_json', params: [], id: 'x1'})); T.raw_handler = 'enviado'; } catch (e) { T.raw_handler = 'error: ' + String(e).slice(0, 60); }
  for (const u of ['http://127.0.0.1:%(port)s/feed/adivinado/items.json', 'http://127.0.0.1:%(port)s/panel/']) {
    try { const r = await fetch(u); T['fetch ' + u] = 'LEIDO ' + r.status + ' ' + (await r.text()).slice(0, 40); }
    catch (e) { T['fetch ' + u] = 'bloqueado: ' + String(e).slice(0, 60); }
  }
  window.__attack.done = true;
}
attack();
</script>
"""


def _ig_api(start):
    items = []
    for i in range(start, min(start + 50, 60)):
        items.append({"media": {
            "code": f"Selftest{i:03d}", "pk": str(9000 + i), "id": f"{9000 + i}_1",
            "user": {"username": f"cuenta_{i}", "full_name": EVIL_NAME if i == 0 else f"Cuenta {i}"},
            "caption": {"text": EVIL_CAPTION + "\n📍 @bar_trampa" if i == 0 else
                        "Las mejores copas de Madrid 📍 @casa_selftest" if i == 1 else
                        f"Receta número {i}: pasta con tomate en 10 minutos para cenar"},
            "taken_at": 1750000000 - i, "media_type": 2, "product_type": "clips", "like_count": i, "play_count": i * 10,
            "saved_collection_ids": ["17900000000000000"],
            "image_versions2": {"candidates": [{"width": 640, "url": f"https://scontent.cdninstagram.com/fake{i}.jpg"}]}}})
    more = start + 50 < 60
    return {"items": items, "more_available": more, "next_max_id": str(start + 50) if more else None, "status": "ok"}


def _tt_api(cursor):
    items = [{"id": str(7300000000000000000 + i),
              "desc": EVIL_CAPTION if i == 39 else f"Truco de Excel {i} para tus finanzas personales",
              "author": {"uniqueId": f"tt.cuenta{i}", "nickname": EVIL_NAME if i == 39 else f"TT {i}"},
              "createTime": 1750000000 - i, "stats": {"playCount": i},
              "video": {"cover": f"https://p16-sign.tiktokcdn.com/fake{i}.jpeg", "subtitleInfos": []}}
             for i in range(cursor, min(cursor + 30, 40))]
    more = cursor + 30 < 40
    return {"statusCode": 0, "itemList": items, "hasMore": more, "cursor": str(cursor + 30), "total": 40}


def _fake(port, kind, app_port):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            from urllib.parse import parse_qs, urlparse
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path.startswith("/api/"):
                time.sleep(1.5)  # como la red de verdad: así se ve la barra de progreso
            if kind == "ig" and u.path == "/api/v1/feed/saved/posts/":
                ok = self.headers.get("X-IG-App-ID") == importer.IG_APP_ID
                body, ctype = (json.dumps(_ig_api(int((q.get("max_id") or ["0"])[0]))), "application/json") if ok \
                    else ("<!doctype html><html>login</html>", "text/html")
            elif kind == "tt" and u.path == "/api/user/collect/item_list/":
                body, ctype = json.dumps(_tt_api(int((q.get("cursor") or ["0"])[0]))), "application/json"
            elif u.path == "/":
                rehy = ('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
                        '{"__DEFAULT_SCOPE__":{"webapp.app-context":{"user":{"secUid":"MS4wLjABAAAA_selftest"}}}}</script>'
                        if kind == "tt" else "")
                body = f"<!doctype html><html><body><h1>{kind} falso y hostil</h1>{rehy}{ATTACK_JS % {'port': app_port}}</body></html>"
                ctype = "text/html; charset=utf-8"
            else:
                self.send_response(404)
                self.end_headers()
                return
            b = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

    s = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class FakeGemini:
    """Gemini FALSO en 127.0.0.1 (nunca el de verdad). Apunta cómo le llega la clave:
    debe venir en la cabecera x-goog-api-key y NUNCA en la URL."""

    def __init__(self, port, good_key=None):
        self.seen, self.good = [], good_key
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                key = self.headers.get("x-goog-api-key") or ""
                text = " ".join(p.get("text", "") for p in body["contents"][0]["parts"] if "text" in p)
                imgs = sum(1 for p in body["contents"][0]["parts"] if "inline_data" in p)
                fake.seen.append({"path": self.path, "key_in_header": bool(key), "key": key,
                                  "key_in_url": bool(key) and key in self.path, "kind": "carpetas" if "Ordena videos" in text else "sitios",
                                  "imgs": imgs})
                if fake.good and key != fake.good:
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b'{"error":{"code":403,"message":"API key not valid"}}')
                    return
                if "Ordena videos" in text:
                    out = {}
                    for block in text.split("=== id: ")[1:]:
                        code = block.split("\n", 1)[0].strip()
                        out[code] = ({"c": ["sitios/bares", "humor"], "ciudad": "Madrid"} if "Trampa" in block or "pasta" in block.lower()
                                     else {"c": ["tecnologia/webs"], "ciudad": ""})
                else:
                    out = {"lugares": [{"nombre": "Bar Trampa", "direccion": "", "ciudad": "Madrid", "pais": "España",
                                        "tipo": "bares", "lat": 40.42, "lng": -3.70}]}
                b = json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(out)}]}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{port}/v1beta/models/{{m}}:generateContent"


GEMINI = {}


def serve_fakes(app_port):
    import media   # portadas: en vez del CDN de Instagram/TikTok, un JPEG de color hecho aquí (sin red)
    media.fetch = lambda url, src, dest, opener=None: media.allowed(url, src) and fake_jpeg(dest, sum(map(ord, url)))
    importer.IG_HOST = "127.0.0.1"
    importer.TT_HOST_RE = r"^127\.0\.0\.1$"
    _fake(47700, "ig", app_port)
    _fake(47701, "tt", app_port)
    GEMINI["srv"] = FakeGemini(47702)


def _snapshot(win, path):
    """Foto de lo que se ve en la ventana (WKWebView.takeSnapshot): no necesita permiso de grabar pantalla."""
    from AppKit import NSBitmapImageRep, NSBitmapImageFileTypePNG
    from PyObjCTools import AppHelper
    from webview.platforms.cocoa import BrowserView
    done = threading.Event()

    def go():
        try:
            wv = BrowserView.instances[win.uid].webview

            def handler(img, err):
                try:
                    if img is not None:
                        rep = NSBitmapImageRep.imageRepWithData_(img.TIFFRepresentation())
                        rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {}).writeToFile_atomically_(str(path), True)
                finally:
                    done.set()
            wv.takeSnapshotWithConfiguration_completionHandler_(None, handler)
        except Exception:
            done.set()
    AppHelper.callAfter(go)
    done.wait(10)
    return Path(path).exists()


def _js(win, code, timeout=20):
    done, box = threading.Event(), {}
    win.evaluate_js("(async()=>{%s})()" % code, lambda r: (box.update(r=r), done.set()))
    done.wait(timeout)
    r = box.get("r")
    return json.loads(r) if isinstance(r, str) else r


def _movil(api, panel, ig, tt, srv, out):
    """El móvil: la persona pulsa «Conectar el móvil» en el panel; el Mac crea la llave, sube el
    buzón cifrado (cloud/ con wrangler dev en local) y enseña el QR. Las páginas de IG/TT intentan
    sacar el QR, la llave o cambiarla."""
    import os
    r = {}
    # como la persona: pulsa el botón del panel y el QR aparece en pantalla
    q = _js(panel, "document.getElementById('movil-qr').click();"
                   "for (let i = 0; i < 60 && document.getElementById('qr-box').hidden; i++) await new Promise(r => setTimeout(r, 250));"
                   "const img = document.getElementById('qr');"
                   "await new Promise(r => img.complete ? r() : (img.onload = r));"
                   "return JSON.stringify({shown: !document.getElementById('qr-box').hidden, qr: img.src, w: img.naturalWidth})", 30) or {}
    r["panel_qr_shown"] = bool(q.get("shown"))
    r["qr_is_svg"] = str(q.get("qr", "")).startswith("data:image/svg+xml")
    r["qr_px"] = q.get("w")
    c = api.nube.cred() or {}
    t0 = time.time()
    while time.time() - t0 < 90:   # sube en segundo plano: datos y luego portadas
        e = api.nube.estado()
        if e.get("subido") and not e.get("subiendo") and e.get("covers", 0) >= 100:
            break
        if e.get("error") and time.time() - t0 > 10:
            break
        time.sleep(0.5)
    r["estado"] = api.nube.estado()
    r["secs"] = round(time.time() - t0, 1)
    r["again"] = api.nube.subir()   # sin cambios: ni una petición
    r["cred_mode"] = oct(os.stat(api.nube.f).st_mode & 0o777) if api.nube.f.exists() else None
    status_txt = json.dumps(api.status(), ensure_ascii=False, default=str)
    logf = api.nube.f.parent / "app.log"
    logtxt = logf.read_text() if logf.exists() else ""
    secretos = [c.get(k) for k in ("k", "w", "r", "id") if c.get(k)]
    r["secret_in_status"] = any(x in status_txt for x in secretos)
    r["secret_in_log"] = any(x in logtxt for x in secretos)
    r["secret_in_panel_html"] = _js(panel, "return JSON.stringify(%s.some(x => document.documentElement.outerHTML.includes(x)))"
                                    % json.dumps(secretos))
    # las páginas hostiles de Instagram y TikTok: ¿pueden pedir el QR o cambiar la llave?
    steal = r"""
      const out = {};
      for (const f of ['movil_qr', 'movil_cambiar', 'status']) {
        try { const r = await Promise.race([window.pywebview.api[f](), new Promise(r => setTimeout(() => r('sin respuesta'), 2000))]); out[f] = 'devolvio: ' + JSON.stringify(r).slice(0, 80); }
        catch (e) { out[f] = 'error: ' + String(e).slice(0, 60); }
        try { window.pywebview._jsApiCallback(f, [], 'id' + Math.random()); out['bridge.' + f] = 'enviado'; } catch (e) { out['bridge.' + f] = 'error'; }
      }
      for (const u of ['/movil.json', '/feed/x/movil.json', '/panel/../movil.json']) {
        try { const r = await fetch('http://127.0.0.1:%(port)s' + u); out['fetch ' + u] = 'LEIDO ' + r.status; } catch (e) { out['fetch ' + u] = 'bloqueado'; }
      }
      await new Promise(r => setTimeout(r, 1500));
      return JSON.stringify(out);""" % {"port": srv.port}
    r["steal_ig"] = _js(ig, steal)
    r["steal_tt"] = _js(tt, steal)
    r["cred_same_after_attack"] = (api.nube.cred() or {}).get("k") == c.get("k") and bool(c.get("k"))
    try:
        urllib.request.urlopen(srv.base + "/movil.json")
        r["server_cred"] = "SERVIDO (mal)"
    except Exception as e:
        r["server_cred"] = str(e)
    # para la prueba de punta a punta en la web (tools/prueba_movil.py): solo en modo prueba
    import os as _os
    dest = _os.environ.get("GUARDADOS_SELFTEST_ENLACE")
    if dest:
        fd = _os.open(dest, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
        with _os.fdopen(fd, "w") as fh:
            json.dump({"enlace": api.nube.enlace(), "qr": q.get("qr"), "n": 100}, fh)
    return r


def run(out, api, srv, db, blocked):
    res = {"started": time.time()}
    calls = []
    for name in ("export_json", "import_now", "stop", "show"):  # cualquier llamada desde IG/TT quedaría aquí
        orig = getattr(api, name)

        def wrap(*a, _o=orig, _n=name):
            calls.append({"func": _n, "args": repr(a)[:80], "t": time.time()})
            if _n == "export_json":
                return "selftest-no-escribe"
            return _o(*a)
        setattr(api, name, wrap)
    try:
        ig, tt, panel, viewer = api.wins["ig"], api.wins["tt"], api.wins["panel"], api.wins["viewer"]
        t0 = time.time()
        stages, panel_rows, shot = {}, [], None
        png = Path(out).parent / "panel-progreso.png"
        while time.time() - t0 < 120:  # la app detecta la "sesión" sola y arranca
            for g in api.prog.snapshot():   # la barra: lo que ve el panel en cada momento
                stages.setdefault(g["k"], []).append({k: g[k] for k in ("state", "done", "total", "eta", "rate_min")})
            g_tt = next((g for g in api.prog.snapshot() if g["k"] == "tt"), None)
            if shot is None and g_tt and g_tt["state"] == "run" and g_tt["done"] > 0:
                time.sleep(1.6)  # que el panel (cada 1,5 s) ya lo pinte
                panel_rows = _js(panel, "return JSON.stringify([...document.querySelectorAll('#stages .stage')].map(r => ({"
                                        "name: r.querySelector('b').textContent, num: r.querySelector('.st-num').textContent,"
                                        "sub: r.querySelector('.st-sub').textContent, bar: r.querySelector('.bar').className,"
                                        "width: r.querySelector('.bar>span').style.width})))")
                shot = _snapshot(panel, png)
            c = db.counts()
            if not api.task["running"] and c.get("instagram", {}).get("n") == 60 and c.get("tiktok", {}).get("n") == 40 \
                    and db.get("ig.last_ok") and db.get("tt.last_ok"):
                break
            time.sleep(0.5)
        res["auto_import"] = {"counts": db.counts(), "task": api.task, "secs": round(time.time() - t0, 1),
                              "ig_last_ok": db.get("ig.last_ok"), "tt_last_ok": db.get("tt.last_ok")}
        res["progress"] = {"stages_seen": {k: {"n": len(v), "first": v[0], "last": v[-1],
                                               "max_total": max((x["total"] or 0) for x in v),
                                               "eta_seen": any(x["eta"] is not None for x in v)} for k, v in stages.items()},
                           "panel_rows_mid_import": panel_rows, "screenshot": str(png) if shot else None}
        # sin IA: carpetas/subcarpetas por reglas y sitios por Apple Maps (falso, tools/fake_geo.py)
        feed = {p["id"]: p for p in db.feed("")["posts"]}
        res["rules"] = {"sub_count": sum(1 for p in feed.values() if p["sub"]),
                        "cats": sorted({c for p in feed.values() for c in p["cat"]}),
                        "lug_posts": sorted(k for k, p in feed.items() if p["lug"]),
                        "lug_names": [l["n"] for p in feed.values() for l in p["lug"]][:5],
                        "gemini_calls_without_key": len(GEMINI["srv"].seen) if GEMINI.get("srv") else None}
        res["attack_ig"] = _js(ig, "for(let i=0;i<60&&!(window.__attack&&window.__attack.done);i++)await new Promise(r=>setTimeout(r,250));return JSON.stringify(window.__attack)")
        res["attack_tt"] = _js(tt, "for(let i=0;i<60&&!(window.__attack&&window.__attack.done);i++)await new Promise(r=>setTimeout(r,250));return JSON.stringify(window.__attack)")
        # IA opcional: la clave se pega en el panel (por el puente, como haría la persona)
        import secrets
        key = "AIzaSelftest" + secrets.token_hex(14)[:27]   # se inventa al vuelo: no queda escrita en el paquete
        res["ia_set"] = _js(panel, "const r = await window.pywebview.api.set_gemini_key(%s); return JSON.stringify(r)" % json.dumps(key))
        t1 = time.time()
        while time.time() - t1 < 60:
            if not api.task["running"] and db.ia_counts()["done"] == db.ia_counts()["total"]:
                break
            time.sleep(0.5)
        kf = Path(api.clave.f)
        status_txt = json.dumps(api.status(), ensure_ascii=False, default=str)
        logtxt = (kf.parent / "app.log").read_text() if (kf.parent / "app.log").exists() else ""
        seen = GEMINI["srv"].seen if GEMINI.get("srv") else []
        feed = {p["id"]: p for p in db.feed("")["posts"]}
        res["ia"] = {"counts": db.ia_counts(), "secs": round(time.time() - t1, 1),
                     "key_file_mode": oct(kf.stat().st_mode & 0o777) if kf.exists() else None,
                     "key_in_status": key in status_txt, "key_in_log": key in logtxt,
                     "calls": len(seen), "all_in_header": bool(seen) and all(x["key_in_header"] and x["key"] == key for x in seen),
                     "any_in_url": any(x["key_in_url"] for x in seen),
                     "sample_sub": feed.get("Selftest000", {}).get("sub"), "sample_lug": len(feed.get("Selftest000", {}).get("lug") or [])}
        # ¿alguna página de IG/TT puede guardar, borrar o leer la clave? (el ataque corre al cargar; se repite ahora)
        steal = r"""
          const out = {};
          for (const f of ['set_gemini_key', 'delete_gemini_key', 'status']) {
            try { const r = await Promise.race([window.pywebview.api[f]('AIzaEVIL' + 'E'.repeat(27)), new Promise(r => setTimeout(() => r('sin respuesta'), 2000))]); out[f] = 'devolvio: ' + JSON.stringify(r).slice(0, 80); }
            catch (e) { out[f] = 'error: ' + String(e).slice(0, 60); }
            try { window.pywebview._jsApiCallback(f, ['AIzaEVIL' + 'E'.repeat(27)], 'id' + Math.random()); out['bridge.' + f] = 'enviado'; } catch (e) { out['bridge.' + f] = 'error'; }
          }
          try { const r = await fetch('http://127.0.0.1:%(port)s/gemini.key'); out.fetch_key = 'LEIDO ' + r.status; } catch (e) { out.fetch_key = 'bloqueado'; }
          await new Promise(r => setTimeout(r, 1500));
          out.page_has_key = document.documentElement.outerHTML.includes(%(key)s);
          return JSON.stringify(out);""" % {"port": srv.port, "key": json.dumps(key)}
        res["steal_key_ig"] = _js(ig, steal)
        res["steal_key_tt"] = _js(tt, steal)
        res["key_after_attack"] = api.clave.get() == key
        try:
            urllib.request.urlopen(srv.base + "/gemini.key")
            res["server_key"] = "SERVIDA (mal)"
        except Exception as e:
            res["server_key"] = str(e)
        res["movil"] = _movil(api, panel, ig, tt, srv, out)
        time.sleep(4)  # el panel ve version nueva y empuja a IndexedDB
        res["panel"] = _js(panel, r"""
          let unsafeEval = null; try { unsafeEval = eval('1+1') === 2; } catch (e) { unsafeEval = 'bloqueado: ' + e; }
          window.__inl = 0; let violated = [];
          document.addEventListener('securitypolicyviolation', e => violated.push(e.violatedDirective));
          const s = document.createElement('script'); s.textContent = 'window.__inl = 1'; document.body.append(s);
          await new Promise(r => setTimeout(r, 300));
          const n = await new Promise(res => { const o = indexedDB.open('guardados'); o.onsuccess = () => { try { const q = o.result.transaction('posts').objectStore('posts').count(); q.onsuccess = () => res(q.result); } catch (e) { res('sin tabla: ' + e); } }; o.onerror = () => res('error'); });
          const rec = document.getElementById('recent');
          return JSON.stringify({ready: !!window.__panelReady, csp_meta: document.querySelector('meta[http-equiv]').content,
            unsafe_eval_ok: unsafeEval, inline_script_ran: window.__inl === 1, violations: violated,
            pwned: window.__pwned || 0, recent_imgs: rec.querySelectorAll('img,script,b').length,
            recent_has_escaped: rec.innerHTML.includes('&lt;img'), recent_text_sample: rec.textContent.slice(0, 160),
            indexeddb_posts: n, web_note: document.getElementById('web').textContent,
            idb_sample: await new Promise(res => { const o = indexedDB.open('guardados'); o.onsuccess = () => { try { const q = o.result.transaction('posts').objectStore('posts').get('Selftest000'); q.onsuccess = () => res({cat: q.result?.cat, sub: q.result?.sub, lug: (q.result?.lug || []).length}); } catch (e) { res(String(e)); } }; })});""")
        viewer.show()
        viewer.load_url(srv.base + "/guardados/?q=r%C3%A1pida%20cenar#Selftest000")
        time.sleep(6)
        res["viewer"] = _js(viewer, r"""
          const cards = [...document.querySelectorAll('#grid .card')];
          const evil = cards.find(c => c.textContent.includes('<img') || c.textContent.includes('Receta de pasta rápida'));
          return JSON.stringify({cards: cards.length, status: (document.getElementById('status')||{}).textContent,
            literal_tag_shown_as_text: document.body.textContent.includes('<img src=x'),
            img_x_anywhere: document.querySelectorAll('img[src="x"]').length, built: (document.getElementById('built')||{}).textContent,
            pwned: window.__pwned || 0, has_pywebview_api: !!(window.pywebview && window.pywebview.api && Object.keys(window.pywebview.api).length),
            evil_card_text: evil ? evil.textContent.trim().slice(0, 120) : null,
            injected_nodes: document.querySelectorAll('#grid img[src="x"], #grid script').length,
            detail_open: !!document.querySelector('dialog[open]'), detail_text: (document.querySelector('dialog[open]')||{textContent:''}).textContent.replace(/\s+/g,' ').trim().slice(0, 200),
            lug_items: document.querySelectorAll('#d-lug-list li:not(.vacio)').length,
            lug_text: (document.getElementById('d-lug-list')||{textContent:''}).textContent.replace(/\s+/g,' ').trim().slice(0, 120),
            lug_tags: document.querySelectorAll('#d-lug-list img, #d-lug-list script').length});""")
        res["manual"] = _manual(viewer, ig, tt, srv, db)
        # cabeceras del panel y del feed
        with urllib.request.urlopen(srv.base + "/panel/") as r:
            res["panel_csp_header"] = r.headers.get("Content-Security-Policy")
        for path, label in (("/feed/adivinado/items.json", "feed_sin_token"), (f"/feed/{srv.token}/items.json", "feed_con_token")):
            try:
                with urllib.request.urlopen(srv.base + path) as r:
                    res[label] = r.status
            except Exception as e:
                res[label] = str(e)
        req = urllib.request.Request(srv.base + "/panel/", headers={"Host": "evil.example:47613"})
        try:
            urllib.request.urlopen(req)
            res["host_rebinding"] = "ACEPTADO (mal)"
        except Exception as e:
            res["host_rebinding"] = str(e)
        time.sleep(1)
    except Exception as e:
        import traceback
        res["exception"] = traceback.format_exc()
    res["api_calls_from_pages"] = calls
    res["bridge_blocked"] = blocked[:40]
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    import webview
    for w in list(webview.windows):
        w.destroy()


EVIL_FOLDER = '<img src=x onerror="window.__pwned=(window.__pwned||0)+1">Trampa'


def _manual(viewer, ig, tt, srv, db):
    """(o) Carpetas a mano desde la ficha de «Mis guardados» (la del vídeo Selftest000, abierta):
    añadir a una que existe, crear una nueva, intentar un nombre hostil (en la web y saltándose
    la web), quitar una; que nada automático lo pise y que Instagram/TikTok no puedan escribir."""
    out = {"antes": db.rutas_de("Selftest000")}
    out["ficha"] = _js(viewer, r"""
      for (let i = 0; i < 40 && !document.querySelector('#d-carp select'); i++) await new Promise(r => setTimeout(r, 250));
      const sec = document.getElementById('d-carp'), sel = sec.querySelector('select[name=ruta]');
      const items = () => [...sec.querySelectorAll('#d-carp-list li .l-main')].map(l => l.textContent);
      const espera = () => new Promise(r => setTimeout(r, 700));
      const hasta = async f => { for (let i = 0; i < 50 && !f(); i++) await new Promise(r => setTimeout(r, 150)); };
      sel.value = 'recetas/postres'; sel.form.requestSubmit(); await hasta(() => items().includes('Recetas \u203a Postres'));
      const tras_anadir = items();
      sel.value = '+'; sel.dispatchEvent(new Event('change'));
      const inp = sec.querySelector('input[name=nombre]');
      inp.value = %(evil)s; inp.form.requestSubmit(); await espera();
      const aviso = sec.querySelector('.d-lug-msg').textContent;
      const T = document.querySelector('meta[name="guardados-mac"]').content;
      const directo = await (await fetch('/api/' + T + '/post/Selftest000', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rutas: ['humor/memes', %(evil)s]})})).json();
      inp.value = %(regalos)s; inp.form.requestSubmit(); await hasta(() => items().includes(%(regalos)s));
      const tras_crear = items(), aviso_crear = sec.querySelector('.d-lug-msg').textContent;
      const n = items().length;
      sec.querySelector('#d-carp-list li .l-x').click(); await hasta(() => items().length < n);   // quita la primera (la automática)
      return JSON.stringify({tras_anadir, aviso, directo, tras_crear, aviso_crear, final: items(), pwned: window.__pwned || 0,
        img_x: document.querySelectorAll('img[src="x"]').length, tags: sec.querySelectorAll('img,script').length,
        chips: [...document.querySelectorAll('#d-cats .chip')].map(b => b.textContent)});""" % {
        "evil": json.dumps(EVIL_FOLDER), "regalos": json.dumps("Regalos 🎁")})   # emoji escapado: evaluate_js con texto ASCII
    out["guardado"] = db.rutas_de("Selftest000")
    # lo automático no lo pisa: re-importar con otra descripción y que la IA diga otra cosa
    db.add({"code": "Selftest000", "caption": "Tutorial de Python y GitHub", "user": "dev"})
    db.set_rutas_ia("Selftest000", ["tecnologia/programacion"], "")
    out["tras_reimportar"] = db.rutas_de("Selftest000")
    feed = next(p for p in db.feed("")["posts"] if p["id"] == "Selftest000")
    out["feed"] = {"cat": feed["cat"], "sub": feed["sub"]}
    # Instagram y TikTok (hostiles) intentan escribir: sin token, ni leyendo «Mis guardados» para sacarlo
    ataque = r"""
      const o = {};
      for (const [k, u, b] of [['post_sin_token', '/api/adivinado/post/Selftest000', '{"rutas":["humor/memes"]}'],
                               ['post_form', '/api/adivinado/post/Selftest000', 'rutas=x']]) {
        try { const r = await fetch('http://127.0.0.1:%(port)s' + u, {method: 'POST', headers: {'Content-Type': k === 'post_form' ? 'text/plain' : 'application/json'}, body: b});
              o[k] = 'LEIDO ' + r.status; } catch (e) { o[k] = 'bloqueado'; }
      }
      try { const r = await fetch('http://127.0.0.1:%(port)s/guardados/'); const t = await r.text(); o.leer_token = 'LEIDO ' + /guardados-mac" content="([^"]+)/.test(t); }
      catch (e) { o.leer_token = 'bloqueado'; }
      return JSON.stringify(o);""" % {"port": srv.port}
    out["ataque_ig"] = _js(ig, ataque)
    out["ataque_tt"] = _js(tt, ataque)
    out["tras_ataque"] = db.rutas_de("Selftest000")
    # cerrar la ficha: la web se rehace con lo nuevo (IndexedDB) y la carpeta nueva sale en el inicio
    _js(viewer, "history.state?.post ? history.back() : document.getElementById('sheet').close(); return 1")
    time.sleep(5)
    viewer.load_url(srv.base + "/guardados/")
    time.sleep(4)
    out["web"] = _js(viewer, r"""
      const nombres = [...document.querySelectorAll('#grid .carpeta .c-nom')].map(e => e.textContent);
      return JSON.stringify({carpetas: nombres, regalos: nombres.includes('Regalos 🎁'), pwned: window.__pwned || 0,
        img_x: document.querySelectorAll('img[src="x"]').length,
        idb: await new Promise(res => { const o = indexedDB.open('guardados'); o.onsuccess = () => { const q = o.result.transaction('posts').objectStore('posts').get('Selftest000'); q.onsuccess = () => res({cat: q.result?.cat, sub: q.result?.sub}); }; })});""")
    return out


def fake_jpeg(dest, i, w=320, h=568):
    """Una portada de prueba: un JPEG de un color distinto por guardado (BMP hecho a mano + sips)."""
    import colorsys
    import struct as st
    import subprocess
    import tempfile
    r, g, b = (int(255 * x) for x in colorsys.hsv_to_rgb((i * 0.137) % 1, 0.65, 0.9))
    row = bytes([b, g, r]) * w + b"\0" * ((4 - (w * 3) % 4) % 4)
    stripe = bytes([255, 255, 255]) * w + b"\0" * ((4 - (w * 3) % 4) % 4)
    pix = b"".join(stripe if (y // 24) % 6 == 0 else row for y in range(h))
    bmp = b"BM" + st.pack("<IHHI", 54 + len(pix), 0, 0, 54) + st.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pix), 2835, 2835, 0, 0) + pix
    with tempfile.NamedTemporaryFile(suffix=".bmp") as t:
        t.write(bmp)
        t.flush()
        p = subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", t.name, "--out", str(dest)], capture_output=True)
    return p.returncode == 0 and Path(dest).is_file()
