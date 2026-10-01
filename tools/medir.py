#!/usr/bin/env python3
"""Mide las reglas SIN IA contra lo que Gemini le hizo a Nacho (~/Projects/ig-saved/saved.db,
abierta en solo lectura; no se copia nada a la app).

  python3 tools/medir.py carpetas [--todo] [--con-transcripcion]
  python3 tools/medir.py sitios [--geo] [--limite N]
  python3 tools/medir.py falsos            # pines de más en vídeos sin sitio (usa Apple Maps)

Partición honesta: las palabras clave se ajustaron mirando la mitad "dev" (crc32(code) par);
la cifra que cuenta es la de la mitad "test" (impar), que no se miró. --todo mide las dos.

Escenario por defecto = lo que tendrá una persona nueva en la app empaquetada:
descripción + @usuario + nombre; subtítulos solo en TikTok (Instagram no se transcribe
en la app). --con-transcripcion usa también la transcripción de Instagram.
"""
import json
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
DB = Path.home() / "Projects" / "ig-saved" / "saved.db"


def con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def filas(c, con_tr):
    tr = dict(c.execute("SELECT code, text FROM transcripts"))
    out = []
    for code, rutas, cap, user, full in c.execute(
            "SELECT f.code, f.rutas, MAX(p.caption), MAX(p.username), MAX(p.fullname) FROM post_folders f"
            " JOIN posts p USING(code) GROUP BY f.code"):
        t = tr.get(code, "") if (code.startswith("tt_") or con_tr) else ""
        out.append((code, json.loads(rutas), cap or "", t or "", user or "", full or ""))
    return out


def parte(code):
    return "dev" if zlib.crc32(code.encode()) % 2 == 0 else "test"


def medir_carpetas(todo=False, con_tr=False):
    import carpetas
    import sitios
    c = con()
    rows = filas(c, con_tr)
    for nombre in (["dev", "test"] if todo else ["test"]):
        sel = [r for r in rows if parte(r[0]) == nombre]
        n_top = n_sub = n_any = 0
        rec = Counter(); tot = Counter(); prec_ok = Counter(); prec_n = Counter()
        sub_ok = Counter(); sub_n = Counter()
        for code, g, cap, tr, user, full in sel:
            hay = bool(sitios.candidatos(cap))
            r, _ = carpetas.rutas(cap, tr, user, full, hay_sitio=hay)
            gtops = {x.split("/")[0] for x in g}
            mtops = [x.split("/")[0] for x in r]
            n_top += mtops[0] in gtops
            n_any += bool(set(mtops) & gtops)
            n_sub += r[0] in g
            for t in gtops:
                tot[t] += 1
                rec[t] += t in mtops
            for t in set(mtops):
                prec_n[t] += 1
                prec_ok[t] += t in gtops
            # subcarpeta: entre los que acertamos la carpeta, ¿la misma subcarpeta?
            for gr in g:
                if "/" in gr and gr.split("/")[0] in mtops:
                    sub_n[gr.split("/")[0]] += 1
                    mine = next(x for x in r if x.split("/")[0] == gr.split("/")[0])
                    sub_ok[gr.split("/")[0]] += mine == gr
        N = len(sel)
        print(f"\n== {nombre}: {N} vídeos ({'con' if con_tr else 'sin'} transcripción de Instagram) ==")
        print(f"carpeta principal igual que la de Nacho: {n_top / N:.0%} · alguna carpeta en común: {n_any / N:.0%}"
              f" · ruta principal exacta (carpeta+subcarpeta): {n_sub / N:.0%}")
        print(f"{'carpeta':14} {'vídeos':>6} {'encontrados':>11} {'acierto':>8} {'subcarpeta':>11}")
        for t, k in tot.most_common():
            pr = f"{prec_ok[t] / prec_n[t]:.0%}" if prec_n[t] else "-"
            sb = f"{sub_ok[t] / sub_n[t]:.0%}" if sub_n[t] else "-"
            print(f"{t:14} {k:6} {rec[t] / k:11.0%} {pr:>8} {sb:>11}")


