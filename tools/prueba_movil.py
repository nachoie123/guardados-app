#!/usr/bin/env python3
"""Prueba de punta a punta del móvil, sin desplegar nada (lo llama tools/seguridad.py).

  python3 tools/prueba_movil.py --enlace build/selftest-enlace.json --persist build/wrangler-state

Necesita el buzón de cloud/ corriendo en local (`npx wrangler dev`, en 127.0.0.1:8787) y
Playwright (Chromium). Sirve la web de ~/Projects/ig-saved/app en 127.0.0.1:8781 (copia sin datos).

(i)  El buzón (Worker): sin token no se escribe; el de lectura no escribe; un id inventado da 404;
     CORS solo para nachosanbenito.com y el localhost de pruebas; tamaño máximo; nombres raros fuera.
(j)  Lo que guarda el servidor (el KV local de wrangler) son bytes cifrados: ni captions, ni
     JPEG, ni gzip, ni JSON, ni la llave; cada objeto con entropía de bytes al azar.
(k)  La web abre el enlace del QR de la app empaquetada: guarda la llave, borra el fragmento,
     baja y descifra el buzón y enseña los guardados con portadas. El QR del panel, leído con
     jsQR, es ese enlace. La llave nunca sale en una petición. Al recargar, solo pide el índice.
(l)  Cambiar la llave en el Mac desconecta el móvil viejo y el enlace nuevo funciona.
(m)  La sincronización de Nacho (sync/ + #k=) da exactamente lo mismo con la web nueva que con
     la de antes (git HEAD), y sin nada conectado tampoco cambia nada ni se llama al buzón.
Los valores de la llave y los tokens no se imprimen nunca.
"""
import argparse
import base64
import gzip
import hashlib
import http.server as hserver
import json
import math
import os
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
IGS = Path.home() / "Projects" / "ig-saved"
sys.path.insert(0, str(HERE))
WEB_PORT = 8781
FILES = ["index.html", "app.css", "app.js", "search.js", "horario.js", "rules.js", "store.js", "buzon-config.js",
         "rules-data.json", "manifest.webmanifest", "sw.js", "bookmarklet.js", "bookmarklet-tiktok.js"]
DIRS = ["icons", "vendor", "demo"]


def b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def http(method, url, body=None, headers=None):
    # con nombre propio: Cloudflare corta con 403 (error 1010) al User-Agent por defecto de Python
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "Guardados-Prueba/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def parse_link(link):
    frag = link.split("#conectar=1.", 1)[1].split("&", 1)[0]
    i, r, k = frag.split(".")
    return i, r, k


