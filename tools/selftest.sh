#!/bin/bash
# Prueba de punta a punta con Instagram/TikTok falsos (sin internet ni cuentas).
# Puerto 47615, no el 47613 de la app: WebKit guarda IndexedDB por origen y por app (bundle id), así
# que con el mismo puerto los guardados falsos de la prueba acababan en «Mis guardados» de verdad.
#   tools/selftest.sh                 # desde el código (python3 del sistema + pywebview)
#   tools/selftest.sh "dist/Guardados.app/Contents/MacOS/Guardados"   # contra la app empaquetada
set -e
cd "$(dirname "$0")/.."
OUT="${OUT:-$PWD/build/selftest.json}"
DATA_DIR="$(mktemp -d /tmp/guardados-selftest.XXXX)"
mkdir -p build; rm -f "$OUT"
BIN="${1:-}"
export GUARDADOS_SELFTEST="$OUT" GUARDADOS_DATA="$DATA_DIR" GUARDADOS_PORT=47615 \
       GUARDADOS_IG_URL=http://127.0.0.1:47700/ GUARDADOS_TT_URL=http://127.0.0.1:47701/ \
       GUARDADOS_GEMINI_URL='http://127.0.0.1:47702/v1beta/models/{m}:generateContent' \
       GUARDADOS_GEO_BIN="$PWD/tools/fake_geo.py" \
       GUARDADOS_BUZON_URL="${GUARDADOS_BUZON_URL:-http://127.0.0.1:8787}" GUARDADOS_WEB_URL="${GUARDADOS_WEB_URL:-http://127.0.0.1:8781/}" \
       GUARDADOS_SELFTEST_ENLACE="${GUARDADOS_SELFTEST_ENLACE:-$PWD/build/selftest-enlace.json}"
rm -f "$GUARDADOS_SELFTEST_ENLACE"
# Gemini, Apple Maps y el CDN de portadas falsos; el buzón del móvil, el de cloud/ en local (wrangler dev)
if [ -n "$BIN" ]; then "$BIN"; else .venv/bin/python app.py; fi
echo "datos de prueba en $DATA_DIR"; cat "$OUT"
