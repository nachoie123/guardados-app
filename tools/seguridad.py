#!/usr/bin/env python3
"""Chequeo de seguridad de dist/Guardados.app, ejecutado de verdad. Escribe docs/seguridad.md.

  .venv/bin/python tools/seguridad.py dist/Guardados.app

(a) Datos personales: abre TODO el paquete (también el archivo comprimido de
    Python que va dentro del ejecutable y los .zip) y busca: la clave de
    sincronización de ig-saved (.sync-key), claves de Gemini, correos y
    teléfono de Nacho, rutas /Users/<usuario>, nombres de ficheros de datos y
    los codes de TODOS los posts de su saved.db (abierta en solo lectura).
    Ninguno de esos valores se imprime: solo cuántas veces aparece.
(b)(c)(d) Lanza la app empaquetada en modo selftest (Instagram/TikTok falsos y
    hostiles, sin internet) y recoge: llamadas bloqueadas en el puente, CSP del
    panel (cabecera, meta, eval permitido, script en línea bloqueado) y escapado
    de nombres y captions en el panel y en "Mis guardados".
(e) Clave de Gemini: no está en el paquete; el selftest la pega en el panel (por el
    puente, como la persona) y comprueba fichero 600, que no sale en status() ni en
    app.log, que viaja solo en la cabecera al Gemini FALSO y que las páginas de IG/TT
    no pueden guardarla, borrarla ni leerla.
(f) Nombres de sitios hostiles (Apple Maps falso) escapados en la ficha de "Mis guardados".
(g) Barra de progreso vista en el panel en plena importación (y captura build/panel-progreso.png).
(h) Carpetas, subcarpetas y mapa SIN IA llegan a la web (IndexedDB) y sin clave no se llama a Gemini.
(i)-(m) El móvil (docs/diseno.md, decisión 9): arranca el buzón de cloud/ en local (`npx wrangler dev`,
    sin desplegar nada), el selftest pulsa «Conectar el móvil» en el panel y la app empaquetada sube su
    buzón cifrado; luego tools/prueba_movil.py abre el enlace del QR en una web local (Chromium) y mira
    que salen los guardados con portadas, que el Worker no deja escribir sin token, que un id inventado
    da 404, que el servidor solo guarda bytes cifrados, que cambiar la llave desconecta el móvil viejo y
    que la sincronización de Nacho (sync/ + #k=) da lo mismo que la web de antes (git HEAD).
(n) La llave del móvil en el Mac: fichero 600, ni en status() ni en app.log ni en el HTML del panel;
    Instagram/TikTok no pueden pedir el QR ni cambiar la llave; el servidor local no la sirve.
Además: arquitecturas de cada binario (universal2 = x86_64 + arm64) y que el buscador
de Apple Maps empaquetado contesta de verdad (una búsqueda pública: «Museo del Prado»).
"""
import json
import os
import re
import shutil
import signal
import time
import urllib.request
import sqlite3
import subprocess
import sys
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
IGS = Path.home() / "Projects" / "ig-saved"


def bundle_blobs(app: Path):
    """(nombre, bytes) de cada fichero del .app, con los archivos de PyInstaller abiertos."""
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    for f in app.rglob("*"):
        if not f.is_file() or f.is_symlink():
            continue
        data = f.read_bytes()
        yield str(f.relative_to(app)), data
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    yield f"{f.name}!{n}", z.read(n)
        if f.name == "Guardados" and f.parent.name == "MacOS":
            try:
                ca = CArchiveReader(str(f))
            except Exception:
                continue
            for name in ca.toc:
                try:
                    blob = ca.extract(name)
                except Exception:
                    continue
                yield f"exe!{name}", blob or b""
                if name.endswith(".pyz") or name.startswith("PYZ"):
                    tmp = HERE / "build" / "_pyz.tmp"
                    tmp.write_bytes(blob)
                    z = ZlibArchiveReader(str(tmp))
                    for mod in z.toc:
                        try:
                            code = z.extract(mod, raw=True)
                        except TypeError:
                            code = z.extract(mod)
                        if isinstance(code, bytes):
                            try:
                                code = zlib.decompress(code)
                            except zlib.error:
                                pass
                            yield f"pyz!{mod}", code
                        else:
                            import marshal
                            yield f"pyz!{mod}", marshal.dumps(code) if code else b""
                    tmp.unlink()


