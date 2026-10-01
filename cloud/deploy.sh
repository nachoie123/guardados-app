#!/bin/bash
# Despliega el buzón cifrado de Guardados en la cuenta de Cloudflare de Nacho (plan gratis, sin tarjeta).
#
#   cd ~/Projects/guardados-app/cloud && ./deploy.sh
#
# 1. comprueba que wrangler tiene sesión (si no: npx wrangler login, en el navegador)
# 2. crea el espacio KV "guardados-sync" (si ya existe, reutiliza su id) y lo apunta en wrangler.toml
# 3. despliega el Worker y saca su URL (https://guardados-sync.<cuenta>.workers.dev)
# 4. escribe esa URL en la app del Mac (../nube.py) y en la web (~/Projects/ig-saved/app/buzon-config.js)
# 5. prueba que contesta: un id inventado tiene que dar 404
# Después: ../build.sh (app nueva) y, en ig-saved, ./publish.sh (web nueva). Eso no lo hace este script.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$PATH"
WEB_CFG="$HOME/Projects/ig-saved/app/buzon-config.js"
APP_CFG="../nube.py"

[ -d node_modules/wrangler ] || npm install --no-fund --no-audit
if ! npx wrangler whoami 2>/dev/null | grep -qi "associated with the email\|You are logged in"; then
  echo "wrangler no tiene sesión. Ejecuta:  npx wrangler login   (se abre el navegador) y vuelve a lanzar ./deploy.sh"
  exit 1
fi

echo "== espacio KV"
KV_ID=$(npx wrangler kv namespace list 2>/dev/null | python3 -c "import json,sys;print(next((n['id'] for n in json.load(sys.stdin) if n['title'] in ('guardados-sync','guardados-sync-KV')),''))" || true)
if [ -z "$KV_ID" ]; then
  out=$(npx wrangler kv namespace create guardados-sync 2>&1) || { echo "$out"; exit 1; }
  KV_ID=$(echo "$out" | grep -Eo '[0-9a-f]{32}' | head -1)
fi
[ -n "$KV_ID" ] || { echo "No encuentro el id del espacio KV."; exit 1; }
sed -i '' -E "s|^id = \"[0-9a-f]{32}\"  # deploy.sh: KV_ID|id = \"$KV_ID\"  # deploy.sh: KV_ID|" wrangler.toml
grep -q "\"$KV_ID\"" wrangler.toml || { echo "No he podido escribir el id en wrangler.toml"; exit 1; }
echo "ok $KV_ID"

echo "== Worker"
out=$(npx wrangler deploy 2>&1) || { echo "$out"; exit 1; }
URL=$(echo "$out" | grep -Eo 'https://guardados-sync\.[A-Za-z0-9-]+\.workers\.dev' | head -1)
[ -n "$URL" ] || { echo "$out"; echo "No encuentro la URL en la salida de wrangler deploy."; exit 1; }
echo "$URL"

echo "== configuración"
sed -i '' -E "s|^BUZON_URL = \"[^\"]*\"  # deploy.sh: BUZON_URL|BUZON_URL = \"$URL\"  # deploy.sh: BUZON_URL|" "$APP_CFG"
sed -i '' -E "s|^export const BUZON_URL = \"[^\"]*\";  // deploy.sh: BUZON_URL|export const BUZON_URL = \"$URL\";  // deploy.sh: BUZON_URL|" "$WEB_CFG"
grep -q "\"$URL\"" "$APP_CFG" && grep -q "\"$URL\"" "$WEB_CFG" || { echo "No he podido escribir la URL en $APP_CFG o $WEB_CFG"; exit 1; }
echo "nube.py y buzon-config.js → $URL"

echo "== prueba"
ID=$(python3 -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))")
code=$(curl -s -o /dev/null -w "%{http_code}" "$URL/v1/$ID/index.bin")
cors=$(curl -s -D - -o /dev/null -H "Origin: https://nachosanbenito.com" "$URL/v1/$ID/index.bin" | grep -i "access-control-allow-origin" | tr -d '\r')
echo "id inventado → $code (debe ser 404) · $cors"
[ "$code" = "404" ] || { echo "El Worker no contesta como debe."; exit 1; }

cat <<MSG

Listo. Falta:
  1. ../build.sh                         (la app del Mac con la URL nueva; pasa el chequeo de seguridad)
  2. cd ~/Projects/ig-saved && git commit -am "Buzón: URL real" && ./publish.sh   (la web)
MSG
