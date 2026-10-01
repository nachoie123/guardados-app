"""Después de importar: el mapa (sin IA) y, si hay clave, la pasada de IA.

pasada_geo: lee la descripción de cada guardado nuevo (sitios.candidatos) y busca
            esos nombres en Apple Maps. Solo marca el guardado como "mirado" si Apple
            contestó: sin red, se reintenta en la próxima importación.
pasada_ia:  con la clave de Gemini de la persona, rehace carpetas/subcarpetas
            (como ig-saved/carpetas.py) y, en los de Sitios, investiga los sitios
            (como ig-saved/sitios.py: texto + portada) y los coloca con Apple Maps.
"""
import logging
from collections import defaultdict
from pathlib import Path

import ia
import sitios

log = logging.getLogger("guardados")
LOTE_GEO = 25


class SinMapa(Exception):
    pass


def _dedup(ls):
    out = []
    for g in ls:
        if g and not any(sitios.km(g, o) < 0.05 and sitios.parecido(g["n"], o["n"]) for o in out):
            out.append(g)
    return out


def pasada_geo(db, prog, should_stop=lambda: False):
    if not sitios.geo_bin():
        return {"skipped": "sin buscador de Apple Maps"}
    todo = db.pending_geo()
    if not todo:
        return {"posts": 0, "sitios": 0}
    prog.start("geo", len(todo), 0, "guardados")
    cache = db.geo_cache()
    found = hechos = 0
    for i in range(0, len(todo), LOTE_GEO):
        if should_stop():
            prog.finish("geo", "stop", "Parado")
            break
        chunk = todo[i:i + LOTE_GEO]
        cands = [(code, x) for code, cap, *_ in chunk for x in sitios.candidatos(cap)]
        antes = set(cache)
        try:
            res = sitios.localizar([x for _, x in cands], cache=cache) if cands else []
        except sitios.SinRespuesta:
            prog.finish("geo", "error", "Apple Maps no contesta (¿sin internet?). Se reintentará.")
            raise SinMapa("Apple Maps no contesta")
        db.put_geo_cache({k: v for k, v in cache.items() if k not in antes})
        por = defaultdict(list)
        for (code, _), g in zip(cands, res):
            if g:
                por[code].append(g)
        for code, *_ in chunk:
            ls = _dedup(por.get(code, []))
            db.set_lug(code, ls)
            found += len(ls)
        hechos += len(chunk)
        prog.update("geo", done=hechos, msg=f"{found} sitios en el mapa")
    else:
        prog.finish("geo", "ok", f"{found} sitios en el mapa")
    return {"posts": hechos, "sitios": found}


def pasada_ia(db, clave, prog, media_dir: Path, should_stop=lambda: False, sleep=None):
    key = clave.get()
    if not key:
        return {"skipped": "sin clave"}
    kw = {"sleep": sleep} if sleep else {}
    todo = db.pending_ia()
    if not todo:
        return {"posts": 0}
    prog.start("ia", len(todo), 0, "guardados")
    cache = db.geo_cache()
    hechos = lugares = 0
    try:
        for i in range(0, len(todo), ia.LOTE):
            if should_stop():
                prog.finish("ia", "stop", "Parado")
                return {"posts": hechos, "stopped": True}
            lote = todo[i:i + ia.LOTE]
            res = ia.clasificar(key, lote, **kw)
            for code, cap, tr, user in lote:
                if code not in res:
                    continue   # sin respuesta para este: se reintenta la próxima vez
                rutas, ci = res[code]
                if any(r.startswith("sitios/") for r in rutas):
                    ls = ia.lugares(key, cap, tr, user, media_dir / f"{code}.jpg", **kw)
                    antes = set(cache)
                    try:
                        geo = sitios.localizar(ls, cache=cache) if ls else []
                    except sitios.SinRespuesta:
                        geo = []
                    db.put_geo_cache({k: v for k, v in cache.items() if k not in antes})
                    lug = _dedup([g for g in geo if g])
                    lugares += len(lug)
                    db.set_lug(code, lug, ia=True, rutas=rutas, ciudad=ci)
                else:
                    db.set_rutas_ia(code, rutas, ci)
                hechos += 1
            prog.update("ia", done=min(i + ia.LOTE, len(todo)), msg=f"{lugares} sitios con IA")
    except ia.ClaveMala as e:
        prog.finish("ia", "error", str(e))
        raise
    except Exception as e:
        prog.finish("ia", "error", f"Gemini: {type(e).__name__}")
        raise
    prog.finish("ia", "ok", f"{hechos} reordenados, {lugares} sitios")
    return {"posts": hechos, "sitios": lugares}