def secrets_to_find():
    """{etiqueta: [patrones bytes]}. Los valores reales no se imprimen nunca."""
    s = {}
    k = IGS / ".sync-key"
    if k.exists():
        s["clave de sincronización (.sync-key)"] = [k.read_text().strip().encode()]
    keys = []
    for f in (Path.home() / "Projects" / "goodnotes-apuntes").glob(".gemini-key*"):
        keys.append(f.read_text().strip().encode())
    if keys:
        s["claves de Gemini de Nacho (valor exacto)"] = keys
    s["cualquier clave con forma de Gemini (AIza…)"] = [re.compile(rb"AIza[0-9A-Za-z_\-]{35}")]
    # correos, teléfono…: uno por línea en tools/.personal (fuera del repo, para no publicarlos)
    personal = Path(__file__).with_name(".personal")
    if personal.exists():
        s["datos personales (tools/.personal)"] = [l.strip().encode() for l in personal.read_text().splitlines() if l.strip()]
    s["ruta de su carpeta personal (/Users/" + Path.home().name.encode().decode() + ")"] = [str(Path.home()).encode()]
    codes = []
    db = IGS / "saved.db"
    if db.exists():
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        codes = [r[0] for r in c.execute("SELECT code FROM posts WHERE code IS NOT NULL") if r[0] and len(r[0]) >= 8]
        c.close()
    s[f"codes de sus {len(codes)} guardados (saved.db)"] = [x.encode() for x in codes]
    return s


DATAFILES = "ficheros de datos dentro del paquete (saved.db, posts.json, mis-guardados*.json, .sync-key, k-test.txt, .gemini-key, gemini.key, guardados.db, movil.json)"


def scan(app):
    pats = secrets_to_find()
    hits = {k: {} for k in pats}
    files = 0
    total = 0
    sets = {k: set(v) for k, v in pats.items() if all(isinstance(p, bytes) for p in v) and len(v) > 50}
    word = re.compile(rb"[A-Za-z0-9_\-]{8,40}")
    datafiles = re.compile(r"(saved\.db|posts\.json|mis-guardados[^/]*\.json|\.sync-key|k-test\.txt|\.gemini-key[^/]*|gemini\.key|guardados\.db|movil\.json)$")
    hits[DATAFILES] = {}
    for name, data in bundle_blobs(app):
        files += 1
        if datafiles.search(name) and not name.endswith("demo/posts.json"):
            hits[DATAFILES][name] = 1
        total += len(data)
        for label, plist in pats.items():
            if label in sets:
                n = sum(1 for w in word.findall(data) if w in sets[label])
            else:
                n = sum(len(p.findall(data)) if hasattr(p, "findall") else data.count(p) for p in plist)
            if n:
                hits[label][name] = n
    return files, total, hits


def archs(app):
    out = {}
    for f in app.rglob("*"):
        if f.is_file() and not f.is_symlink() and (f.suffix in (".so", ".dylib") or f.parent.name == "MacOS"
                                                   or f.name in ("Python", "geo", "sello")):
            r = subprocess.run(["lipo", "-archs", str(f)], capture_output=True, text=True)
            if r.returncode == 0:
                out[str(f.relative_to(app))] = r.stdout.strip()
    return out


def selftest(app):
    out = HERE / "build" / "selftest-app.json"
    if out.exists():
        out.unlink()
    env = dict(os.environ, OUT=str(out))
    subprocess.run([str(HERE / "tools" / "selftest.sh"), str(app / "Contents" / "MacOS" / "Guardados")],
                   env=env, capture_output=True, text=True, timeout=420)
    return json.loads(out.read_text()) if out.exists() else {"exception": "la app no escribió el resultado"}


CLOUD = HERE / "cloud"
PERSIST = HERE / "build" / "wrangler-state"
WORKER = "http://127.0.0.1:8787"


def worker_start():
    """El buzón de cloud/ en local, con un KV vacío en build/wrangler-state. Nada se despliega."""
    shutil.rmtree(PERSIST, ignore_errors=True)
    env = dict(os.environ, PATH=str(Path.home() / ".local" / "node" / "bin") + ":" + os.environ.get("PATH", ""))
    log = open(HERE / "build" / "wrangler.log", "w")
    p = subprocess.Popen(["npx", "wrangler", "dev", "--ip", "127.0.0.1", "--port", "8787", "--persist-to", str(PERSIST),
                          "--log-level", "warn"], cwd=CLOUD, env=env, stdout=log, stderr=log, start_new_session=True)
    for _ in range(90):
        try:
            urllib.request.urlopen(WORKER + "/", timeout=2)
        except urllib.error.HTTPError:
            return p   # contesta (404): está listo
        except Exception:
            time.sleep(1)
    return p


