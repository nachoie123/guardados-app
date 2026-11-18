#!/usr/bin/env python3
"""Fixtures de paridad para GuardadosKit (Swift): lo que dice Python sobre la base real del autor.

Lee ~/Projects/ig-saved/saved.db en solo lectura y escribe en ~/Projects/ig-saved/paridad-swift/
(fuera de apple/: son datos personales y no van al repo).

  .venv/bin/python -B tools/paridad_swift.py
  .venv/bin/python -B tools/paridad_swift.py --red   # sitios-red.json: 30 sitios con Apple Maps de verdad
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import carpetas  # noqa: E402
import rules  # noqa: E402  (vendor/rules.py, lo mete carpetas en sys.path)
import sitios  # noqa: E402

DB = Path.home() / "Projects" / "ig-saved" / "saved.db"
SALIDA = Path.home() / "Projects" / "ig-saved" / "paridad-swift"


def escribir(nombre, filas):
    (SALIDA / nombre).write_text(json.dumps(filas, ensure_ascii=False, separators=(",", ":")) + "\n",
                                 encoding="utf-8")


def main():
    if "--red" in sys.argv:
        return red()
    SALIDA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    titulos = []
    for code, cap, tr, u, db_t, db_cat in db.execute(
            "SELECT code, caption, text, username, title, category FROM posts LEFT JOIN transcripts USING(code)"):
        cap, tr, u = cap or "", tr or "", u or ""
        t, cat = rules.rule_title(cap, tr, u, "")[:2]
        titulos.append({"code": code, "cap": cap, "tr": tr, "u": u, "t": t, "cat": cat,
                        "db_t": db_t, "db_cat": db_cat})
    escribir("titulos.json", titulos)

    # un registro por code (hay codes repetidos en varias colecciones)
    por_code = db.execute(
        "SELECT code, MAX(caption), MAX(username), MAX(fullname), MAX(title), MAX(text) "
        "FROM posts LEFT JOIN transcripts USING(code) GROUP BY code ORDER BY code").fetchall()
    folders = dict(db.execute("SELECT code, rutas FROM post_folders"))

    filas_carpetas, docs = [], []
    for code, cap, u, n, t, tr in por_code:
        cap, u, n, t, tr = cap or "", u or "", n or "", t or "", tr or ""
        hs = bool(sitios.candidatos(cap))
        rutas, ciudad = carpetas.rutas(cap, tr, u, n, hay_sitio=hs)
        filas_carpetas.append({"code": code, "cap": cap, "tr": tr, "u": u, "n": n, "hs": hs,
                               "rutas": rutas, "ciudad": ciudad})
        raices = []
        for r in json.loads(folders[code]) if folders.get(code) else []:
            raiz = r.split("/")[0]
            if raiz not in raices:
                raices.append(raiz)
        docs.append({"id": code, "t": t, "c": cap, "u": u, "n": n, "tr": tr, "cat": raices or ["otros"]})
    escribir("carpetas.json", filas_carpetas)
    escribir("busqueda-docs.json", docs)

    caps = {code: cap or "" for code, cap, *_ in por_code}
    codes = [c for (c,) in db.execute(
        "SELECT DISTINCT code FROM post_places WHERE idx >= 0 AND lat IS NOT NULL ORDER BY code")]
    candidatos = []
    for code in codes:
        cands = [{"n": c["n"], "ci": c["ci"], "dir": c["dir"], "src": c["src"], "solo_dir": bool(c.get("solo_dir"))}
                 for c in sitios.candidatos(caps.get(code, ""))]
        candidatos.append({"code": code, "cap": caps.get(code, ""), "cands": cands})
    escribir("candidatos.json", candidatos)

    con_nombre = sum(1 for f in candidatos if f["cands"])
    nombres = sum(len(f["cands"]) for f in candidatos)
    print(f"titulos {len(titulos)} · carpetas {len(filas_carpetas)} · candidatos {len(candidatos)} "
          f"({con_nombre} con nombre, {nombres} nombres) · busqueda-docs {len(docs)}")


def red():
    """30 candidatos (barajados con semilla 11) que Python + Apple Maps (build/geo) sí colocan."""
    filas = json.loads((SALIDA / "candidatos.json").read_text(encoding="utf-8"))
    todos = [(f["code"], c) for f in filas for c in f["cands"]]
    random.Random(11).shuffle(todos)
    cache, out, mirados, caidas = {}, [], 0, 0
    for code, cand in todos:
        if len(out) == 30:
            break
        mirados += 1
        try:
            g = sitios.localizar([dict(cand)], cache=cache)[0]
        except sitios.SinRespuesta:
            caidas += 1
            continue
        if g:
            out.append({"code": code, "cand": cand,
                        "py": {k: g.get(k) for k in ("n", "t", "ci", "lat", "lng", "a")} | {"aprox": bool(g.get("aprox"))}})
    escribir("sitios-red.json", out)
    print(f"sitios-red {len(out)} (mirados {mirados} de {len(todos)}, sin respuesta {caidas})")


if __name__ == "__main__":
    main()
