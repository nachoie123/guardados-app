# Chequeo de seguridad de Guardados.app

Generado por `tools/seguridad.py` el 2026-10-01 19:11 sobre `dist/Guardados.app`.
Todo lo de abajo es salida real de este script, no texto escrito a mano.

| Prueba | Resultado |
|---|---|
| (a) Sin datos personales ni claves en el paquete | OK |
| (b) Instagram/TikTok no pueden llamar a la app (js_api solo en el panel) | OK |
| (c) CSP del panel con 'unsafe-eval' y sin script en línea | OK |
| (d) Nombres y captions escapados (panel y Mis guardados) | OK |
| App empaquetada importa sola de punta a punta (IG/TT falsos) | OK |
| (e) Clave de Gemini: fuera del paquete, fichero 600, ni en logs ni en status, solo en cabecera; IG/TT no la tocan | OK |
| (f) Nombres de sitios hostiles escapados en «Mis guardados» | OK |
| (g) Barra de progreso en el panel durante la importación | OK |
| (h) Carpetas, subcarpetas y mapa sin IA llegan a la web; sin clave, cero llamadas a Gemini | OK |
| (i) Buzón: sin token no se escribe, id inventado da 404, CORS solo nachosanbenito.com (+ localhost de pruebas), tope de tamaño | OK |
| (j) El servidor solo guarda bytes cifrados (ni texto, ni JPEG, ni la llave) | OK |
| (k) App empaquetada sube → la web abre el enlace del QR → guardados con portadas; la llave nunca viaja | OK |
| (l) «Desconectar móviles» deja fuera al móvil viejo; el código nuevo funciona | OK |
| (m) La sincronización de Nacho (sync/ + #k=) da lo mismo que la web de antes; sin buzón, ni una petición | OK |
| (n) Llave del móvil: fichero 600, ni en status ni en logs ni en el panel; IG/TT no piden el QR ni la cambian | OK |
| (o) Carpetas a mano: se guardan aparte, nada automático las pisa, nombres hostiles fuera; IG/TT no escriben | OK |
| Buscador de Apple Maps empaquetado contesta (Apple real) | OK |
| Todos los binarios universal2 (x86_64 + arm64) | OK (68 binarios) |

## (a) Datos personales

Ficheros revisados: 813 (incluye cada módulo del archivo comprimido de Python dentro del ejecutable), 73.9 MB descomprimidos. Apariciones de cada cosa buscada:

- clave de sincronización (.sync-key): **0**
- claves de Gemini de Nacho (valor exacto): **0**
- cualquier clave con forma de Gemini (AIza…): **0**
- correos de Nacho: **0**
- teléfono de Nacho: **0**
- ruta de su carpeta personal (/Users/nachosanbenito): **0**
- codes de sus 3944 guardados (saved.db): **0**
- ficheros de datos dentro del paquete (saved.db, posts.json, mis-guardados*.json, .sync-key, k-test.txt, .gemini-key, gemini.key, guardados.db, movil.json): **0**

Se buscan los valores exactos pero no se imprimen. Los comentarios del código de la web que nombran a Nacho (p. ej. «los filtros los quitó Nacho») no son datos y no se cuentan; el identificador del paquete es com.nachosanbenito.guardados, como el de IG Limpieza.

## (b) La página de Instagram/TikTok no puede llamar a la app

Las ventanas de Instagram y TikTok cargaron páginas hostiles falsas que probaron todas las puertas:

```
{
 "has_pywebview": true,
 "api_keys": [],
 "api.import_now": "error: TypeError: window.pywebview.api[f] is not a function. (In 'window.pywebview.api[",
 "api.export_json": "error: TypeError: window.pywebview.api[f] is not a function. (In 'window.pywebview.api[",
 "api.status": "error: TypeError: window.pywebview.api[f] is not a function. (In 'window.pywebview.api[",
 "api.show": "error: TypeError: window.pywebview.api[f] is not a function. (In 'window.pywebview.api[",
 "api.stop": "error: TypeError: window.pywebview.api[f] is not a function. (In 'window.pywebview.api[",
 "bridge.export_json": "enviado",
 "bridge.import_now": "enviado",
 "bridge.__class__.__base__.__subclasses__": "enviado",
 "bridge.pywebviewMoveWindow": "enviado",
 "bridge.pywebviewStateUpdate": "enviado",
 "raw_handler": "enviado",
 "fetch http://127.0.0.1:47615/feed/adivinado/items.json": "bloqueado: TypeError: Load failed",
 "fetch http://127.0.0.1:47615/panel/": "bloqueado: TypeError: Load failed"
}
```

Llamadas que llegaron a funciones de la app desde esas páginas: **0**.
Mensajes bloqueados por el puente vigilado (app.py `_guard_bridge`): **24**:

- Instagram: `export_json`
- Instagram: `import_now`
- Instagram: `__class__.__base__.__subclasses__`
- Instagram: `pywebviewMoveWindow`
- Instagram: `pywebviewStateUpdate`
- Instagram: `export_json`
- TikTok: `export_json`
- TikTok: `import_now`
- TikTok: `__class__.__base__.__subclasses__`
- TikTok: `pywebviewMoveWindow`
- TikTok: `pywebviewStateUpdate`
- TikTok: `export_json`
- Instagram: `set_gemini_key`
- Instagram: `delete_gemini_key`

«Mis guardados» (sin js_api) ve `pywebview.api` con funciones: False.
Servidor local: feed sin token → HTTP Error 404: Not Found; con token → 200; Host falso (DNS rebinding) → HTTP Error 403: Forbidden.

## (c) CSP del panel

- Cabecera HTTP: `default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`
- Meta en index.html: `default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'`
- eval() permitido (pywebview lo necesita): True
- Un `<script>` en línea inyectado se ejecutó: False (violaciones CSP: ['script-src-elem', 'script-src-elem'])

## (d) Escapado

Un guardado de prueba trae caption `<img src=x onerror=…>` y nombre `<script>…</script>`.

- Panel: código ejecutado 0 veces; etiquetas reales en la lista 0; se ve como texto: «<img src=x onerror="window.__pwned=(window.__pwned||0)+1"> Receta de pasta rápida para cenar
    TikTok · @tt.»
- Mis guardados: código ejecutado 0 veces; `<img src=x>` en el DOM 0; la ficha muestra el texto literal: True

## (e) Clave de Gemini (IA opcional)

El selftest pega una clave de prueba en el panel con `pywebview.api.set_gemini_key` (el mismo camino que la persona).
Gemini es un servidor FALSO en 127.0.0.1:47702; no se llama al de verdad.

- Guardada: {'ok': True}; permisos del fichero: 0o600
- Aparece en lo que devuelve status() al panel: False; en app.log: False
- Llamadas al Gemini falso: 65; todas con la clave en la cabecera x-goog-api-key: True; alguna con la clave en la URL: False
- Guardados afinados con IA: {'done': 100, 'total': 100} en 0.5 s; ejemplo (Selftest000): ['sitios/bares', 'humor/memes'], 1 sitio(s)
- Sin clave (antes de pegarla), llamadas a Gemini: 0
- Las páginas hostiles de Instagram y TikTok intentan guardar, borrar y leer la clave:

```
{
 "instagram": {
  "set_gemini_key": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.set_gemini_key": "enviado",
  "delete_gemini_key": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.delete_gemini_key": "enviado",
  "status": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.status": "enviado",
  "fetch_key": "bloqueado",
  "page_has_key": false
 },
 "tiktok": {
  "set_gemini_key": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.set_gemini_key": "enviado",
  "delete_gemini_key": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.delete_gemini_key": "enviado",
  "status": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.status": "enviado",
  "fetch_key": "bloqueado",
  "page_has_key": false
 }
}
```

- La clave sigue siendo la del panel tras el ataque: True; el servidor local sirve /gemini.key: HTTP Error 404: Not Found

## (f) Sitios con nombre hostil

Apple Maps falso (tools/fake_geo.py) devuelve el sitio `<img src=x onerror=…>Bar Trampa`. Ficha en «Mis guardados»: 1 sitio(s), etiquetas reales 0, código ejecutado 0 veces; se ve como texto: «🍸 <img src=x onerror="window.__pwned=(window.__pwned||0)+1">Bar TrampaCalle Falsa 123 Madrid Ir ×»

## (g) Barra de progreso

Lo que pintaba el panel en plena importación de TikTok (captura: `/Users/nachosanbenito/Projects/guardados-app/build/panel-progreso.png`):

```
[
 {
  "name": "Instagram",
  "num": "60 guardados",
  "sub": "Hecho · 60 nuevos",
  "bar": "bar ok",
  "width": ""
 },
 {
  "name": "TikTok",
  "num": "30 de 40 favoritos",
  "sub": "Quedan menos de un minuto · va a 506 por minuto",
  "bar": "bar",
  "width": "75%"
 },
 {
  "name": "Portadas",
  "num": "30 de 30 portadas",
  "sub": "Hecho",
  "bar": "bar ok",
  "width": ""
 },
 {
  "name": "Mapa (Apple Maps)",
  "num": "60 de 60 guardados",
  "sub": "Hecho · 2 sitios en el mapa",
  "bar": "bar ok",
  "width": ""
 }
]
```

- TikTok: total 40 (lo da item_list), tiempo restante calculado: True
- Instagram: sin total (no lo da), barra en movimiento; al final {'state': 'ok', 'done': 60, 'total': None, 'eta': None, 'rate_min': None}

## (h) Carpetas y mapa sin IA

- Con subcarpeta: 100 de 100; carpetas: ['finanzas', 'recetas', 'sitios', 'tecnologia']
- Guardados con sitios en el mapa: ['Selftest000', 'Selftest001']
- En IndexedDB de la web (Selftest000): {'cat': ['sitios', 'humor'], 'sub': ['sitios/bares', 'humor/memes'], 'lug': 1}

## (o) Carpetas a mano

En «Mis guardados», ficha de Selftest000: se añade a Recetas › Postres, se intenta crear la carpeta `<img src=x onerror=…>Trampa` (desde la web y saltándose la web), se crea «Regalos 🎁» y se quita la primera.

```
{
 "tras_anadir": [
  "Sitios › Bares y copas",
  "Humor › Memes",
  "Recetas › Postres"
 ],
 "aviso": "Ese nombre no vale: usa letras, números, espacios o emojis.",
 "directo": {
  "ok": false,
  "error": "Ese nombre de carpeta no vale: usa letras, números, espacios o emojis."
 },
 "tras_crear": [
  "Sitios › Bares y copas",
  "Humor › Memes",
  "Recetas › Postres",
  "Regalos 🎁"
 ],
 "aviso_crear": "",
 "final": [
  "Humor › Memes",
  "Recetas › Postres",
  "Regalos 🎁"
 ],
 "pwned": 0,
 "img_x": 0,
 "tags": 0,
 "chips": [
  "Humor",
  "Recetas",
  "Regalos 🎁"
 ]
}
```

- En la base (tabla `manual`): [["humor/memes", "recetas/postres", "Regalos 🎁"], true]
- Tras re-importar con otra descripción y que la IA diga otra cosa: [["humor/memes", "recetas/postres", "Regalos 🎁"], true]
- Lo que va a la web y al móvil (feed): {"cat": ["humor", "recetas", "Regalos 🎁"], "sub": ["humor/memes", "recetas/postres"]}
- Instagram y TikTok (páginas hostiles) intentan escribir o leer el token:

```
{
 "instagram": {
  "post_sin_token": "bloqueado",
  "post_form": "bloqueado",
  "leer_token": "bloqueado"
 },
 "tiktok": {
  "post_sin_token": "bloqueado",
  "post_form": "bloqueado",
  "leer_token": "bloqueado"
 }
}
```

- Tras el ataque: [["humor/memes", "recetas/postres", "Regalos 🎁"], true]
- La web, al cerrar la ficha: {"carpetas": ["Humor", "Sitios", "Tecnología", "Recetas", "Regalos 🎁", "Todos los vídeos", "Instagram", "TikTok"], "regalos": true, "pwned": 0, "img_x": 0, "idb": {"cat": ["humor", "recetas", "Regalos 🎁"], "sub": ["humor/memes", "recetas/postres"]}}

## Buscador de Apple Maps empaquetado

`{'path': 'Contents/Frameworks/geo', 'ok': True, 'name': 'Museo del Prado', 'cat': 'MKPOICategoryLandmark', 'lat': 40.414, 'lng': -3.692}`

## Punta a punta (app empaquetada, sin internet)

- Importación automática al detectar sesión: {"instagram": {"n": 60, "covers": 60, "tr": 0}, "tiktok": {"n": 40, "covers": 40, "tr": 0}} en 15.3 s
- Pasado a la web (IndexedDB de «Mis guardados»): 100 guardados

## El móvil (buzón cifrado)

Todo en local: el Worker de `cloud/` con `npx wrangler dev` (KV simulado en `build/wrangler-state`), la web de `~/Projects/ig-saved/app` copiada sin datos en http://127.0.0.1:8781 y Chromium (Playwright). Nada se ha desplegado. La llave y los tokens no se imprimen.

### (n) En el Mac (app empaquetada, selftest)

- El panel enseña el QR al pulsar «Conectar el móvil»: True (SVG: True, 230 px)
- Subida al buzón: {"on": true, "subido": 1790874623, "posts": 100, "covers": 100, "mb": 0.9, "subiendo": false, "error": null} en 0.5 s; una segunda subida sin cambios: {'skip': 'sin cambios'}
- movil.json: permisos 0o600; la llave/tokens/id salen en status(): False, en app.log: False, en el HTML del panel: False
- El servidor local sirve /movil.json: HTTP Error 404: Not Found; la llave sigue igual tras el ataque: True
- Instagram y TikTok (páginas hostiles) intentan pedir el QR, cambiar la llave y leer el fichero:

```
{
 "instagram": {
  "movil_qr": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.movil_qr": "enviado",
  "movil_cambiar": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.movil_cambiar": "enviado",
  "status": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.status": "enviado",
  "fetch /movil.json": "bloqueado",
  "fetch /feed/x/movil.json": "bloqueado",
  "fetch /panel/../movil.json": "bloqueado"
 },
 "tiktok": {
  "movil_qr": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.movil_qr": "enviado",
  "movil_cambiar": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.movil_cambiar": "enviado",
  "status": "error: TypeError: window.pywebview.api[f] is not a function. (In 'w",
  "bridge.status": "enviado",
  "fetch /movil.json": "bloqueado",
  "fetch /feed/x/movil.json": "bloqueado",
  "fetch /panel/../movil.json": "bloqueado"
 }
}
```

### (i) El Worker

```
{
 "crear": 201,
 "crear_otra_vez": 409,
 "put_sin_token": 401,
 "put_token_inventado": 401,
 "put_con_token_de_lectura": 401,
 "put_con_token_de_escritura": 201,
 "get_sin_token": 401,
 "get_con_token_de_escritura": 401,
 "get_con_token_de_lectura": 200,
 "get_devuelve_lo_mismo": true,
 "get_objeto_que_falta": [
  404,
  "aún no está"
 ],
 "get_id_inventado": 404,
 "put_id_inventado": 404,
 "id_corto": 404,
 "nombre_meta": 404,
 "nombre_raro": 404,
 "stats": 404,
 "put_25MB_mas_1": 413,
 "origen_malo": [
  403,
  null
 ],
 "origen https://nachosanbenito.com": [
  200,
  "https://nachosanbenito.com"
 ],
 "origen http://127.0.0.1:8781": [
  200,
  "http://127.0.0.1:8781"
 ],
 "preflight_metodos": "GET",
 "put_desde_navegador": 403,
 "borrar_sin_token": 401,
 "borrar_con_token": 200,
 "get_tras_borrar": [
  404,
  "sin buzón"
 ]
}
```

### (j) Lo que guarda el servidor

KV local de wrangler: `{"ficheros": 25, "bytes": 3377351, "objetos_grandes": 3, "con_entropia_baja": [], "apariciones": {}}`. Se buscan captions, codes y cuentas de prueba, cabeceras JPEG, JSON de guardados, nombres de carpetas y la llave: 0 apariciones; cada objeto grande tiene la entropía de bytes al azar.

El buzón de la app, abierto con la llave del enlace (como el móvil): `{"index": 200, "posts_obj": 200, "posts": 100, "covers": 100, "paquetes": 1, "bytes_datos": 2958, "bytes_portadas": 856175, "otra_llave_no_abre": true, "ejemplo": {"id": "Selftest000", "src": "instagram", "cat": ["humor", "recetas", "Regalos 🎁"], "sub": ["humor/memes", "recetas/postres"]}}`

### (k) La web abre el enlace del QR

```
{
 "qr_es_el_enlace": true,
 "idb": {
  "posts": 100,
  "covers": 100,
  "img": 100
 },
 "url_tras_abrir": "http://127.0.0.1:8781/",
 "fragmento_borrado": true,
 "llave_guardada_en_el_dispositivo": true,
 "dialogo": "Listo: 100 guardados nuevos y 100 portadas.",
 "grid": {
  "carpetas": 48,
  "imgs": 48,
  "blob": 48,
  "pintadas": 48,
  "ancho": 270,
  "built": "100 guardados tuyos, en este dispositivo",
  "status": "Del Mac: 100 guardados nuevos, 100 portadas. 100 guardados"
 },
 "peticiones_al_buzon": 3,
 "todas_con_cabecera": true,
 "llave_o_token_en_alguna_url": false,
 "al_recargar_pide": [
  "index.bin"
 ],
 "al_recargar_idb": {
  "posts": 100,
  "covers": 100
 },
 "busqueda": {
  "tarjetas": 40,
  "con_portada": 40
 },
 "captura": "build/movil-web.png"
}
```

Capturas: `build/movil-web.png` (carpetas) y `build/movil-web-lista.png` (búsqueda «pasta», con portadas).

### (l) Cambiar la llave

```
{
 "subir": {
  "ok": true,
  "bytes": 102547,
  "covers": 12
 },
 "antes": {
  "posts": 12,
  "covers": 12
 },
 "subir_nuevo": {
  "ok": true,
  "bytes": 9355,
  "covers": 1
 },
 "con_uno_nuevo": {
  "posts": 13,
  "covers": 13
 },
 "subir_llave_nueva": {
  "ok": true,
  "bytes": 111503,
  "covers": 13
 },
 "movil_viejo": {
  "buzon": "borrado",
  "status": "Tu Mac cambió la llave: este móvil se ha desconectado. Escanea el código nuevo."
 },
 "id_viejo": 404,
 "enlace_distinto": true,
 "movil_nuevo": {
  "posts": 13,
  "covers": 13
 }
}
```

### (m) La sincronización de Nacho, antes y ahora

Paquetes con el formato de `tools/sync-pack.py` pero con datos inventados y una llave de prueba (la `.sync-key` de Nacho no se lee). La misma prueba con la web de git HEAD («antes») y con la nueva («ahora»):

```
{
 "iguales": true,
 "antes": {
  "sin_conectar": {
   "cards": 0,
   "built": "Muestra de 34 guardados",
   "mac": "Vincular con el Mac",
   "peticiones_buzon": 0,
   "peticiones_sync": 0
  },
  "con_k": {
   "idb": {
    "posts": 30,
    "covers": 30,
    "img": 30
   },
   "rows": "30 filas (id, carpeta, subcarpeta, sitios, portada)",
   "url": "http://127.0.0.1:8781/",
   "ls": [
    "guardados.sync",
    "guardados.sync.posts.v4"
   ],
   "built": "30 guardados tuyos, en este dispositivo",
   "mac": "✓ Vinculado con el Mac · traer lo nuevo",
   "peticiones": [
    "f3216265f95f1a63.bin",
    "fb0c674439179186.bin",
    "index.bin"
   ],
   "peticiones_buzon": 0,
   "al_recargar": {
    "posts": 30,
    "covers": 30
   }
  }
 },
 "ahora": {
  "sin_conectar": {
   "cards": 0,
   "built": "Muestra de 34 guardados",
   "mac": "Vincular con el Mac",
   "peticiones_buzon": 0,
   "peticiones_sync": 0
  },
  "con_k": {
   "idb": {
    "posts": 30,
    "covers": 30,
    "img": 30
   },
   "rows": "30 filas (id, carpeta, subcarpeta, sitios, portada)",
   "url": "http://127.0.0.1:8781/",
   "ls": [
    "guardados.sync",
    "guardados.sync.posts.v4"
   ],
   "built": "30 guardados tuyos, en este dispositivo",
   "mac": "✓ Vinculado con el Mac · traer lo nuevo",
   "peticiones": [
    "f6e34e8de538cf0f.bin",
    "fd25884dccd3fd76.bin",
    "index.bin"
   ],
   "peticiones_buzon": 0,
   "al_recargar": {
    "posts": 30,
    "covers": 30
   }
  }
 }
}
```

## Arquitecturas

- `Contents/Frameworks/AppKit/_AppKit.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/AppKit/_inlines.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/CoreFoundation/_CoreFoundation.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/CoreFoundation/_inlines.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/Foundation/_Foundation.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/Foundation/_inlines.cpython-312-darwin.so`: x86_64 arm64
- `Contents/Frameworks/Python.framework/Versions/3.12/Python`: x86_64 arm64
- `Contents/Frameworks/WebKit/_WebKit.cpython-312-darwin.so`: x86_64 arm64
- … y 60 más, todos x86_64 arm64
