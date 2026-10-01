#!/bin/bash
# Sonda contra Instagram/TikTok de verdad: abre la app (desde el código), espera
# a que inicies sesión en las dos ventanas (hasta 10 min), pide UNA página de
# cada API y apunta solo la forma de la respuesta. No importa nada.
#   tools/probe.sh            -> build/probe.json
set -e
cd "$(dirname "$0")/.."
mkdir -p build
export GUARDADOS_PROBE="$PWD/build/probe.json" GUARDADOS_NO_AUTO=1 \
       GUARDADOS_DATA="$(mktemp -d /tmp/guardados-probe.XXXX)" GUARDADOS_PORT=47614
.venv/bin/python app.py
cat build/probe.json
