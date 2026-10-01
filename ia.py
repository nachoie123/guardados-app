"""IA OPCIONAL: si la persona pega SU clave de Gemini, las carpetas y el mapa se
afinan como en ~/Projects/ig-saved (carpetas.py y sitios.py). Sin clave, todo
sigue con reglas (carpetas.py / sitios.py de esta app) y no se llama a nadie.

La clave es como la llave de casa de la persona:
- se guarda SOLO en su Mac: ~/Library/Application Support/Guardados/gemini.key,
  permisos 600, en una carpeta 700. Nunca en el .app, nunca en app.log.
  (No en el Llavero: el .app va firmado ad hoc y cada versión nueva pediría
  permiso para leerla; un fichero 600 en su carpeta no.)
- viaja en la cabecera x-goog-api-key, nunca en la URL (las URL acaban en logs).
- solo el panel puede pedir guardarla o borrarla; nadie puede leerla de vuelta:
  status() dice "hay clave", nunca cuál.
"""
import base64
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi

import carpetas
import sitios

MODELO_CARPETAS = "gemini-3.1-flash-lite"   # los de ig.py (GEMINI_CASCADA)
MODELO_SITIOS = "gemini-3.8-flash"
URL_REAL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{20,120}$")
LOTE = 20


def url_base():
    """La de Google. Solo las pruebas (servidor falso en 127.0.0.1) pueden cambiarla."""
    u = os.environ.get("GUARDADOS_GEMINI_URL", "")
    if u.startswith("http://127.0.0.1:") and "{m}" in u:
        return u
    return URL_REAL


class Clave:
    def __init__(self, folder: Path):
        self.f = Path(folder) / "gemini.key"

    def has(self):
        return self.f.is_file() and self.f.stat().st_size > 0

    def get(self):
        try:
            k = self.f.read_text().strip()
        except OSError:
            return None
        return k if KEY_RE.match(k) else None

    def set(self, k):
        k = (k or "").strip()
        if not KEY_RE.match(k):
            raise ValueError("Eso no parece una clave de Gemini (letras, números, - y _; empieza por AIza…).")
        tmp = self.f.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(k)
        os.chmod(tmp, 0o600)
        tmp.replace(self.f)
        os.chmod(self.f, 0o600)

    def delete(self):
        try:
            self.f.unlink()
        except FileNotFoundError:
            pass


class SinClave(Exception):
    pass


class ClaveMala(Exception):
    pass


def _ctx():
    return ssl.create_default_context(cafile=certifi.where())


def pedir(key, modelo, parts, max_tokens=4000, sleep=time.sleep):
    """Una llamada a Gemini -> texto. Reintenta 429/5xx. 400/401/403 -> ClaveMala (sin reintentar)."""
    body = json.dumps({"contents": [{"parts": parts}],
                       "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens,
                                            "responseMimeType": "application/json"}}).encode()
    url = url_base().format(m=modelo)
    ultimo = ""
    for espera in (0, 5, 20, 60):
        if espera:
            sleep(espera)
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                              "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=120, context=None if url.startswith("http:") else _ctx()) as r:
                d = json.loads(r.read())
            cand = (d.get("candidates") or [{}])[0]
            return "".join(p.get("text", "") for p in ((cand.get("content") or {}).get("parts") or [])
                           if isinstance(p, dict) and not p.get("thought"))
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
            if e.code in (400, 401, 403):
                raise ClaveMala(f"Gemini rechaza la clave ({ultimo}). Revisa que esté bien copiada.")
            if e.code not in (429, 500, 502, 503):
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo = type(e).__name__
    raise RuntimeError(f"Gemini no responde ({ultimo})")


# ---------------------------------------------------------------- carpetas (como ig-saved/carpetas.py)
DESC = {
    "sitios/asiatico": "restaurante asiatico", "sitios/italiano": "restaurante italiano, pizza",
    "sitios/hamburguesas": "hamburguesas, bocadillos, comida rapida", "sitios/espanola": "cocina espanola, tapas",
    "sitios/restaurantes": "otros restaurantes", "sitios/bares": "bares, copas, discotecas",
    "sitios/cafes": "cafeterias, pastelerias, heladerias", "sitios/planes": "ocio, actividades, mercados",
    "sitios/naturaleza": "playas, rutas, miradores", "recetas/saludables": "proteicas, fit",
    "pelis_series/accion": "accion, thriller, crimen", "pelis_series/scifi": "ciencia ficcion, fantasia, superheroes",
    "pelis_series/recomendaciones": "listas de que ver", "anime/edits": "edits, AMV",
    "tecnologia/ia": "herramientas de IA", "tecnologia/ia_noticias": "noticias y modelos de IA",
    "tecnologia/asistentes": "trucos de ChatGPT, Claude, Gemini", "tecnologia/automatizaciones": "n8n, bots, flujos",
    "finanzas/dinero": "ahorro, sueldos", "carrera/practicas": "practicas, CV, entrevistas",
    "carrera/estudio": "tecnicas de estudio", "moda/cuidado": "pelo, piel", "humor/memes": "memes",
    "humor/sketches": "sketches", "humor/clips": "clips graciosos de la vida real",
}
PROMPT_CARPETAS = """Ordena videos guardados de Instagram/TikTok en carpetas. Cada video va en
1 a 3 rutas de esta lista (la mas importante primero). Usa SOLO estas rutas, tal cual:

{lista}

Reglas:
- "sitios/..." SOLO si el video habla de uno o mas lugares CONCRETOS que se pueden visitar
  (un restaurante con nombre, "3 bares de Madrid", un hotel, un museo). Un restaurante
  NO es una receta. Si ensena a cocinar, es recetas.
- Si es sitios, "ciudad": la ciudad del sitio; si no se sabe, "".
- Un clip o escena de una peli/serie es pelis_series aunque sea gracioso.
- "otros" solo si de verdad no encaja nada.

Devuelve SOLO JSON: {{"<id>": {{"c": ["ruta", ...], "ciudad": ""}}, ...}} con los {n} ids.

{posts}"""


