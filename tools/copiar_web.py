#!/usr/bin/env python3
"""Trae de ~/Projects/ig-saved lo que la app reutiliza, SIN datos de nadie:

- app/ (la web de guardados) -> web/guardados/   solo código, iconos y vendor
- rules.py                   -> vendor/rules.py  títulos y categorías sin IA

Lista blanca a propósito: data/, covers/, sync/, fotos/ y demo/ (la muestra de
el autor) se quedan fuera. Se ejecuta antes de cada build (build.sh).
"""
import re
import shutil
from pathlib import Path

SRC = Path.home() / "Projects" / "ig-saved"
HERE = Path(__file__).resolve().parent.parent
FILES = ["index.html", "app.css", "app.js", "search.js", "horario.js", "rules.js", "store.js", "buzon-config.js",
         "rules-data.json", "manifest.webmanifest", "sw.js", "bookmarklet.js", "bookmarklet-tiktok.js"]
DIRS = ["icons", "vendor"]
# La web de origen es también la personal del autor: lo que lo nombra sale en neutro dentro de la app (regla: nada
# personal en lo publicado). Su nombre vive en tools/.nombre (fuera de git), como sus datos en tools/.personal.
_N = Path(__file__).with_name(".nombre")
N = re.escape(_N.read_text().strip()) if _N.exists() else None
NEUTRO = [(rf"buscador personal de {N}", "buscador personal de quien usa la app"), (rf"Pregunta de {N}:", "Pregunta:"),
          (rf"guardados por {N}", "guardados de ejemplo"), (rf"\bde {N}\b", "del autor"), (rf"\ba {N}\b", "al autor"),
          (rf"\b{N}\b", "el autor"),
          (r' \("Sitios con [^)]*\)', "")] if N else []   # nombres de sus colecciones de Instagram en un comentario


def neutro(carpeta: Path) -> None:
    for p in carpeta.rglob("*"):
        if p.suffix in (".js", ".html", ".css", ".json", ".webmanifest") and p.is_file():
            s = t = p.read_text()
            for a, b in NEUTRO:
                t = re.sub(a, b, t)
            if t != s:
                p.write_text(t)


def main():
    if not SRC.exists():   # fuera del Mac del autor (repo público): web/guardados y vendor/ ya vienen copiados
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
    neutro(dst)
    (HERE / "vendor").mkdir(exist_ok=True)
    shutil.copy2(SRC / "rules.py", HERE / "vendor" / "rules.py")
    n = sum(1 for _ in dst.rglob("*") if _.is_file())
    print(f"web/guardados: {n} ficheros · vendor/rules.py copiado")


if __name__ == "__main__":
    main()
