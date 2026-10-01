"""Sitios del mapa SIN IA: se sacan de la descripción y se buscan en Apple Maps.

Como quien lee un folleto con un rotulador: subraya lo que va tras 📍, las
@cuentas que parecen de un local ("📍 @bar_centifolia", "cenamos en @casa_lucio")
y frases tipo «Restaurante Casa Pepe». Luego le pregunta a Apple Maps
(tools/geo.swift, MKLocalSearch: gratis, sin cuenta y sin permiso de ubicación)
y solo se queda con lo que Apple encuentra con un nombre parecido.
Lo que solo se dice en voz o se ve en el vídeo no lo ve: para eso está la IA opcional (ia.py).

Formato de cada sitio (el campo `lug` que ya entiende la web, como export.py de ig-saved):
  {"n": nombre, "t": tipo, "ci": ciudad, "lat": .., "lng": .., "a": dirección, "aprox": 1 si no es exacto}
"""
import difflib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import carpetas

TIPOS = ["restaurantes", "bares", "cafes", "hoteles", "museos", "planes", "naturaleza", "tiendas"]
# categorías de Apple (MKPointOfInterestCategory) -> tipo del mapa
APPLE_TIPO = {
    "Restaurant": "restaurantes", "Bakery": "cafes", "Cafe": "cafes", "Brewery": "bares", "Winery": "bares",
    "Nightlife": "bares", "Hotel": "hoteles", "Museum": "museos", "Theater": "museos", "Library": "museos",
    "MovieTheater": "planes", "AmusementPark": "planes", "Aquarium": "planes", "Zoo": "planes",
    "Stadium": "planes", "FitnessCenter": "planes", "Marina": "naturaleza", "Beach": "naturaleza",
    "NationalPark": "naturaleza", "Park": "naturaleza", "Campground": "naturaleza", "Store": "tiendas",
    "FoodMarket": "tiendas", "Pharmacy": "tiendas", "Landmark": "museos", "CastleOrFortress": "museos",
    "MusicVenue": "planes", "Spa": "hoteles", "Hiking": "naturaleza", "Skiing": "naturaleza",
}
SUB_DE_TIPO = {"bares": "bares", "cafes": "cafes", "hoteles": "hoteles", "museos": "museos", "planes": "planes",
               "naturaleza": "naturaleza", "tiendas": "tiendas"}

# ---------------------------------------------------------------- sacar nombres
PIN = re.compile(r"[📍📌🏠🍽🍴]️?\s*:?\s*([^\n📍📌]{2,90})")
MENCION = re.compile(r"@([A-Za-z0-9_.]{3,30})")
LOCAL_EN_HANDLE = re.compile(
    r"(bar|rest|resto|cafe|coffee|caf[eé]|bistro|sushi|ramen|pizz|burger|taberna|tasca|asador|brasa|grill|"
    r"cantina|trattoria|osteria|hotel|hostel|museo|museum|bakery|panader|pasteler|helad|gelat|brunch|tapas|"
    r"cocina|kitchen|house|club|lounge|rooftop|terraza|mercado|market|shop|store|tienda|izakaya|yakiniku|"
    r"_mad$|madrid|_bcn$|tokyo|tokio|osaka|marbella|ibiza|oficial|official)", re.I)
CONTEXTO = re.compile(r"(?:\ben|\bat|\bin|\bvisit(?:a|ad|amos|é)?|\bfuimos a|\bprobamos|\bcomimos en|\bcenamos en|"
                      r"\breserva(?:r)? en|\b(?:restaurante|restaurant|bar|cafeter[ií]a|hotel|local)\b)\s*$", re.I)
TIPO_FRASE = re.compile(
    r"\b(Restaurante|Restaurant|Bar|Cafeter[ií]a|Caf[eé]|Hotel|Museo|Museum|Taberna|Asador|Pizzer[ií]a|"
    r"Hamburgueser[ií]a|Helader[ií]a|Pasteler[ií]a|Mercado|Tienda)\s+((?:[A-ZÁÉÍÓÚÑ0-9][\w'’&-]*|de|del|la|el|los|las|y|&)"
    r"(?:\s+(?:[A-ZÁÉÍÓÚÑ0-9][\w'’&-]*|de|del|la|el|los|las|y|&)){0,4})")
DIRECCION = re.compile(r"^\s*(c/|c\.|calle|avda|av\.|avenida|plaza|pza|paseo|carrer|ronda|camino|\d+[\s,-])", re.I)
CP = re.compile(r"\b\d{5}\b")
GENERICO = {"madrid", "barcelona", "spain", "españa", "japan", "tokyo", "tokio", "link in bio", "bio", "ubicación",
            "ubicacion", "location", "info", "más info", "mas info", "dirección", "direccion", "restaurante", "bar",
            "hotel", "aqui", "aquí", "here", "centro", "el centro", "precio", "menu", "menú"}


def _limpia_nombre(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"[#][\w]+", "", s)
    s = re.split(r"\s+[|–—]\s+|\s+-\s+|[•·]|\s{2,}|[!?¡¿]|https?://|\.\s", s)[0]
    s = s.strip(" .,:;\"'“”«»*-–—")
    return s[:60]