def medir_sitios(geo=False, limite=None):
    """Cuántos sitios saca de la descripción frente a los de Nacho (post_places) y cuántos coinciden."""
    import sitios
    c = con()
    nacho = defaultdict(list)
    for code, nom, lat, lng in c.execute("SELECT code, nombre, lat, lng FROM post_places WHERE idx >= 0 AND lat IS NOT NULL"):
        nacho[code].append((nom, lat, lng))
    caps = {code: (cap or "", u or "") for code, cap, u in c.execute(
        "SELECT code, MAX(caption), MAX(username) FROM posts GROUP BY code")}
    con_sitio = sorted(nacho)
    sin_sitio = [k for k in caps if k not in nacho]
    if limite:
        con_sitio = con_sitio[:limite]
    tot_n = sum(len(nacho[k]) for k in con_sitio)
    sacados = match = videos_con = 0
    ejemplos = []
    cands = {}
    for k in con_sitio:
        cs = sitios.candidatos(caps[k][0])
        cands[k] = cs
        sacados += len(cs)
        videos_con += bool(cs)
        for nom, _, _ in nacho[k]:
            if any(sitios.parecido(nom, x["n"]) for x in cs):
                match += 1
        if len(ejemplos) < 8 and cs:
            ejemplos.append((k, [x["n"] for x in cs], [n for n, _, _ in nacho[k]]))
    falsos = sum(1 for k in sin_sitio if sitios.candidatos(caps[k][0]))
    print(f"Vídeos con sitios de Nacho: {len(con_sitio)} ({tot_n} sitios).")
    print(f"Las reglas sacan algo en {videos_con} de esos vídeos ({videos_con / len(con_sitio):.0%}); "
          f"{sacados} nombres; {match} de los {tot_n} sitios de Nacho coinciden por nombre ({match / tot_n:.0%}).")
    print(f"Falsas alarmas: en {falsos} de {len(sin_sitio)} vídeos SIN sitio para Nacho saca algún nombre "
          f"({falsos / len(sin_sitio):.1%}).")
    for e in ejemplos:
        print("  ", e)
    if geo:
        todos = [(k, x) for k in con_sitio for x in cands[k]]
        res = sitios.localizar([x for _, x in todos], ciudad_de=lambda x: x.get("ci", ""))
        ok = cerca = 0
        for (k, x), g in zip(todos, res):
            if not g:
                continue
            ok += 1
            if any(sitios.km(g, {"lat": la, "lng": lo}) < 0.5 for _, la, lo in nacho[k]):
                cerca += 1
        print(f"Apple Maps coloca {ok} de {len(todos)} nombres sacados; {cerca} caen a menos de 500 m de un sitio de "
              f"Nacho del mismo vídeo ({cerca / tot_n:.0%} de sus {tot_n} sitios).")


def medir_falsos():
    """Pines de más: vídeos SIN sitio para Nacho donde las reglas sacan nombres y Apple los confirma."""
    import sitios
    c = con()
    hay = {r[0] for r in c.execute("SELECT DISTINCT code FROM post_places WHERE idx >= 0 AND lat IS NOT NULL")}
    caps = [(code, cap or "") for code, cap in c.execute("SELECT code, MAX(caption) FROM posts GROUP BY code") if code not in hay]
    todos = [(k, x) for k, cap in caps for x in sitios.candidatos(cap)]
    res = sitios.localizar([x for _, x in todos])
    videos = {k for (k, _), g in zip(todos, res) if g}
    print(f"{len(caps)} vídeos sin sitio para Nacho; las reglas sacan {len(todos)} nombres en "
          f"{len({k for k, _ in todos})} vídeos; Apple confirma {sum(1 for g in res if g)} -> pines de más en "
          f"{len(videos)} vídeos ({len(videos) / len(caps):.1%}).")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "carpetas":
        medir_carpetas("--todo" in a, "--con-transcripcion" in a)
    elif a and a[0] == "falsos":
        medir_falsos()
    elif a and a[0] == "sitios":
        medir_sitios("--geo" in a, int(a[a.index("--limite") + 1]) if "--limite" in a else None)
    else:
        print(__doc__)