# ---------------------------------------------------------------- (i) el Worker
def worker_checks(base):
    out = {}
    i, w, r = b64(secrets.token_bytes(32)), b64(secrets.token_bytes(32)), b64(secrets.token_bytes(32))
    hw, hr = hashlib.sha256(w.encode()).hexdigest(), hashlib.sha256(r.encode()).hexdigest()
    U = f"{base}/v1/{i}"
    body = json.dumps({"w": hw, "r": hr}).encode()
    out["crear"] = http("PUT", U, body, {"Content-Type": "application/json"})[0]
    out["crear_otra_vez"] = http("PUT", U, body, {"Content-Type": "application/json"})[0]
    blob = secrets.token_bytes(5000)
    out["put_sin_token"] = http("PUT", f"{U}/index.bin", blob)[0]
    out["put_token_inventado"] = http("PUT", f"{U}/index.bin", blob, {"Authorization": "Bearer " + b64(secrets.token_bytes(32))})[0]
    out["put_con_token_de_lectura"] = http("PUT", f"{U}/index.bin", blob, {"Authorization": "Bearer " + r})[0]
    out["put_con_token_de_escritura"] = http("PUT", f"{U}/index.bin", blob, {"Authorization": "Bearer " + w})[0]
    out["get_sin_token"] = http("GET", f"{U}/index.bin")[0]
    out["get_con_token_de_escritura"] = http("GET", f"{U}/index.bin", headers={"Authorization": "Bearer " + w})[0]
    st, h, got = http("GET", f"{U}/index.bin", headers={"Authorization": "Bearer " + r})
    out["get_con_token_de_lectura"] = st
    out["get_devuelve_lo_mismo"] = got == blob
    out["get_objeto_que_falta"] = http("GET", f"{U}/0123456789abcdef.bin", headers={"Authorization": "Bearer " + r})[:3:2]
    out["get_id_inventado"] = http("GET", f"{base}/v1/{b64(secrets.token_bytes(32))}/index.bin",
                                   headers={"Authorization": "Bearer " + r})[0]
    out["put_id_inventado"] = http("PUT", f"{base}/v1/{b64(secrets.token_bytes(32))}/index.bin", blob,
                                   {"Authorization": "Bearer " + w})[0]
    out["id_corto"] = http("GET", f"{base}/v1/abc/index.bin")[0]
    out["nombre_meta"] = http("GET", f"{U}/meta", headers={"Authorization": "Bearer " + r})[0]
    out["nombre_raro"] = http("PUT", f"{U}/..%2Fx.bin", blob, {"Authorization": "Bearer " + w})[0]
    out["stats"] = http("GET", f"{base}/v1/_stats")[0]
    big = b"\0" * 25_000_001
    out["put_25MB_mas_1"] = http("PUT", f"{U}/aaaaaaaaaaaaaaaa.bin", big, {"Authorization": "Bearer " + w})[0]
    # CORS: solo la web de guardados y el localhost de pruebas, y solo para leer
    st, h, _ = http("GET", f"{U}/index.bin", headers={"Authorization": "Bearer " + r, "Origin": "https://evil.example"})
    out["origen_malo"] = [st, h.get("Access-Control-Allow-Origin")]
    for o in ("https://nachosanbenito.com", f"http://127.0.0.1:{WEB_PORT}"):
        st, h, _ = http("GET", f"{U}/index.bin", headers={"Authorization": "Bearer " + r, "Origin": o})
        out[f"origen {o}"] = [st, h.get("Access-Control-Allow-Origin")]
    st, h, _ = http("OPTIONS", f"{U}/index.bin", headers={"Origin": "https://nachosanbenito.com",
                                                          "Access-Control-Request-Method": "PUT",
                                                          "Access-Control-Request-Headers": "authorization"})
    out["preflight_metodos"] = h.get("Access-Control-Allow-Methods")
    out["put_desde_navegador"] = http("PUT", f"{U}/index.bin", blob, {"Authorization": "Bearer " + w,
                                                                      "Origin": "https://nachosanbenito.com"})[0]
    out["borrar_sin_token"] = http("DELETE", U)[0]
    out["borrar_con_token"] = http("DELETE", U, headers={"Authorization": "Bearer " + w})[0]
    out["get_tras_borrar"] = http("GET", f"{U}/index.bin", headers={"Authorization": "Bearer " + r})[:3:2]
    out["get_tras_borrar"] = [out["get_tras_borrar"][0], out["get_tras_borrar"][1].decode(errors="replace")]
    out["get_objeto_que_falta"] = [out["get_objeto_que_falta"][0], out["get_objeto_que_falta"][1].decode(errors="replace")]
    ok = (out["crear"] == 201 and out["crear_otra_vez"] == 409 and out["put_sin_token"] == 401
          and out["put_token_inventado"] == 401 and out["put_con_token_de_lectura"] == 401
          and out["put_con_token_de_escritura"] == 201 and out["get_sin_token"] == 401
          and out["get_con_token_de_escritura"] == 401 and out["get_con_token_de_lectura"] == 200
          and out["get_devuelve_lo_mismo"] and out["get_id_inventado"] == 404 and out["put_id_inventado"] == 404
          and out["id_corto"] == 404 and out["nombre_meta"] == 404 and out["nombre_raro"] == 404 and out["stats"] == 404
          and out["put_25MB_mas_1"] == 413 and out["origen_malo"] == [403, None]
          and out["origen https://nachosanbenito.com"] == [200, "https://nachosanbenito.com"]
          and out["preflight_metodos"] == "GET" and out["put_desde_navegador"] == 403
          and out["borrar_sin_token"] == 401 and out["borrar_con_token"] == 200 and out["get_tras_borrar"][0] == 404
          and out["get_objeto_que_falta"][0] == 404 and out["get_tras_borrar"][1] != out["get_objeto_que_falta"][1])
    return ok, out