_SUFIJOS = re.compile(r"(?:[._]?(?:madrid|barcelona|tokyo|tokio|oficial|official|spain|espana|marbella|ibiza|"
                      r"valencia|sevilla|london|paris|group|grupo)|[._](?:mad|bcn|es|eu|dg|nyc))+$", re.I)


def _handle_a_nombre(h):
    h = h.strip("._")
    h2 = _SUFIJOS.sub("", h).strip("._")
    h = h2 if len(h2) >= 3 else h
    partes = [p for p in re.split(r"[._]+", h) if p]
    return " ".join(p if p.isupper() else p.capitalize() for p in partes)


def candidatos(caption):
    """Nombres de sitios que se pueden sacar de la descripción, sin IA: [{"n", "ci", "dir"}]."""
    cap = caption or ""
    if not cap.strip():
        return []
    ci = carpetas.ciudad(cap)
    out, vistos = [], set()

    def add(n, d="", fuente=""):
        n = _limpia_nombre(n)
        k = plano(n).strip()
        if len(k) < 3 or k in GENERICO or k in vistos or len(n.split()) > 7:
            return
        if carpetas._CIU_RE.fullmatch(n):
            return
        vistos.add(k)
        out.append({"n": n, "ci": ci, "dir": d, "src": fuente})

    for m in PIN.finditer(cap):
        txt = m.group(1).strip()
        men = MENCION.findall(txt)
        if men:
            for h in men:
                add(_handle_a_nombre(h), fuente="pin@")
            continue
        if DIRECCION.match(txt) or CP.search(txt):
            # 📍 con una dirección: el nombre suele ir entre comillas o en la frase de antes
            q = re.findall(r"[\"“«]([^\"”»]{2,40})[\"”»]", cap)
            if q:
                add(q[0], txt, "pin-dir")
            elif out and not out[-1]["dir"]:
                out[-1]["dir"] = txt[:90]
            else:
                # solo la dirección: un pin en esa calle (se busca la dirección, no un nombre)
                d = _limpia_nombre(txt)
                if len(d) >= 6 and plano(d).strip() not in vistos:
                    vistos.add(plano(d).strip())
                    out.append({"n": d, "ci": ci, "dir": d, "src": "dir", "solo_dir": True})
            continue
        # "📍Yakiniku Jambo Hanare" / "📍 Madrid": la primera parte, sin la ciudad del final
        nombre = re.split(r",", txt)[0]
        resto = txt[len(nombre):]
        if carpetas._CIU_RE.fullmatch(nombre.strip()):
            continue
        add(nombre, resto.strip(" ,") if re.search(r"\d", resto) else "", "pin")
    # si la descripción habla de comer/salir, cualquier @cuenta puede ser el local (Apple Maps filtra luego)
    de_sitios = carpetas._cuenta(carpetas.rules._blob([cap]), carpetas.EXTRA["sitios"]) >= 2 or bool(PIN.search(cap))
    for m in MENCION.finditer(cap):
        h = m.group(1)
        antes = cap[max(0, m.start() - 25):m.start()]
        if re.search(r"[📍📌]\s*$", antes):
            continue  # ya lo cogió el 📍
        if CONTEXTO.search(antes) or LOCAL_EN_HANDLE.search(h) or de_sitios:
            add(_handle_a_nombre(h), fuente="@")
    for m in TIPO_FRASE.finditer(cap):
        nombre = m.group(2).strip()
        if nombre.split()[0].lower() in ("de", "del", "la", "el", "los", "las", "y"):
            continue
        add(f"{m.group(1)} {nombre}" if len(nombre.split()) == 1 and len(nombre) < 5 else nombre, fuente="frase")
    return out[:12]