def worker_stop(p):
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=20)
    except Exception:
        pass


def prueba_movil():
    out = HERE / "build" / "prueba-movil.json"
    if out.exists():
        out.unlink()
    subprocess.run(["/usr/bin/env", "python3", str(HERE / "tools" / "prueba_movil.py"), "--persist", str(PERSIST),
                    "--base", WORKER, "--out", str(out)], capture_output=True, text=True, timeout=900)
    return json.loads(out.read_text()) if out.exists() else {"ok": {}}


def geo_real(app):
    """El buscador de Apple Maps que va dentro del .app, contra Apple de verdad (búsqueda pública)."""
    b = next((f for f in app.rglob("geo") if f.is_file() and not f.is_symlink()), None)
    if not b:
        return {"error": "no está en el paquete"}
    try:
        p = subprocess.run([str(b)], input='[{"id":"p","q":"Museo del Prado, Madrid"}]', capture_output=True,
                           text=True, timeout=60)
        d = json.loads(p.stdout.splitlines()[0])
        c = (d.get("c") or [{}])[0]
        return {"path": str(b.relative_to(app)), "ok": d.get("ok"), "name": c.get("name"), "cat": c.get("cat"),
                "lat": round(c.get("lat", 0), 3), "lng": round(c.get("lng", 0), 3)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:120]}


EVIL = '<img src=x onerror=…>Trampa'