# ---------------------------------------------------------------- (j) lo que ve el servidor
def entropy(b):
    if not b:
        return 0
    c = Counter(b)
    return -sum(n / len(b) * math.log2(n / len(b)) for n in c.values())


def storage_scan(persist, secretos, marcas):
    files = [f for f in Path(persist).rglob("*") if f.is_file()]
    hits, blobs, low = {}, 0, []
    for f in files:
        data = f.read_bytes()
        for label, m in marcas.items():
            if m in data:
                hits[label] = hits.get(label, 0) + 1
        for j, s in enumerate(secretos):
            if s.encode() in data:
                hits[f"secreto {j}"] = hits.get(f"secreto {j}", 0) + 1
        if "blobs" in f.parts and len(data) >= 1024:
            blobs += 1
            e = entropy(data)
            if e < 8 - 600 / len(data):   # bytes al azar: ~8 bits por byte (menos un sesgo de ~184/len en muestras cortas)
                low.append(round(e, 2))
    return {"ficheros": len(files), "bytes": sum(f.stat().st_size for f in files), "objetos_grandes": blobs,
            "con_entropia_baja": low, "apariciones": hits}


def decrypt_check(base, link):
    """Lo que hay en el buzón de la app, abierto con la llave del enlace (como haría el móvil)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    i, r, k = parse_link(link)
    raw = unb64(k)
    st, _, blob = http("GET", f"{base}/v1/{i}/index.bin", headers={"Authorization": "Bearer " + r})
    ix = json.loads(AESGCM(raw).decrypt(blob[:12], blob[12:], None))
    st2, _, pb = http("GET", f"{base}/v1/{i}/{ix['posts']}", headers={"Authorization": "Bearer " + r})
    posts = json.loads(gzip.decompress(AESGCM(raw).decrypt(pb[:12], pb[12:], None)))["posts"]
    wrong = False
    try:
        AESGCM(secrets.token_bytes(32)).decrypt(blob[:12], blob[12:], None)
    except Exception:
        wrong = True
    sizes = []
    for p in ix["covers"]:
        sizes.append(len(http("GET", f"{base}/v1/{i}/{p['f']}", headers={"Authorization": "Bearer " + r})[2]))
    return {"index": st, "posts_obj": st2, "posts": len(posts), "covers": sum(len(p["ids"]) for p in ix["covers"]),
            "paquetes": len(ix["covers"]), "bytes_datos": len(pb), "bytes_portadas": sum(sizes),
            "otra_llave_no_abre": wrong, "ejemplo": {k2: posts[0].get(k2) for k2 in ("id", "src", "cat", "sub")} if posts else None}


# ---------------------------------------------------------------- la web local
class Web:
    def __init__(self, root):
        class Quiet(hserver.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        h = partial(Quiet, directory=str(root))
        self.s = hserver.ThreadingHTTPServer(("127.0.0.1", WEB_PORT), h)
        threading.Thread(target=self.s.serve_forever, daemon=True).start()

    def close(self):
        self.s.shutdown()
        self.s.server_close()


def web_copy(dst, old=False):
    """Copia de la web de ig-saved, sin datos. old=True: los ficheros tal como están en git HEAD."""
    dst.mkdir(parents=True)
    for f in FILES:
        if old:
            p = subprocess.run(["git", "-C", str(IGS), "show", f"HEAD:app/{f}"], capture_output=True)
            if p.returncode == 0:
                (dst / f).write_bytes(p.stdout)
        else:
            shutil.copy2(IGS / "app" / f, dst / f)
    for d in DIRS:
        shutil.copytree(IGS / "app" / d, dst / d)


IDB_JS = """async () => {
  // sin crearla: si la base aún no existe, abrirla aquí la dejaría vacía y la app no podría montarla
  const open = () => new Promise(r => { const o = indexedDB.open('guardados'); o.onupgradeneeded = () => o.transaction.abort();
    o.onsuccess = () => r(o.result); o.onerror = () => r(null); });
  const d = await open(); if (!d || !d.objectStoreNames.contains('posts')) return {posts: 0, covers: 0, rows: []};
  const all = (s, m) => new Promise(r => { const q = d.transaction(s).objectStore(s)[m](); q.onsuccess = () => r(q.result); });
  const rows = await all('posts', 'getAll'); const ck = await all('covers', 'getAllKeys');
  return {posts: rows.length, covers: ck.length, img: rows.filter(p => p.img).length,
          rows: rows.map(p => ({id: p.id, cat: p.cat, sub: p.sub, lug: (p.lug || []).length, img: !!p.img, ciudad: p.ciudad, src: p.src})).sort((a, b) => a.id < b.id ? -1 : 1)};
}"""


def wait_idb(page, n, covers, secs=90):
    t0, st = time.time(), {}
    while time.time() - t0 < secs:
        st = page.evaluate(IDB_JS)
        if st["posts"] >= n and st["covers"] >= covers:
            break
        time.sleep(0.5)
    return st


def web_e2e(pw, root, link_file, worker_base, shot):
    d = json.loads(Path(link_file).read_text())
    link, n = d["enlace"], d["n"]
    i, r, k = parse_link(link)
    web = Web(root)
    out = {}
    try:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
        reqs = []
        ctx.on("request", lambda q: reqs.append({"url": q.url, "auth": "authorization" in {h.lower() for h in q.headers}}))
        page = ctx.new_page()
        # el QR del panel, leído con jsQR (el mismo lector de la web): ¿es este enlace?
        page.goto(f"http://127.0.0.1:{WEB_PORT}/vendor/jsQR.js")
        page.set_content("<canvas id=c></canvas>")
        page.add_script_tag(path=str(root / "vendor" / "jsQR.js"))
        decoded = page.evaluate("""async src => { const img = new Image(); img.src = src; await img.decode();
            const c = document.getElementById('c'); c.width = img.naturalWidth * 2; c.height = img.naturalHeight * 2;
            const x = c.getContext('2d'); x.imageSmoothingEnabled = false; x.drawImage(img, 0, 0, c.width, c.height);
            const r = jsQR(x.getImageData(0, 0, c.width, c.height).data, c.width, c.height); return r && r.data; }""", d["qr"])
        out["qr_es_el_enlace"] = decoded == link
        reqs.clear()
        page.goto(link)
        st = wait_idb(page, n, n)
        page.wait_for_timeout(1500)
        out["idb"] = {k2: st.get(k2) for k2 in ("posts", "covers", "img")}
        out["url_tras_abrir"] = page.url
        out["fragmento_borrado"] = "#" not in page.url and "conectar" not in page.url
        ls = page.evaluate("() => localStorage.getItem('guardados.buzon')") or ""
        out["llave_guardada_en_el_dispositivo"] = k in ls and i in ls
        out["dialogo"] = page.evaluate("() => { const d = document.getElementById('mac'); return d.open ? document.getElementById('mac-msg').textContent : null; }")
        if out["dialogo"] is not None:
            page.click("#mac-done")
        page.wait_for_timeout(800)
        page.evaluate("() => { const sh = document.querySelector('dialog[open]'); if (sh) sh.close(); }")
        page.wait_for_timeout(800)
        grid = page.evaluate("""() => { const imgs = [...document.querySelectorAll('#grid img')];
            return {carpetas: document.querySelectorAll('#grid > li').length, imgs: imgs.length,
                    blob: imgs.filter(i => i.src.startsWith('blob:')).length,
                    pintadas: imgs.filter(i => i.complete && i.naturalWidth > 0).length,
                    ancho: imgs.length ? imgs[0].naturalWidth : 0,
                    built: (document.getElementById('built') || {}).textContent, status: (document.getElementById('status') || {}).textContent}; }""")
        out["grid"] = grid
        page.screenshot(path=str(shot))
        worker = [q for q in reqs if q["url"].startswith(worker_base)]
        out["peticiones_al_buzon"] = len(worker)
        out["todas_con_cabecera"] = all(q["auth"] for q in worker)
        out["llave_o_token_en_alguna_url"] = any(k in q["url"] or r in q["url"] for q in reqs)
        reqs.clear()
        page.reload()
        page.wait_for_timeout(3000)
        again = [q["url"].rsplit("/", 1)[1] for q in reqs if q["url"].startswith(worker_base)]
        out["al_recargar_pide"] = again
        st2 = page.evaluate(IDB_JS)
        out["al_recargar_idb"] = {k2: st2.get(k2) for k2 in ("posts", "covers")}
        # una búsqueda: la lista de vídeos, cada uno con su portada
        page.goto(f"http://127.0.0.1:{WEB_PORT}/?q=pasta")
        page.wait_for_timeout(3000)
        out["busqueda"] = page.evaluate("""() => { const imgs = [...document.querySelectorAll('#grid .card img')];
            return {tarjetas: document.querySelectorAll('#grid .card').length, con_portada: imgs.filter(i => i.src.startsWith('blob:') && i.naturalWidth === 270).length}; }""")
        page.screenshot(path=str(shot).replace(".png", "-lista.png"))
        b.close()
    finally:
        web.close()
    ok = (out["qr_es_el_enlace"] and out["idb"]["posts"] == n and out["idb"]["covers"] == n and out["fragmento_borrado"]
          and out["llave_guardada_en_el_dispositivo"] and out["grid"]["blob"] >= 1 and out["grid"]["pintadas"] >= 1
          and out["grid"]["ancho"] == 270 and out["todas_con_cabecera"] and not out["llave_o_token_en_alguna_url"]
          and out["al_recargar_pide"] == ["index.bin"] and out["al_recargar_idb"] == {"posts": n, "covers": n}
          and out["busqueda"]["tarjetas"] >= 1 and out["busqueda"]["con_portada"] >= 1)
    return ok, out


# ---------------------------------------------------------------- (l) cambiar la llave
def rotation(pw, root, worker_base):
    import db as dbmod
    import nube
    import selftest
    os.environ["GUARDADOS_BUZON_URL"] = worker_base
    os.environ["GUARDADOS_WEB_URL"] = f"http://127.0.0.1:{WEB_PORT}/"
    d = Path(tempfile.mkdtemp(prefix="guardados-rot."))
    db = dbmod.DB(d / "guardados.db")
    (d / "media").mkdir()
    for j in range(12):
        code = f"Rotacion{j:03d}"
        db.add({"code": code, "caption": f"Truco {j} para ahorrar", "user": f"rot{j}", "taken_at": 1750000000 - j, "type": 2})
        selftest.fake_jpeg(d / "media" / f"{code}.jpg", j)
        db.set_cover(code, True)
    n = nube.Nube(d, db, d / "media")
    n.asegurar()
    out = {"subir": n.subir()}
    old = n.enlace()
    web = Web(root)
    try:
        b = pw.chromium.launch()
        ctx = b.new_context(service_workers="block")
        page = ctx.new_page()
        page.goto(old)
        out["antes"] = {k2: v for k2, v in wait_idb(page, 12, 12, 40).items() if k2 in ("posts", "covers")}
        # un guardado nuevo en el Mac: el móvil lo recibe al volver a abrir
        db.add({"code": "Rotacion999", "caption": "Uno nuevo", "user": "rot", "taken_at": 1760000000, "type": 2})
        selftest.fake_jpeg(d / "media" / "Rotacion999.jpg", 99)
        db.set_cover("Rotacion999", True)
        out["subir_nuevo"] = n.subir()
        page.reload()
        out["con_uno_nuevo"] = {k2: v for k2, v in wait_idb(page, 13, 13, 30).items() if k2 in ("posts", "covers")}
        n.cambiar()
        out["subir_llave_nueva"] = n.subir()
        page.reload()
        page.wait_for_timeout(3000)
        out["movil_viejo"] = page.evaluate("() => ({buzon: localStorage.getItem('guardados.buzon'), status: document.getElementById('status').textContent})")
        i, r, _ = parse_link(old)
        out["id_viejo"] = http("GET", f"{worker_base}/v1/{i}/index.bin", headers={"Authorization": "Bearer " + r})[0]
        new = n.enlace()
        out["enlace_distinto"] = parse_link(new)[2] != parse_link(old)[2] and parse_link(new)[0] != parse_link(old)[0]
        ctx2 = b.new_context(service_workers="block")
        p2 = ctx2.new_page()
        p2.goto(new)
        out["movil_nuevo"] = {k2: v for k2, v in wait_idb(p2, 13, 13, 40).items() if k2 in ("posts", "covers")}
        b.close()
    finally:
        web.close()
        try:
            c = n.cred()
            urllib.request.urlopen(urllib.request.Request(f"{worker_base}/v1/{c['id']}", method="DELETE",
                                                          headers={"Authorization": "Bearer " + c["w"]}), timeout=20)
        except Exception:
            pass
        shutil.rmtree(d, ignore_errors=True)
    ok = (out["subir"].get("ok") and out["antes"] == {"posts": 12, "covers": 12} and out["con_uno_nuevo"] == {"posts": 13, "covers": 13}
          and out["movil_viejo"]["buzon"] is None and "desconectado" in out["movil_viejo"]["status"]
          and out["id_viejo"] == 404 and out["enlace_distinto"] and out["movil_nuevo"] == {"posts": 13, "covers": 13})
    out["movil_viejo"]["buzon"] = "borrado" if out["movil_viejo"]["buzon"] is None else "SIGUE (mal)"
    return ok, out


# ---------------------------------------------------------------- (m) la sincronización de Nacho
def fake_sync(sync_dir, raw, n=30):
    """Paquetes como los de tools/sync-pack.py (mismo formato), con datos inventados y una llave de prueba."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import selftest

    def seal(data):
        iv = secrets.token_bytes(12)
        return iv + AESGCM(raw).encrypt(iv, data, None)

    def write(data):
        name = secrets.token_hex(8) + ".bin"
        (sync_dir / name).write_bytes(seal(data))
        return name
    sync_dir.mkdir(parents=True)
    posts = [{"id": f"NachoPrueba{j:03d}", "src": "instagram", "u": f"cuenta{j}", "n": f"Cuenta {j}",
              "c": f"Bar de prueba {j} en Madrid", "d": 1750000000 - j, "v": True, "p": j, "url": None, "tr": "",
              "cat": ["sitios"] if j % 2 else ["recetas"], "sub": ["sitios/bares"] if j % 2 else ["recetas/pasta"],
              "ciudad": "Madrid", "lug": [{"n": f"Bar {j}", "t": "bares", "ci": "Madrid", "lat": 40.4 + j / 1000, "lng": -3.7, "a": ""}] if j % 2 else [],
              "img": True} for j in range(n)]
    ix = {"v": 1, "covers": [], "built": "2026-10-01T12:00:00"}
    ix["posts"] = write(gzip.compress(json.dumps({"built": ix["built"], "posts": posts}).encode()))
    pk = []
    with tempfile.TemporaryDirectory() as t:
        for j, p in enumerate(posts):
            f = Path(t) / f"{p['id']}.jpg"
            selftest.fake_jpeg(f, j, 270, 480)
            pk.append((p["id"], f.read_bytes()))
    head = json.dumps([[i, len(b)] for i, b in pk]).encode()
    ix["covers"].append({"f": write(struct.pack(">I", len(head)) + head + b"".join(b for _, b in pk)), "ids": [i for i, _ in pk]})
    (sync_dir / "index.bin").write_bytes(seal(json.dumps(ix).encode()))
    return n