# ---------------------------------------------------------------- comparar
def plano(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", s)


_VACIAS = {"restaurante", "restaurant", "bar", "cafe", "hotel", "the", "el", "la", "de", "del", "madrid", "tokyo",
           "tokio", "oficial", "official", "and", "y", "los", "las"}


def parecido(a, b):
    a, b = " ".join(plano(a).split()), " ".join(plano(b).split())
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    if difflib.SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio() >= 0.75:
        return True
    wa, wb = set(a.split()) - _VACIAS, set(b.split()) - _VACIAS
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.6


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- Apple Maps
def geo_bin():
    """El buscador de Apple Maps ya compilado (universal2): dentro del .app o en build/."""
    if os.environ.get("GUARDADOS_GEO_BIN") and os.environ.get("GUARDADOS_SELFTEST"):  # solo en pruebas
        return os.environ["GUARDADOS_GEO_BIN"]
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for p in (base / "geo", base / "build" / "geo", Path(__file__).resolve().parent / "build" / "geo"):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


class SinRespuesta(Exception):
    """Apple Maps no contestó a nada (sin red o sin buscador): no se marca nada como mirado."""


def buscar(consultas, timeout_extra=0):
    """[{"id","q", "ciudad"?: bool, "cerca"?: [lat,lng]}] -> {id: respuesta}. Un proceso para todas
    (Apple limita a ~50 por minuto; geo.swift va a una cada 1,3 s y espera si le frenan)."""
    if not consultas:
        return {}
    b = geo_bin()
    if not b:
        raise SinRespuesta("sin buscador")
    try:
        p = subprocess.run([b], input=json.dumps(consultas), capture_output=True, text=True,
                           timeout=120 + 4 * len(consultas) + timeout_extra)
    except (subprocess.TimeoutExpired, OSError) as e:
        raise SinRespuesta(type(e).__name__)
    out = {}
    for line in p.stdout.splitlines():
        try:
            d = json.loads(line)
            out[str(d["id"])] = d
        except (ValueError, KeyError, TypeError):
            continue
    if not out or all(not d.get("ok") and not d.get("vacio") for d in out.values()):
        raise SinRespuesta("Apple Maps no contesta")
    return out


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def elegir(nombre, resp, centro=None):
    """El candidato de Apple que de verdad es ese sitio -> (cand, "exacto"|"aprox") o (None, None).
    Nunca uno que no se llame parecido (evita pinchar un barrio o la calle con ese nombre)."""
    for c in (resp or {}).get("c", [])[:5]:
        if not isinstance(c, dict):
            continue
        lat, lng = _num(c.get("lat")), _num(c.get("lng"))
        if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        if centro and km({"lat": lat, "lng": lng}, centro) > 40:
            continue
        if parecido(nombre, str(c.get("name") or "")) and (c.get("poi") or c.get("calle")):
            return dict(c, lat=lat, lng=lng), ("exacto" if c.get("calle") else "aprox")
    return None, None


def elegir_dir(resp, centro=None):
    """Solo había una dirección (📍 C/ Conde Peñalver 64): la primera respuesta que es una calle de esa ciudad."""
    for c in (resp or {}).get("c", [])[:1]:
        lat, lng = _num(c.get("lat")), _num(c.get("lng"))
        if lat is None or lng is None or not c.get("calle"):
            continue
        if centro and km({"lat": lat, "lng": lng}, centro) > 40:
            continue
        return dict(c, lat=lat, lng=lng, name=""), "exacto"
    return None, None


def localizar(cands, ciudad_de=lambda x: x.get("ci", ""), cache=None):
    """Cada candidato -> sitio en el formato `lug` o None. cache: dict consulta -> respuesta (se rellena)."""
    cache = {} if cache is None else cache
    ciudades = sorted({ciudad_de(x) for x in cands if ciudad_de(x) and not x.get("centro")})
    pedir = [{"id": f"ci:{c}", "q": c, "ciudad": True} for c in ciudades if f"ci:{c}" not in cache]
    cache.update(buscar(pedir))
    centro = {}
    for c in ciudades:
        r = cache.get(f"ci:{c}") or {}
        cs = r.get("c") or []
        if r.get("ok") and cs and _num(cs[0].get("lat")) is not None:
            centro[c] = {"lat": float(cs[0]["lat"]), "lng": float(cs[0]["lng"])}
    consultas = []
    for i, x in enumerate(cands):
        ci = ciudad_de(x)
        q = ", ".join(v for v in (x["n"], ci) if v)
        ce = x.get("centro") or centro.get(ci)   # la IA da la zona aproximada; si no, la ciudad
        x["_c"] = ce
        cerca = {"cerca": [ce["lat"], ce["lng"]]} if ce else {}
        key = f"q:{q}|{cerca.get('cerca')}"
        x["_k"] = key
        if key not in cache:
            consultas.append({"id": key, "q": q, **cerca})
    cache.update(buscar(consultas))
    out = []
    for x in cands:
        ci = ciudad_de(x)
        resp, ce = cache.get(x.pop("_k")), x.pop("_c", None)
        if x.get("solo_dir"):
            g, prec = elegir_dir(resp, ce)
        else:
            g, prec = elegir(x["n"], resp, ce)
        if not g:
            out.append(None)
            continue
        tipo = APPLE_TIPO.get(str(g.get("cat") or "").replace("MKPOICategory", ""), x.get("t") or "restaurantes")
        a = " ".join(v for v in (str(g.get("addr") or ""), str(g.get("city") or "")) if v)
        out.append({"n": str(g.get("name") or x["n"])[:80], "t": tipo if tipo in TIPOS else "planes",
                    "ci": (ci or str(g.get("city") or ""))[:40], "lat": round(g["lat"], 6), "lng": round(g["lng"], 6),
                    "a": a[:120], **({"aprox": 1} if prec != "exacto" else {})})
    return out


def sub_de_sitio(lug, rutas_actuales, blob):
    """Si hay sitios y el vídeo no estaba en Sitios: la subcarpeta según el tipo del primero."""
    t = lug[0]["t"] if lug else "restaurantes"
    if t == "restaurantes":
        s = carpetas.subcarpeta("sitios", blob).split("/")[1]
        s = s if s in carpetas.COMIDA else "restaurantes"
    else:
        s = SUB_DE_TIPO.get(t, "planes")
    return f"sitios/{s}"
