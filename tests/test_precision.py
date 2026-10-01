"""¿Ordena bien carpetas.py sin IA? Contra tests/casos_carpetas.py (etiquetado a mano).

  .venv/bin/python tests/test_precision.py          # tabla por carpeta y subcarpeta
  .venv/bin/python -m unittest tests.test_precision # el suelo: falla si baja

Precisión de una carpeta: de los vídeos que mete ahí, cuántos van ahí de verdad.
Cobertura: de los que van ahí de verdad, cuántos encuentra. Cuenta la carpeta
principal (la primera ruta); en las subcarpetas, la ruta entera.
"""
import sys
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))
import carpetas  # noqa: E402
from casos_carpetas import CASOS, CASOS_NUEVOS  # noqa: E402

TODOS = CASOS + CASOS_NUEVOS


def medir(casos=TODOS, rutas=carpetas.rutas):
    top_ok = ruta_ok = 0
    m = {"top": (Counter(), Counter(), Counter()), "sub": (Counter(), Counter(), Counter())}  # ok, pred, gold
    fallos = []
    for gold, cap, user, tr in casos:
        buenas = gold.split("|")
        r = rutas(cap, tr, user)[0][0]
        g, gt, rt = buenas[0], {b.split("/")[0] for b in buenas}, r.split("/")[0]
        top_ok += rt in gt
        ruta_ok += r in buenas
        if r not in buenas:
            fallos.append((g, r, cap[:60]))
        for k, (gg, rr, bien) in {"top": (g.split("/")[0], rt, rt in gt),
                                  "sub": (g, r, r in buenas)}.items():
            ok, pred, gol = m[k]
            gol[gg] += 1
            pred[rr] += 1
            if bien:
                ok[rr] += 1
    n = len(casos)
    ok, pred, gol = m["top"]
    con = sum(v for c, v in pred.items() if c != "otros")
    out = {"n": n, "carpeta": top_ok / n, "ruta": ruta_ok / n, "fallos": fallos,
           # global: de lo que mete en alguna carpeta (no "otros"), cuánto acierta; y cuánto deja en "otros"
           "precision": sum(v for c, v in ok.items() if c != "otros") / con if con else 0,
           "cobertura": sum(min(ok[c], gol[c]) for c in gol if c != "otros") / max(1, sum(v for c, v in gol.items() if c != "otros"))}
    for k, (ok, pred, gol) in m.items():
        out[k] = {c: (ok[c] / pred[c] if pred[c] else None, min(ok[c], gol[c]) / gol[c] if gol[c] else None,
                      gol[c]) for c in set(gol) | set(pred)}
    return out


def tabla(res):
    pct = lambda x: "  -" if x is None else f"{x:4.0%}"  # noqa: E731
    print(f"{res['n']} casos · carpeta bien: {res['carpeta']:.0%} · carpeta+subcarpeta bien: {res['ruta']:.0%}"
          f" · precisión {res['precision']:.0%} · cobertura {res['cobertura']:.0%}")
    for k in ("top", "sub"):
        print(f"\n{'carpeta' if k == 'top' else 'subcarpeta':28} casos  precisión  cobertura")
        for c, (p, cov, g) in sorted(res[k].items(), key=lambda x: (-x[1][2], x[0])):
            print(f"{c:28} {g:5}  {pct(p):>9}  {pct(cov):>9}")


# El nivel medido tras la mejora (docs/diseno.md, «Ordenar sin IA»). Si un cambio lo baja, este test falla.
# Antes (01/10/2026): 88% carpeta y 85% carpeta+subcarpeta en estos 178 casos. Después: 98% y 97%.
SUELO_CARPETA = 0.98
SUELO_RUTA = 0.96


class TestPrecision(unittest.TestCase):
    def test_no_baja(self):
        r = medir()
        self.assertGreaterEqual(len(TODOS), 120)
        self.assertGreaterEqual(r["carpeta"], SUELO_CARPETA, r["fallos"])
        self.assertGreaterEqual(r["ruta"], SUELO_RUTA, r["fallos"])

    def test_rutas_validas(self):
        for _, cap, user, tr in TODOS:
            for x in carpetas.rutas(cap, tr, user)[0]:
                self.assertIn(x, carpetas.VALIDAS)


class TestMotor(unittest.TestCase):
    """Las piezas del motor nuevo, una a una."""
    def test_hashtag_troceado(self):
        self.assertEqual(carpetas._piezas("pastarecipe", carpetas._VOCAB)[1:], ["pasta", "recipe"])
        self.assertIn("recipe", carpetas._piezas("PastaRecipe", carpetas._VOCAB))
        self.assertEqual(carpetas._trocear("daily", carpetas._VOCAB), [])   # nada de "ai" dentro de "daily"

    def test_palabra_entera(self):
        # " gin" no es "ginger"; "etf" no es "netflix"; "care" no es "car"
        self.assertNotIn("sitios/bares", carpetas.puntos("ginger shots")[1])
        self.assertNotIn("finanzas", carpetas.puntos("nuevo en netflix")[0])
        self.assertNotIn("coches", carpetas.puntos("self care sunday")[0])

    def test_plural_y_acentos(self):
        self.assertEqual(carpetas._raiz("bares"), "bar")
        self.assertEqual(carpetas._raiz("restaurantes"), "restaurante")
        self.assertEqual(carpetas.rutas("RECETA DE TARTA DE QUESO", "", "")[0][0],
                         carpetas.rutas("receta de tarta de queso", "", "")[0][0])

    def test_contexto(self):
        self.assertEqual(carpetas.rutas("Cómo ganar pasta con tu side hustle", "", "")[0][0].split("/")[0], "finanzas")
        self.assertEqual(carpetas.rutas("Pasta carbonara receta", "", "")[0][0].split("/")[0], "recetas")
        self.assertEqual(carpetas.rutas("Pull ups on the bar", "", "")[0][0], "fitness_salud/entreno")

    def test_mismo_texto_mismo_resultado(self):
        for _, cap, user, tr in TODOS[:30]:
            self.assertEqual(carpetas.rutas(cap, tr, user), carpetas.rutas(cap, tr, user))

    @unittest.skipUnless((Path.home() / "Projects" / "ig-saved" / "saved.db").exists(), "sin ig-saved")
    def test_datos_reales_no_baja(self):
        """Contra las carpetas que Gemini le hizo a Nacho (solo lectura, mitad "test"): 71% -> 75%."""
        sys.path.insert(0, str(HERE / "tools"))
        import medir as md
        import sitios
        sel = [r for r in md.filas(md.con(), False) if md.parte(r[0]) == "test"]
        ok = sum(carpetas.rutas(c, t, u, f, hay_sitio=bool(sitios.candidatos(c)))[0][0].split("/")[0]
                 in {x.split("/")[0] for x in g} for _, g, c, t, u, f in sel)
        self.assertGreaterEqual(ok / len(sel), 0.74)


if __name__ == "__main__":
    tabla(medir(CASOS_NUEVOS))   # los que no se miraron al afinar
    print()
    res = medir()
    tabla(res)
    if "-v" in sys.argv:
        print("\nfallos (esperada -> sale):")
        for g, r, c in res["fallos"]:
            print(f"  {g:28} -> {r:28} {c}")
