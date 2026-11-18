#!/usr/bin/env python3
"""Exporta las reglas de carpetas.py y rules.py a JSON para la app nativa (apple/GuardadosKit).

Una sola fuente: las listas siguen viviendo en Python; Swift lee lo que sale de aquí.

  .venv/bin/python -B tools/exportar_carpetas.py
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))
import carpetas  # noqa: E402  (mete vendor/ en sys.path, como siempre)
import rules  # noqa: E402
from casos_carpetas import CASOS, CASOS_NUEVOS  # noqa: E402

KIT = HERE / "apple" / "GuardadosKit"
RECURSOS = KIT / "Sources" / "GuardadosKit" / "Recursos"
FIXTURES = KIT / "Tests" / "GuardadosKitTests" / "Fixtures"


def escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main():
    c = carpetas
    terminos = [{"raw": list(t.raw), "toks": list(t.toks), "modo": t.modo, "duenos": d, "peso": p}
                for t, d, p in zip(c._TERMS, c._DUENOS, c._PESO_T)]
    datos = {
        "kw_orden": list(rules.KEYWORDS),
        "carpetas": c.CARPETAS,
        "sub": c.SUB,
        "por_defecto": c.POR_DEFECTO,
        "comida": c.COMIDA,
        "terminos": terminos,
        "vocab": sorted(c._VOCAB),
        "contexto": [[rx, [[lab, d] for lab, d in aj.items()]] for rx, aj in c.CONTEXTO],
        "cuenta": [[cat, pistas] for cat, pistas in c.CUENTA.items()],
        "peso": [[k, v] for k, v in c.PESO.items()],
        "tope": c.TOPE,
        "umbral": c.UMBRAL,
        "peso_sub_en_carpeta": c.PESO_SUB_EN_CARPETA,
        "peso_cuenta": c.PESO_CUENTA,
        "bono_sitio": c.BONO_SITIO,
        "sitio_fuerte": c.SITIO_FUERTE.pattern,
        "receta": c.RECETA.pattern,
        "ciudades": c.CIUDADES,
        "ciu_alias": c._CIU_ALIAS,
        "extra_sitios": c.EXTRA["sitios"],
        "nombres": c.NOMBRES,
        "reservadas": sorted(c.RESERVADAS),
        "max_nombre": c.MAX_NOMBRE,
        "max_rutas": c.MAX_RUTAS,
    }
    escribir(RECURSOS / "carpetas-data.json", datos)

    casos = [{"buenas": b, "cap": cap, "u": u, "tr": tr} for b, cap, u, tr in CASOS + CASOS_NUEVOS]
    escribir(FIXTURES / "casos-carpetas.json", casos)

    shutil.copyfile(HERE / "web" / "guardados" / "rules-data.json", RECURSOS / "rules-data.json")

    modos = [t["modo"] for t in terminos]
    print(f"carpetas-data.json: {len(terminos)} términos ({modos.count('exacta')} exacta, "
          f"{modos.count('principio')} principio, {modos.count('dentro')} dentro), "
          f"{len(datos['vocab'])} palabras, {len(datos['kw_orden'])} categorías · "
          f"casos-carpetas.json: {len(casos)} casos · rules-data.json copiado")


if __name__ == "__main__":
    main()