def nacho_run(pw, root, key, n, worker_base):
    web = Web(root)
    out = {}
    try:
        b = pw.chromium.launch()
        # 1) sin nada conectado: la muestra, y ni una petición al buzón
        ctx = b.new_context(service_workers="block")
        reqs = []
        ctx.on("request", lambda q: reqs.append(q.url))
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{WEB_PORT}/")
        page.wait_for_timeout(2500)
        out["sin_conectar"] = page.evaluate("() => ({cards: document.querySelectorAll('#grid .card').length, built: document.getElementById('built').textContent, mac: document.getElementById('f-mac').textContent})")
        out["sin_conectar"]["peticiones_buzon"] = sum(1 for u in reqs if worker_base in u or "workers.dev" in u)
        out["sin_conectar"]["peticiones_sync"] = sum(1 for u in reqs if "/sync/" in u)
        ctx.close()
        # 2) el QR de Nacho (#k=): sus paquetes de sync/
        ctx = b.new_context(service_workers="block")
        reqs = []
        ctx.on("request", lambda q: reqs.append(q.url))
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{WEB_PORT}/#k={key}")
        st = wait_idb(page, n, n, 40)
        page.wait_for_timeout(1500)
        out["con_k"] = {"idb": {k2: st.get(k2) for k2 in ("posts", "covers", "img")}, "rows": st.get("rows"),
                        "url": page.url.replace(key, "<llave>"),
                        "ls": page.evaluate("() => Object.keys(localStorage).sort()"),
                        "built": page.evaluate("() => document.getElementById('built').textContent"),
                        "mac": page.evaluate("() => document.getElementById('f-mac').textContent"),
                        "peticiones": sorted({u.split('/')[-1] if '/sync/' in u else 'otra' for u in reqs if '/sync/' in u}),
                        "peticiones_buzon": sum(1 for u in reqs if worker_base in u or "workers.dev" in u)}
        page.reload()
        page.wait_for_timeout(2500)
        out["con_k"]["al_recargar"] = {k2: v for k2, v in page.evaluate(IDB_JS).items() if k2 in ("posts", "covers")}
        b.close()
    finally:
        web.close()
    return out


