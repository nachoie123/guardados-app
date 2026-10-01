#!/bin/bash
# Empaqueta Guardados.app (universal2) en dist/ y pasa el chequeo de seguridad.
set -e
cd "$(dirname "$0")"
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12; [ -x $PY ] || PY=python3
[ -x .venv/bin/python ] || { $PY -m venv .venv && .venv/bin/pip install -q pywebview==6.2.1 certifi pyinstaller==6.22.3 segno==1.6.6; }
.venv/bin/python tools/copiar_web.py
# buscador de Apple Maps (MKLocalSearch) para el mapa sin IA: un binario por arquitectura y lipo
mkdir -p build
swiftc -O -target arm64-apple-macos11 -o build/geo-arm64 tools/geo.swift
swiftc -O -target x86_64-apple-macos11 -o build/geo-x86_64 tools/geo.swift
lipo -create -output build/geo.tmp build/geo-arm64 build/geo-x86_64 && mv build/geo.tmp build/geo && lipo -archs build/geo
# candado del buzón del móvil (AES-256-GCM con CryptoKit): igual, universal2
swiftc -O -target arm64-apple-macos11 -o build/sello-arm64 tools/sello.swift
swiftc -O -target x86_64-apple-macos11 -o build/sello-x86_64 tools/sello.swift
lipo -create -output build/sello.tmp build/sello-arm64 build/sello-x86_64 && mv build/sello.tmp build/sello && lipo -archs build/sello
.venv/bin/python -m unittest discover -s tests
rm -rf build/Guardados dist/Guardados dist/Guardados.app
.venv/bin/pyinstaller --noconfirm --clean Guardados.spec > build/pyinstaller.log 2>&1 || { tail -30 build/pyinstaller.log; exit 1; }
tail -2 build/pyinstaller.log
.venv/bin/python tools/seguridad.py dist/Guardados.app