def _lista():
    out = []
    for c, ss in carpetas.SUB.items():
        out.append(", ".join(f"{c}/{s}" + (f" ({DESC[f'{c}/{s}']})" if f"{c}/{s}" in DESC else "") for s in ss))
    out.append(", ".join(carpetas.SUELTAS))
    return "\n".join(out)


def limpiar_rutas(rs):
    out = []
    for r in rs if isinstance(rs, list) else []:
        r = str(r).strip().lower().replace("diseno", "diseño")
        top = r.split("/")[0]
        if r not in carpetas.VALIDAS and top in carpetas.SUELTAS:
            r = top                                   # "humor/lo-que-sea" en una carpeta sin subcarpetas
        elif r not in carpetas.VALIDAS and top in carpetas.SUB:
            r = f"{top}/{carpetas.POR_DEFECTO[top]}"  # "recetas" a secas -> su subcarpeta más común
        if r in carpetas.VALIDAS and r not in out:
            out.append(r)
    return out[:3]


def clasificar(key, lote, sleep=time.sleep):
    """lote: [(code, caption, tr, user)] -> {code: (rutas, ciudad)}"""
    posts = "\n\n".join(f"=== id: {code}\nCuenta: @{u or ''}\nDescripcion: {(cap or '(nada)')[:500]}\n"
                        f"Transcripcion: {(tr or '(sin voz)')[:600]}" for code, cap, tr, u in lote)
    txt = pedir(key, MODELO_CARPETAS, [{"text": PROMPT_CARPETAS.format(lista=_lista(), n=len(lote), posts=posts)}],
                max_tokens=60 * len(lote) + 300, sleep=sleep)
    try:
        obj = json.loads(txt or "{}")
    except json.JSONDecodeError:
        return {}
    out = {}
    ids = {c for c, *_ in lote}
    for code, v in (obj.items() if isinstance(obj, dict) else []):
        if code in ids and isinstance(v, dict):
            rs = limpiar_rutas(v.get("c"))
            if rs:
                ci = str(v.get("ciudad") or "").strip()[:40] if any(r.startswith("sitios/") for r in rs) else ""
                out[code] = (rs, ci)
    return out


# ---------------------------------------------------------------- sitios (como ig-saved/sitios.py)
PROMPT_SITIOS = """Este es un video guardado de Instagram/TikTok. Saca TODOS los lugares concretos
que se pueden visitar y que aparecen en el (restaurantes, bares, cafeterias, hoteles,
museos, tiendas, playas, miradores...). Si el video recomienda 5 bares, son 5 lugares.

El nombre puede estar en la descripcion (a menudo tras 📍 o como @cuenta del local), en lo
que se dice o en la imagen (cartel, carta, fachada). Una @cuenta como @bar_centi es el bar
"Bar Centi". NO inventes: si no hay forma de saber que sitio es, lista vacia.

Devuelve SOLO JSON: {{"lugares": [{{"nombre": "...", "direccion": "", "ciudad": "...", "pais": "...",
"tipo": uno de {tipos}, "lat": latitud aproximada de la ciudad o zona, "lng": longitud aproximada}}]}}

Cuenta: @{u}
Descripcion: {cap}
Transcripcion: {tr}"""


def lugares(key, cap, tr, user, portada: Path = None, sleep=time.sleep):
    parts = [{"text": PROMPT_SITIOS.format(tipos=sitios.TIPOS, u=user or "", cap=(cap or "")[:1500], tr=(tr or "")[:2500])}]
    if portada and portada.is_file() and portada.stat().st_size < 3_000_000:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(portada.read_bytes()).decode()}})
    txt = pedir(key, MODELO_SITIOS, parts, max_tokens=8192, sleep=sleep)
    try:
        obj = json.loads(txt or "{}")
    except json.JSONDecodeError:
        return []
    ls = obj.get("lugares") if isinstance(obj, dict) else None
    out = []
    for l in ls if isinstance(ls, list) else []:
        if not isinstance(l, dict) or not str(l.get("nombre") or "").strip():
            continue
        lat, lng = sitios._num(l.get("lat")), sitios._num(l.get("lng"))
        out.append({"n": str(l["nombre"]).strip()[:80], "ci": str(l.get("ciudad") or "")[:40],
                    "dir": str(l.get("direccion") or "")[:120], "pais": str(l.get("pais") or "")[:40],
                    "t": l.get("tipo") if l.get("tipo") in sitios.TIPOS else "planes",
                    "centro": {"lat": lat, "lng": lng} if lat is not None and lng is not None
                    and -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng) else None})
    return out[:15]