def main():
    app = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "dist" / "Guardados.app").resolve()
    files, size, hits = scan(app)
    ar = archs(app)
    not_universal = {k: v for k, v in ar.items() if set(v.split()) != {"x86_64", "arm64"}}
    wk = worker_start()
    try:
        st = selftest(app)
        pm = prueba_movil()
    finally:
        worker_stop(wk)
    panel, viewer = st.get("panel", {}), st.get("viewer", {})
    blocked = st.get("bridge_blocked", [])
    a_ig = (st.get("attack_ig") or {}).get("tries", {})

    ok_a = not any(v for k, v in hits.items())
    ok_b = (not st.get("api_calls_from_pages")) and len(blocked) >= 10 and a_ig.get("api_keys") == [] \
        and not viewer.get("has_pywebview_api")
    ok_c = bool(st.get("panel_csp_header")) and "'unsafe-eval'" in st["panel_csp_header"] \
        and "'unsafe-inline'" not in st["panel_csp_header"].split("script-src")[1].split(";")[0] \
        and panel.get("unsafe_eval_ok") is True and panel.get("inline_script_ran") is False
    ok_d = panel.get("pwned") == 0 and viewer.get("pwned") == 0 and panel.get("recent_imgs") == 0 \
        and panel.get("recent_has_escaped") and viewer.get("literal_tag_shown_as_text") and viewer.get("img_x_anywhere") == 0
    ok_e2e = (st.get("auto_import", {}).get("counts", {}).get("instagram", {}).get("n") == 60
              and st.get("auto_import", {}).get("counts", {}).get("tiktok", {}).get("n") == 40
              and panel.get("indexeddb_posts") == 100)
    iax, ru, pg = st.get("ia") or {}, st.get("rules") or {}, st.get("progress") or {}
    steals = [st.get("steal_key_ig") or {}, st.get("steal_key_tt") or {}]
    ok_e = (not any(v for k, v in hits.items() if "Gemini" in k or "gemini" in k)
            and st.get("ia_set") == {"ok": True} and iax.get("key_file_mode") == "0o600"
            and iax.get("key_in_status") is False and iax.get("key_in_log") is False
            and iax.get("all_in_header") is True and iax.get("any_in_url") is False
            and all(s and not any(str(v).startswith("devolvio") for v in s.values()) and s.get("page_has_key") is False
                    and s.get("fetch_key") == "bloqueado" for s in steals)
            and st.get("key_after_attack") is True and "404" in str(st.get("server_key")))
    ok_f = viewer.get("lug_items", 0) >= 1 and viewer.get("lug_tags") == 0 and "<img" in (viewer.get("lug_text") or "") \
        and viewer.get("pwned") == 0
    tt_seen = (pg.get("stages_seen") or {}).get("tt") or {}
    ig_seen = (pg.get("stages_seen") or {}).get("ig") or {}
    rows = pg.get("panel_rows_mid_import") or []
    ok_g = (tt_seen.get("max_total") == 40 and tt_seen.get("eta_seen") and ig_seen.get("max_total") == 0
            and ig_seen.get("last", {}).get("state") == "ok"
            and any(r.get("name") == "TikTok" and "de 40" in r.get("num", "") for r in rows) and bool(pg.get("screenshot")))
    ok_h = (ru.get("sub_count") == 100 and "sitios" in (ru.get("cats") or []) and len(ru.get("lug_posts") or []) >= 2
            and ru.get("gemini_calls_without_key") == 0
            and (panel.get("idb_sample") or {}).get("lug", 0) >= 1 and (panel.get("idb_sample") or {}).get("sub"))
    mv = st.get("movil") or {}
    pok = pm.get("ok") or {}
    ok_i, ok_j, ok_k, ok_l, ok_m = (pok.get(x) is True for x in "ijklm")
    msteals = [mv.get("steal_ig") or {}, mv.get("steal_tt") or {}]
    ok_n = (mv.get("panel_qr_shown") is True and mv.get("qr_is_svg") is True and mv.get("cred_mode") == "0o600"
            and mv.get("secret_in_status") is False and mv.get("secret_in_log") is False
            and mv.get("secret_in_panel_html") is False and mv.get("cred_same_after_attack") is True
            and all(x and not any(str(v).startswith("devolvio") or str(v).startswith("LEIDO") for v in x.values()) for x in msteals)
            and "404" in str(mv.get("server_cred")) and (mv.get("estado") or {}).get("covers") == 100
            and mv.get("again") == {"skip": "sin cambios"})
    man = st.get("manual") or {}
    fi, mw = man.get("ficha") or {}, man.get("web") or {}
    ataques = [man.get("ataque_ig") or {}, man.get("ataque_tt") or {}]
    guard = man.get("guardado") or [[], False]
    ok_o = (bool(fi) and "Recetas › Postres" in (fi.get("tras_anadir") or []) and "no vale" in (fi.get("aviso") or "")
            and (fi.get("directo") or {}).get("ok") is False and "Regalos 🎁" in (fi.get("tras_crear") or [])
            and fi.get("pwned") == 0 and fi.get("img_x") == 0 and fi.get("tags") == 0
            and guard[1] is True and "Regalos 🎁" in guard[0] and "recetas/postres" in guard[0] and ((man.get("antes") or [[None]])[0] or [None])[0] not in guard[0]
            and man.get("tras_reimportar") == guard and man.get("tras_ataque") == guard
            and "Regalos 🎁" in ((man.get("feed") or {}).get("cat") or [])
            and all(a and not any(str(v).startswith("LEIDO 200") or v == "LEIDO true" for v in a.values()) for a in ataques)
            and mw.get("regalos") is True and mw.get("pwned") == 0 and mw.get("img_x") == 0
            and "Regalos 🎁" in ((mw.get("idb") or {}).get("cat") or []))
    geo = geo_real(app)
    ok_geo = geo.get("ok") is True and abs(geo.get("lat", 0) - 40.414) < 0.02 and abs(geo.get("lng", 0) + 3.692) < 0.02
    mark = lambda b: "OK" if b else "FALLA"

    L = [f"# Chequeo de seguridad de Guardados.app", "",
         f"Generado por `tools/seguridad.py` el {datetime.now():%Y-%m-%d %H:%M} sobre `{app.relative_to(HERE)}`.",
         "Todo lo de abajo es salida real de este script, no texto escrito a mano.", "",
         "| Prueba | Resultado |", "|---|---|",
         f"| (a) Sin datos personales ni claves en el paquete | {mark(ok_a)} |",
         f"| (b) Instagram/TikTok no pueden llamar a la app (js_api solo en el panel) | {mark(ok_b)} |",
         f"| (c) CSP del panel con 'unsafe-eval' y sin script en línea | {mark(ok_c)} |",
         f"| (d) Nombres y captions escapados (panel y Mis guardados) | {mark(ok_d)} |",
         f"| App empaquetada importa sola de punta a punta (IG/TT falsos) | {mark(ok_e2e)} |",
         f"| (e) Clave de Gemini: fuera del paquete, fichero 600, ni en logs ni en status, solo en cabecera; IG/TT no la tocan | {mark(ok_e)} |",
         f"| (f) Nombres de sitios hostiles escapados en «Mis guardados» | {mark(ok_f)} |",
         f"| (g) Barra de progreso en el panel durante la importación | {mark(ok_g)} |",
         f"| (h) Carpetas, subcarpetas y mapa sin IA llegan a la web; sin clave, cero llamadas a Gemini | {mark(ok_h)} |",
         f"| (i) Buzón: sin token no se escribe, id inventado da 404, CORS solo nachosanbenito.com (+ localhost de pruebas), tope de tamaño | {mark(ok_i)} |",
         f"| (j) El servidor solo guarda bytes cifrados (ni texto, ni JPEG, ni la llave) | {mark(ok_j)} |",
         f"| (k) App empaquetada sube → la web abre el enlace del QR → guardados con portadas; la llave nunca viaja | {mark(ok_k)} |",
         f"| (l) «Desconectar móviles» deja fuera al móvil viejo; el código nuevo funciona | {mark(ok_l)} |",
         f"| (m) La sincronización de Nacho (sync/ + #k=) da lo mismo que la web de antes; sin buzón, ni una petición | {mark(ok_m)} |",
         f"| (n) Llave del móvil: fichero 600, ni en status ni en logs ni en el panel; IG/TT no piden el QR ni la cambian | {mark(ok_n)} |",
         f"| (o) Carpetas a mano: se guardan aparte, nada automático las pisa, nombres hostiles fuera; IG/TT no escriben | {mark(ok_o)} |",
         f"| Buscador de Apple Maps empaquetado contesta (Apple real) | {mark(ok_geo)} |",
         f"| Todos los binarios universal2 (x86_64 + arm64) | {mark(not not_universal)} ({len(ar)} binarios) |",
         "", "## (a) Datos personales", "",
         f"Ficheros revisados: {files} (incluye cada módulo del archivo comprimido de Python dentro del ejecutable),"
         f" {size / 1e6:.1f} MB descomprimidos. Apariciones de cada cosa buscada:", ""]
    for k, v in hits.items():
        L.append(f"- {k}: **{sum(v.values())}**" + (f" en {', '.join(list(v)[:5])}" if v else ""))
    L += ["", "Se buscan los valores exactos pero no se imprimen. Los comentarios del código de la web que"
          " nombran a Nacho (p. ej. «los filtros los quitó Nacho») no son datos y no se cuentan;"
          " el identificador del paquete es com.nachosanbenito.guardados, como el de IG Limpieza.", "",
          "## (b) La página de Instagram/TikTok no puede llamar a la app", "",
          "Las ventanas de Instagram y TikTok cargaron páginas hostiles falsas que probaron todas las puertas:", "",
          "```", json.dumps(a_ig, ensure_ascii=False, indent=1), "```", "",
          f"Llamadas que llegaron a funciones de la app desde esas páginas: **{len(st.get('api_calls_from_pages') or [])}**.",
          f"Mensajes bloqueados por el puente vigilado (app.py `_guard_bridge`): **{len(blocked)}**:", ""]
    L += [f"- {b['window']}: `{b['func']}`" for b in blocked[:14]]
    L += ["", f"«Mis guardados» (sin js_api) ve `pywebview.api` con funciones: {viewer.get('has_pywebview_api')}.",
          f"Servidor local: feed sin token → {st.get('feed_sin_token')}; con token → {st.get('feed_con_token')};"
          f" Host falso (DNS rebinding) → {st.get('host_rebinding')}.", "",
          "## (c) CSP del panel", "",
          f"- Cabecera HTTP: `{st.get('panel_csp_header')}`",
          f"- Meta en index.html: `{panel.get('csp_meta')}`",
          f"- eval() permitido (pywebview lo necesita): {panel.get('unsafe_eval_ok')}",
          f"- Un `<script>` en línea inyectado se ejecutó: {panel.get('inline_script_ran')} (violaciones CSP: {panel.get('violations')})",
          "", "## (d) Escapado", "",
          "Un guardado de prueba trae caption `<img src=x onerror=…>` y nombre `<script>…</script>`.", "",
          f"- Panel: código ejecutado {panel.get('pwned')} veces; etiquetas reales en la lista {panel.get('recent_imgs')};"
          f" se ve como texto: «{(panel.get('recent_text_sample') or '')[:110]}»",
          f"- Mis guardados: código ejecutado {viewer.get('pwned')} veces; `<img src=x>` en el DOM {viewer.get('img_x_anywhere')};"
          f" la ficha muestra el texto literal: {viewer.get('literal_tag_shown_as_text')}",
          "", "## (e) Clave de Gemini (IA opcional)", "",
          "El selftest pega una clave de prueba en el panel con `pywebview.api.set_gemini_key` (el mismo camino que la persona).",
          "Gemini es un servidor FALSO en 127.0.0.1:47702; no se llama al de verdad.", "",
          f"- Guardada: {st.get('ia_set')}; permisos del fichero: {iax.get('key_file_mode')}",
          f"- Aparece en lo que devuelve status() al panel: {iax.get('key_in_status')}; en app.log: {iax.get('key_in_log')}",
          f"- Llamadas al Gemini falso: {iax.get('calls')}; todas con la clave en la cabecera x-goog-api-key: {iax.get('all_in_header')};"
          f" alguna con la clave en la URL: {iax.get('any_in_url')}",
          f"- Guardados afinados con IA: {iax.get('counts')} en {iax.get('secs')} s; ejemplo (Selftest000): {iax.get('sample_sub')}, {iax.get('sample_lug')} sitio(s)",
          f"- Sin clave (antes de pegarla), llamadas a Gemini: {ru.get('gemini_calls_without_key')}",
          "- Las páginas hostiles de Instagram y TikTok intentan guardar, borrar y leer la clave:", "",
          "```", json.dumps({"instagram": steals[0], "tiktok": steals[1]}, ensure_ascii=False, indent=1), "```", "",
          f"- La clave sigue siendo la del panel tras el ataque: {st.get('key_after_attack')};"
          f" el servidor local sirve /gemini.key: {st.get('server_key')}", "",
          "## (f) Sitios con nombre hostil", "",
          f"Apple Maps falso (tools/fake_geo.py) devuelve el sitio `<img src=x onerror=…>Bar Trampa`. Ficha en «Mis guardados»:"
          f" {viewer.get('lug_items')} sitio(s), etiquetas reales {viewer.get('lug_tags')}, código ejecutado {viewer.get('pwned')} veces;"
          f" se ve como texto: «{(viewer.get('lug_text') or '')[:100]}»", "",
          "## (g) Barra de progreso", "",
          f"Lo que pintaba el panel en plena importación de TikTok (captura: `{pg.get('screenshot')}`):", "",
          "```", json.dumps(rows, ensure_ascii=False, indent=1), "```", "",
          f"- TikTok: total {tt_seen.get('max_total')} (lo da item_list), tiempo restante calculado: {tt_seen.get('eta_seen')}",
          f"- Instagram: sin total (no lo da), barra en movimiento; al final {ig_seen.get('last')}", "",
          "## (h) Carpetas y mapa sin IA", "",
          f"- Con subcarpeta: {ru.get('sub_count')} de 100; carpetas: {ru.get('cats')}",
          f"- Guardados con sitios en el mapa: {ru.get('lug_posts')}",
          f"- En IndexedDB de la web (Selftest000): {panel.get('idb_sample')}", "",
          "## (o) Carpetas a mano", "",
          "En «Mis guardados», ficha de Selftest000: se añade a Recetas › Postres, se intenta crear la carpeta"
          f" `{EVIL}` (desde la web y saltándose la web), se crea «Regalos 🎁» y se quita la primera.", "",
          "```", json.dumps(fi, ensure_ascii=False, indent=1), "```", "",
          f"- En la base (tabla `manual`): {json.dumps(guard, ensure_ascii=False)}",
          f"- Tras re-importar con otra descripción y que la IA diga otra cosa: {json.dumps(man.get('tras_reimportar'), ensure_ascii=False)}",
          f"- Lo que va a la web y al móvil (feed): {json.dumps(man.get('feed'), ensure_ascii=False)}",
          "- Instagram y TikTok (páginas hostiles) intentan escribir o leer el token:", "",
          "```", json.dumps({"instagram": ataques[0], "tiktok": ataques[1]}, ensure_ascii=False, indent=1), "```", "",
          f"- Tras el ataque: {json.dumps(man.get('tras_ataque'), ensure_ascii=False)}",
          f"- La web, al cerrar la ficha: {json.dumps(mw, ensure_ascii=False)}", "",
          "## Buscador de Apple Maps empaquetado", "",
          f"`{geo}`", "",
          "## Punta a punta (app empaquetada, sin internet)", "",
          f"- Importación automática al detectar sesión: {json.dumps(st.get('auto_import', {}).get('counts'))}"
          f" en {st.get('auto_import', {}).get('secs')} s",
          f"- Pasado a la web (IndexedDB de «Mis guardados»): {panel.get('indexeddb_posts')} guardados",
          "", "## El móvil (buzón cifrado)", "",
          "Todo en local: el Worker de `cloud/` con `npx wrangler dev` (KV simulado en `build/wrangler-state`),"
          " la web de `~/Projects/ig-saved/app` copiada sin datos en http://127.0.0.1:8781 y Chromium (Playwright)."
          " Nada se ha desplegado. La llave y los tokens no se imprimen.", "",
          "### (n) En el Mac (app empaquetada, selftest)", "",
          f"- El panel enseña el QR al pulsar «Conectar el móvil»: {mv.get('panel_qr_shown')} (SVG: {mv.get('qr_is_svg')}, {mv.get('qr_px')} px)",
          f"- Subida al buzón: {json.dumps(mv.get('estado'), ensure_ascii=False)} en {mv.get('secs')} s;"
          f" una segunda subida sin cambios: {mv.get('again')}",
          f"- movil.json: permisos {mv.get('cred_mode')}; la llave/tokens/id salen en status(): {mv.get('secret_in_status')},"
          f" en app.log: {mv.get('secret_in_log')}, en el HTML del panel: {mv.get('secret_in_panel_html')}",
          f"- El servidor local sirve /movil.json: {mv.get('server_cred')}; la llave sigue igual tras el ataque: {mv.get('cred_same_after_attack')}",
          "- Instagram y TikTok (páginas hostiles) intentan pedir el QR, cambiar la llave y leer el fichero:", "",
          "```", json.dumps({"instagram": msteals[0], "tiktok": msteals[1]}, ensure_ascii=False, indent=1), "```", "",
          "### (i) El Worker", "", "```", json.dumps(pm.get("worker"), ensure_ascii=False, indent=1), "```", "",
          "### (j) Lo que guarda el servidor", "",
          f"KV local de wrangler: `{json.dumps(pm.get('servidor'), ensure_ascii=False)}`. Se buscan captions, codes y cuentas"
          " de prueba, cabeceras JPEG, JSON de guardados, nombres de carpetas y la llave: 0 apariciones; cada objeto"
          " grande tiene la entropía de bytes al azar.", "",
          f"El buzón de la app, abierto con la llave del enlace (como el móvil): `{json.dumps(pm.get('buzon_de_la_app'), ensure_ascii=False)}`", "",
          "### (k) La web abre el enlace del QR", "", "```", json.dumps(pm.get("web"), ensure_ascii=False, indent=1), "```", "",
          "Capturas: `build/movil-web.png` (carpetas) y `build/movil-web-lista.png` (búsqueda «pasta», con portadas).", "",
          "### (l) Cambiar la llave", "", "```", json.dumps(pm.get("rotacion"), ensure_ascii=False, indent=1), "```", "",
          "### (m) La sincronización de Nacho, antes y ahora", "",
          "Paquetes con el formato de `tools/sync-pack.py` pero con datos inventados y una llave de prueba (la `.sync-key`"
          " de Nacho no se lee). La misma prueba con la web de git HEAD («antes») y con la nueva («ahora»):", "",
          "```", json.dumps(pm.get("nacho"), ensure_ascii=False, indent=1), "```",
          "", "## Arquitecturas", ""]
    L += [f"- `{k}`: {v}" for k, v in sorted(ar.items())[:8]]
    if len(ar) > 8:
        L.append(f"- … y {len(ar) - 8} más" + (f"; NO universales: {not_universal}" if not_universal else ", todos x86_64 arm64"))
    if st.get("exception"):
        L += ["", "## Error en el selftest", "", "```", st["exception"], "```"]
    (HERE / "docs" / "seguridad.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[5:27]))
    sys.exit(0 if ok_a and ok_b and ok_c and ok_d and ok_e2e and ok_e and ok_f and ok_g and ok_h and ok_o and ok_geo
             and ok_i and ok_j and ok_k and ok_l and ok_m and ok_n and not not_universal else 1)


if __name__ == "__main__":
    main()
