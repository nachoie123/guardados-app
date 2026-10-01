#!/usr/bin/env python3
"""Trae de ~/Projects/ig-saved lo que la app reutiliza, SIN datos de nadie:

- app/ (la web de guardados) -> web/guardados/   solo código, iconos y vendor
- rules.py                   -> vendor/rules.py  títulos y categorías sin IA

Lista blanca a propósito: data/, covers/, sync/, fotos/ y demo/ (la muestra de
Nacho) se quedan fuera. Se ejecuta antes de cada build (build.sh).
"""
import shutil
from pathlib import Path

SRC = Path.home() / "Projects" / "ig-saved"
HERE = Path(__file__).resolve().parent.parent
FILES = ["index.html", "app.css", "app.js", "search.js", "horario.js", "rules.js", "store.js", "buzon-config.js",
         "rules-data.json", "manifest.webmanifest", "sw.js", "bookmarklet.js", "bookmarklet-tiktok.js"]
DIRS = ["icons", "vendor"]


def main():
    if not SRC.exists():   # fuera del Mac de Nacho (repo público): web/guardados y vendor/ ya vienen copiados
        print("sin ~/Projects/ig-saved: uso web/guardados y vendor/rules.py tal cual")
        return
    dst = HERE / "web" / "guardados"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in FILES:
        shutil.copy2(SRC / "app" / f, dst / f)
    for d in DIRS:
        shutil.copytree(SRC / "app" / d, dst / d)
    (HERE / "vendor").mkdir(exist_ok=True)
    shutil.copy2(SRC / "rules.py", HERE / "vendor" / "rules.py")
    n = sum(1 for _ in dst.rglob("*") if _.is_file())
    print(f"web/guardados: {n} ficheros · vendor/rules.py copiado")


if __name__ == "__main__":
    main()