def nacho_checks(pw, tmp, worker_base):
    raw = secrets.token_bytes(32)
    key = b64(raw)   # llave de prueba (no la .sync-key de Nacho, que no se toca)
    res = {}
    for label, old in (("antes", True), ("ahora", False)):
        root = tmp / f"web-{label}"
        web_copy(root, old=old)
        n = fake_sync(root / "sync", raw)
        res[label] = nacho_run(pw, root, key, n, worker_base)
    a, b = res["antes"], res["ahora"]
    same = (a["sin_conectar"] == b["sin_conectar"] and a["con_k"]["idb"] == b["con_k"]["idb"]
            and a["con_k"]["rows"] == b["con_k"]["rows"] and a["con_k"]["ls"] == b["con_k"]["ls"]
            and a["con_k"]["url"] == b["con_k"]["url"] and a["con_k"]["built"] == b["con_k"]["built"]
            and a["con_k"]["mac"] == b["con_k"]["mac"] and a["con_k"]["al_recargar"] == b["con_k"]["al_recargar"])
    ok = (same and b["con_k"]["idb"]["posts"] == 30 and b["con_k"]["idb"]["covers"] == 30
          and b["sin_conectar"]["peticiones_buzon"] == 0 and b["con_k"]["peticiones_buzon"] == 0 and "#" not in b["con_k"]["url"])
    for v in res.values():
        v["con_k"]["rows"] = f"{len(v['con_k']['rows'])} filas (id, carpeta, subcarpeta, sitios, portada)"
    return ok, {"iguales": same, **res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enlace", default=str(HERE / "build" / "selftest-enlace.json"))
    ap.add_argument("--persist", default=str(HERE / "build" / "wrangler-state"))
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--out", default=str(HERE / "build" / "prueba-movil.json"))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    res, oks = {}, {}
    tmp = Path(tempfile.mkdtemp(prefix="guardados-web."))
    try:
        oks["i"], res["worker"] = worker_checks(a.base)
        link = json.loads(Path(a.enlace).read_text())["enlace"] if Path(a.enlace).exists() else None
        with sync_playwright() as pw:
            if link:
                root = tmp / "web"
                web_copy(root)
                oks["k"], res["web"] = web_e2e(pw, root, a.enlace, a.base, HERE / "build" / "movil-web.png")
                res["web"]["captura"] = "build/movil-web.png"
                res["buzon_de_la_app"] = decrypt_check(a.base, link)
                i, r, k = parse_link(link)
                res["servidor"] = storage_scan(a.persist, [k], {
                    "captions de prueba": b"Receta n", "codes de prueba": b"Selftest0", "TikTok de prueba": b"Truco de Excel",
                    "cuentas de prueba": b"cuenta_1", "JPEG (cabecera JFIF)": b"JFIF", "JSON de guardados": b'"posts"',
                    "carpetas": b"recetas"})
                oks["j"] = (not res["servidor"]["apariciones"] and not res["servidor"]["con_entropia_baja"]
                            and res["servidor"]["objetos_grandes"] >= 2 and res["buzon_de_la_app"]["otra_llave_no_abre"])
                oks["l"], res["rotacion"] = rotation(pw, root, a.base)
            else:
                res["web"] = {"error": f"no está {a.enlace}: el selftest de la app no subió nada"}
                oks["k"] = oks["j"] = oks["l"] = False
            oks["m"], res["nacho"] = nacho_checks(pw, tmp, a.base)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    res["ok"] = oks
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(oks))
    sys.exit(0 if all(oks.values()) else 1)


if __name__ == "__main__":
    main()
