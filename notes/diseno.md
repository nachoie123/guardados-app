# Guardados para Mac: decisiones de diseño

La app es un **recadero con libreta**. La persona abre la puerta de Instagram
y la de TikTok (inicia sesión en sus webs oficiales, dentro de la app). El
recadero entra por esas puertas ya abiertas, pide la lista de guardados y la
apunta en una libreta que se queda en casa (su Mac). Nunca tiene llaves
propias: si la persona cierra la puerta, el recadero no puede entrar.

## Qué hace cada pieza

| Pieza | Qué hace | Fichero |
|---|---|---|
| Panel | La única ventana que puede hablar con Python: estado, botones, progreso | `web/panel/`, `app.py` (`Api`) |
| Ventanas de Instagram y TikTok | Las webs oficiales. La persona inicia sesión ahí | `app.py` (`main`) |
| Recadero | Hace `fetch()` **dentro** de esas ventanas, con su sesión, y valida lo que vuelve | `importer.py` |
| Libreta | SQLite con los guardados y por dónde iba cada importación | `db.py` |
| Títulos | `rules.py` de ig-saved, solo expresiones regulares, sin IA | `vendor/rules.py` |
| Carpetas y subcarpetas | El árbol de ig-saved/carpetas.py rellenado con palabras clave ES/EN (motor de la decisión 10) | `carpetas.py` |
| Carpetas a mano | Desde la ficha de «Mis guardados»: añadir, quitar y crear carpetas; mandan sobre lo automático | `web/mac/asignar.js`, `server.py` (`/api/`), `db.py` (`manual`) |
| Mapa | Sitios sacados de la descripción + Apple Maps (MKLocalSearch, universal2) | `sitios.py`, `tools/geo.swift`, `completar.py` |
| IA opcional | Con la clave de Gemini de la persona, carpetas y sitios como en ig-saved | `ia.py`, `completar.py` |
| Barra de progreso | Cuántos van, cuántos hay (si se sabe) y cuánto falta, por etapa | `progreso.py`, `web/panel/panel.js` |
| Portadas | Se bajan en cuanto llegan (los enlaces caducan en días) | `media.py` |
| Mostrador local | Sirve el panel y la web de guardados en `127.0.0.1` | `server.py` |
| Mis guardados | La misma web de nachosanbenito.com/guardados, servida desde el Mac | `web/guardados/` (copia sin datos) |
| Buzón del móvil | Sube los guardados cifrados a una taquilla de Cloudflare; el móvil los baja con el QR | `nube.py`, `tools/sello.swift`, `cloud/` |

## Decisión 1: la cuenta de cada persona vive en su Mac

**Qué se guarda y dónde:**

- La sesión de Instagram/TikTok (cookies): la guarda WebKit, como Safari, en
  `~/Library/WebKit/com.nachosanbenito.guardados` y `~/Library/HTTPStorages/…`.
  La app no la lee ni la copia; solo la usa la propia página.
- Los guardados, el estado de reanudación y las portadas:
  `~/Library/Application Support/Guardados/` (`guardados.db`, `media/`,
  `app.log`), carpeta 700 y base 600.
- Nada personal va dentro del `.app` (comprobado en `docs/seguridad.md`, (a)).

**Por qué no los paquetes cifrados de `tools/sync-pack.py`:**

1. Son de **una sola persona**. Hay una carpeta `app/sync/` y una clave
   `.sync-key` para toda la web; con dos personas habría que inventar
   carpetas por persona, gestionar sus claves y meterlas en el repo de Nacho.
2. Publicar es **`./publish.sh` desde el Mac de Nacho** (git push a su web).
   Una persona nueva no puede hacerlo, y Nacho no debe alojar en su web los
   guardados de otros, aunque vayan cifrados.
3. La regla del encargo era "solo se da de alta e inicia sesión". Un servidor
   o una cuenta propia de la app añadiría registro, contraseñas y un sitio que
   mantener. Sin servidor no hay nada que mantener ni que se pueda filtrar.

**Lo que se perdía:** la sincronización automática con el móvil. Al principio se
cubrió con un botón «Copia para el móvil (.json)» (AirDrop + Importar, sin
portadas). Desde el 01/10/2026 lo sustituye el buzón cifrado de la decisión 9:
cada persona con su propia llave, en un almacén gratuito de Cloudflare de Nacho
que solo ve bytes cifrados. Nacho sigue usando sus paquetes de `sync/` como
hasta ahora; no cambia nada para él.

## Decisión 2: cómo llega a la web de guardados

El panel y «Mis guardados» se sirven desde el **mismo origen**
(`http://127.0.0.1:47613`). Por eso comparten IndexedDB: el panel, cuando ve
algo nuevo, pide `/feed/<token>/items.json` y lo mete con el mismo
`store.js` (`parseFile` + `importItems`) que usa la web pública. La ventana
«Mis guardados» solo recarga.

- El puerto es fijo para que el IndexedDB (va por origen) no se pierda entre
  aperturas.
- El token del feed cambia en cada arranque y solo lo conoce el panel.
- La web viene de `~/Projects/ig-saved/app` con lista blanca
  (`tools/copiar_web.py`): código, iconos y vendor; sin `data/`, `covers/`,
  `sync/`, `fotos/` ni `demo/`. La muestra de Nacho se sirve vacía.

## Decisión 3: cómo importa

- **Instagram:** `/api/v1/feed/saved/posts/?count=50&max_id=…` con
  `X-IG-App-ID: 936619743392459`. Si vuelve HTML o 401/403, se pide iniciar
  sesión; nunca se interpreta HTML como datos.
- **TikTok:** `secUid` sale del `__UNIVERSAL_DATA_FOR_REHYDRATION__` de la
  página logueada; luego `/api/user/collect/item_list/` sin firma, como el
  marcador. Si TikTok devolviera cuerpo vacío (pide X-Bogus), se dice tal cual.
  Los subtítulos de TikTok (su propio reconocimiento de voz) se bajan desde la
  propia página, porque su CDN solo deja leerlos desde tiktok.com.
- **Incremental:** para tras 15 guardados ya conocidos seguidos.
- **Despacio:** 1-3 s entre páginas. 429 → espera 1, 2, 3… min. «Load
  failed» o tiempo agotado → 10, 20… s. Seis intentos y se para.
- **Reanudable:** el cursor de la página siguiente se apunta *después* de
  guardar cada página. Si la app se cierra, la próxima vez sigue desde ahí.
- **Sola:** un vigilante mira cada 10 s si hay sesión; si la hay y la última
  importación buena tiene más de 12 h (o quedó a medias), arranca.
- **Sin IA:** títulos con `rules.py`; carpetas, subcarpetas y mapa con reglas (decisiones 5 y 6). La transcripción de reels
  de Instagram (faster-whisper) solo corre si está instalada; en la app
  empaquetada no va (no hay ruedas universal2 y el modelo pesa ~460 MB).

## Decisión 4: empaquetado

PyInstaller `universal2` (`Guardados.spec`, `./build.sh`), igual que IG
Limpieza. `build.sh` copia la web, pasa las pruebas, construye y ejecuta
`tools/seguridad.py`, que escribe `docs/seguridad.md` con resultados reales.

## Comprobado contra Instagram y TikTok reales (01/10/2026, 15:14)

`.app` empaquetada en modo sonda (`GUARDADOS_PROBE`), sesión iniciada por Nacho
en las ventanas, una sola página por web, sin importar nada:

- **Instagram:** 200, `application/json`, 50 guardados, hay página siguiente;
  los 50 traen portada, enlace de vídeo y `saved_collection_ids`.
- **TikTok:** `secUid` sacado de la página; `item_list` **sin firma X-Bogus**
  responde 200 JSON, `statusCode 0`, 29 favoritos de 2.253, hay página
  siguiente; 29 con portada y 15 con subtítulos. No hace falta el marcador.

## Decisión 5: carpetas y subcarpetas sin IA (01/10/2026)

Nacho decidió «solo reglas y con IA opcional». La app es un **bibliotecario con
una lista de etiquetas**: mira las palabras de la descripción, el @usuario, el
nombre y (en TikTok) los subtítulos, y coloca cada vídeo en el mismo árbol que
Gemini le hizo a Nacho (`SUB` de ig-saved/carpetas.py, 29/09/2026: 22 carpetas,
12 con subcarpetas). `carpetas.py`:

- Carpeta grande: las palabras de `rules.py` (las mismas de la web) + unas pocas
  más; `planes` pasa a llamarse `sitios` y `estudios` va a `carrera`.
- **Sitios** solo si hay un sitio concreto (📍, una dirección, «Restaurante X»,
  una @cuenta de local) o si Apple Maps confirma uno; «comer» o «Madrid» a secas
  no bastan.
- Subcarpeta: la que más palabras suyas tenga; sin ninguna, la más común de
  esa carpeta en lo de Nacho.
- Se manda a la web con el formato de `export.py` (`cat`, `sub`, `ciudad`, `lug`):
  la web las ordena igual que las de Nacho (por número de vídeos, `subsDe` en app.js),
  porque es el mismo código.

**Calidad medida** (`tools/medir.py carpetas`): contra las carpetas de Gemini de
Nacho (`post_folders`, 3.776 vídeos). Las palabras se ajustaron mirando solo la
mitad «dev»; estas cifras son de la otra mitad (1.882 vídeos), que no se miró.
Escenario de la app: descripción + cuenta, subtítulos solo de TikTok.
(Cifras del motor viejo; las de ahora, en la decisión 10: 75 % y 46 %.)

| | |
|---|---|
| Carpeta principal igual que la de Nacho | **71 %** |
| Alguna carpeta en común | 76 % |
| Carpeta + subcarpeta exactas | **41 %** |

| Carpeta (vídeos) | La encuentra | Cuando la pone, acierta | Subcarpeta igual (si acierta la carpeta) |
|---|---|---|---|
| pelis_series (528) | 83 % | 79 % | 40 % |
| tecnologia (345) | 79 % | 89 % | 49 % |
| sitios (232) | 72 % | 77 % | 60 % |
| anime (160) | 61 % | 93 % | 41 % |
| recetas (145) | 83 % | 79 % | 61 % |
| humor (129) | 39 % | 40 % | 64 % |
| carrera (93) | 65 % | 56 % | 81 % |
| moda (76) | 72 % | 77 % | 89 % |
| videojuegos (74) | 86 % | 80 % | 69 % |
| finanzas (67) | 45 % | 51 % | 66 % |
| viajes (29) | 83 % | 26 % | 68 % |
| fitness_salud (23) | 74 % | 42 % | 82 % |
| sueltas pequeñas (musica, diseño, ciencia, negocios, hogar…) | 9-67 % | 8-44 % | — |

Dónde falla y por qué: el **género** de una escena de peli (comedia/acción/drama)
y si un clip de anime es «escena» o «edit» no está escrito en la descripción; lo
sabe quien ve el vídeo. Con la transcripción de Instagram (whisper, que no va en
la app empaquetada) apenas cambia: 71 % / 41 %. Para afinar eso está la IA opcional.

## Decisión 6: el mapa sin IA (01/10/2026)

Como quien lee un folleto con un rotulador (`sitios.py`): subraya lo que va tras
📍, las @cuentas que parecen de un local («📍 @bar_centifolia», «cenamos en
@casa_lucio», o cualquiera si la descripción habla de comer/salir) y frases tipo
«Restaurante Casa Pepe». Una @cuenta se convierte en nombre («sushiginmadrid» →
«Sushigin»). Una 📍 con solo la dirección se busca como dirección.

Luego cada nombre se busca en **Apple Maps** (`tools/geo.swift`, copia de la de
ig-saved + la categoría de Apple, que da el tipo del sitio: Restaurant → 🍽️,
Nightlife → 🍸…). Gratis, sin cuenta, sin permiso de ubicación. Va **compilado
universal2 dentro del .app** (`Contents/Frameworks/geo`, lo hace `build.sh`).
Solo se pincha si Apple devuelve algo **con un nombre parecido** en esa ciudad
(nunca un barrio o la calle que se llama igual). Si Apple no contesta (sin red),
no se da nada por mirado: se reintenta en la próxima importación. Las respuestas
se guardan (`geo_cache`) para no repetir búsquedas. `lug` sale con el formato que
la web ya entiende (`n, t, ci, lat, lng, a, aprox`); sin foto del sitio (`f`),
porque eso salía de fotogramas del vídeo.

**Calidad medida** (`tools/medir.py sitios --geo` y `falsos`, Apple Maps real):

- Vídeos con sitios de Nacho: 281 (486 sitios, sacados por Gemini mirando
  descripción, voz y fotogramas).
- Las reglas sacan algún nombre en **59 %** de esos vídeos (316 nombres); **37 %**
  de los sitios de Nacho coinciden por nombre.
- Apple Maps coloca 126 de esos 316 nombres; **96 caen a menos de 500 m de un
  sitio de Nacho** del mismo vídeo: **20 % de sus 486 sitios**, y de los pines
  que pone, 76 % son de Nacho.
- Pines de más: en los 3.498 vídeos donde Nacho no tiene sitio, las reglas sacan
  131 nombres (95 vídeos) y Apple confirma 26: **25 vídeos con un pin que Nacho
  no tiene (0,7 %)**; parte pueden ser sitios reales fuera de su carpeta Sitios.

Lo que no ve: sitios que solo se dicen en voz o se ven en el cartel (la mayoría en
los vídeos de «5 sitios de Londres»), y @cuentas pegadas que Apple no reconoce
(«nuriabrasserie»).

## Decisión 7: IA opcional con la clave de cada persona (01/10/2026)

En el panel, «IA opcional (Gemini)»: un campo para pegar la clave propia
(aistudio.google.com). Si la hay, al acabar cada importación `completar.pasada_ia`
rehace carpetas y subcarpetas (prompt de ig-saved/carpetas.py, lotes de 20,
`gemini-3.1-flash-lite`) y, en los de Sitios, investiga los sitios como
ig-saved/sitios.py (descripción, subtítulos y la portada; `gemini-3.8-flash`) y
los coloca con Apple Maps alrededor de la zona que da Gemini. Lo hecho con IA se
marca (`ia=1`) y las reglas ya no lo pisan.

La clave es **la llave de casa de la persona**:

- Se guarda solo en `~/Library/Application Support/Guardados/gemini.key`,
  permisos 600, carpeta 700. No en el Llavero: el .app va firmado ad hoc y cada
  versión nueva pediría permiso para leerla.
- Nunca dentro del .app ni en `app.log` (comprobado en `docs/seguridad.md`, (e)).
- Viaja en la cabecera `x-goog-api-key`, nunca en la URL.
- `status()` solo dice si hay clave, nunca cuál; el campo se vacía al guardar.
- Solo el panel puede guardarla o borrarla: las ventanas de Instagram/TikTok
  pasan por el puente vigilado y el servidor local no la sirve.
- La URL de Gemini solo se puede cambiar a `http://127.0.0.1:…` (pruebas con un
  Gemini falso); en la app real siempre es la de Google.

No se ha probado con Gemini real (Nacho no quiere gastar ahora); el camino entero
se prueba con un Gemini falso en 127.0.0.1 (`selftest.FakeGemini`). Con la clave
gratis, Flash tiene cupo diario bajo: la pasada de sitios puede quedarse a medias
con 429 y sigue sola en la siguiente importación.

## Decisión 8: la barra de progreso (01/10/2026)

El marcador de una carrera (`progreso.py`): una fila por etapa (Instagram,
TikTok, Portadas, Transcripción si hay whisper, Mapa, IA) con cuántos van, el
total si se sabe y cuánto falta. El ritmo se **mide** (lo que entró en los
últimos 90 s, contando pausas y esperas de 429), no se supone. TikTok da el total
(`total` de item_list) y sale «600 de 2.253 favoritos · Quedan unos 7 min».
Instagram no lo da: la barra va en movimiento y dice «Instagram no dice cuántos
tienes: la barra se llena al terminar» con el ritmo real. Todo se pinta con
`textContent` y las filas se reutilizan para que la barra se deslice sin saltos.
Captura real del panel en plena importación: `build/panel-progreso.png`.

## Cuánto tarda la primera vez (~500 guardados de IG + ~2.000 favoritos de TikTok)

Sale de los tiempos del código (pausas 1-3 s, páginas de 50 y 30, subtítulos de
4 en 4 con 0,3 s, Apple Maps a 1 búsqueda cada 1,3 s), de la sonda real del 01/10
(TikTok devuelve 29 por página y 15 de 29 traen subtítulos) y del selftest (con una
red falsa de 1,5 s por página, 2 páginas de IG + 2 de TikTok + mapa = 16 s). Lo que
NO está medido es la latencia real de cada página: se supone 1-1,5 s.

| Etapa | Cuenta | Tiempo |
|---|---|---|
| Instagram | 10 páginas × (≈1,5 s de red + 2 s de pausa media) | **≈ 35 s** |
| TikTok | ~69 páginas de 29 × (≈1 s de red + ≈4 s de subtítulos: ~15 por página en 4 tandas + 2 s de pausa) | **≈ 8 min** |
| Portadas | ~2.500, 4 a la vez, mientras importa | casi todo solapado; ≈ 1 min de cola |
| Mapa (Apple Maps) | ~7 % de los vídeos traen un nombre (dato de Nacho): ~175 vídeos, ~280 búsquedas × 1,3 s | **≈ 6 min** |
| **Total sin IA** | | **≈ 15-17 min** (con 429 de TikTok: +1, +2, +3 min por aviso) |
| IA opcional | 125 lotes de carpetas (≈5-10 s) + ~280 vídeos de Sitios (≈10-20 s cada uno) + sus búsquedas en Apple | ≈ 1-1,5 h más; con clave gratis, Flash se corta por cupo diario y sigue otro día |

La app se puede usar mientras tanto: lo que entra se ve en «Mis guardados» tras
cada tanda. Si se cierra, sigue donde iba.

## Decisión 9: el móvil, con un buzón cifrado por persona (01/10/2026)

Decisión de Nacho: «cada persona tiene su propio paquete cifrado con una clave
que solo tiene ella». Es una **taquilla de consigna**: el Mac mete los guardados
en cajas cerradas con candado y las deja en una taquilla de Cloudflare. El móvil
tiene el resguardo (para sacar las cajas) y la llave (para abrirlas). La
taquilla guarda las cajas, pero no tiene la llave: Nacho, que es el dueño de la
taquilla, solo ve cajas cerradas.

### Los pasos de la persona

1. En la app del Mac, «Tu móvil» → **Conectar el móvil**. Sale un QR.
2. Lo escanea con la cámara del iPhone. Se abre nachosanbenito.com/guardados,
   que guarda la llave, la borra de la barra de direcciones y baja sus
   guardados con portadas (barra «Trayendo portadas… 300 de 2.500»).
3. Ya está. Cada importación del Mac sube lo nuevo (solo si ha cambiado) y la
   web lo trae cada vez que se abre. Si quiere la app de la pantalla de inicio
   (que en iPhone guarda sus datos aparte de Safari), desde ahí: Ajustes →
   Vincular con el Mac → Escanear el QR (el mismo lector de siempre).
4. ¿Móvil perdido o QR enseñado? **Desconectar móviles y cambiar la llave**
   (dos toques): el buzón viejo se borra y los móviles viejos dicen «Tu Mac
   cambió la llave»; se escanea el código nuevo.

### Las piezas

| Pieza | Qué hace | Dónde |
|---|---|---|
| La llave y el resguardo | `movil.json` (600) en `~/Library/Application Support/Guardados`: id del buzón (32 bytes al azar), token de escritura, token de lectura y llave AES-256. Se crea al pulsar «Conectar el móvil», no antes | `nube.py` |
| El candado | AES-256-GCM con CryptoKit de Apple, compilado universal2 dentro del .app (`Contents/Frameworks/sello`), igual que el buscador de Apple Maps. La llave entra por stdin, nunca en argumentos | `tools/sello.swift` |
| Las cajas | El mismo formato que `ig-saved/tools/sync-pack.py` (la web ya lo sabía leer): `index.bin` + los datos en gzip + portadas en paquetes de ≤ 8 MB. Portadas reducidas a 270 px con `sips` (como hace la web) | `nube.py` |
| La taquilla | Worker de Cloudflare + KV: crear buzón, subir, bajar, borrar. Guarda solo el hash de cada token | `cloud/src/index.js`, `cloud/wrangler.toml` |
| El QR | Hecho en el Mac con `segno` (Python puro, empaquetado): SVG en `data:`, que la CSP del panel ya permite. Ni red ni JS de fuera | `app.py` (`movil_qr`), `web/panel/` |
| El móvil | `#conectar=` → `localStorage`, `history.replaceState`, y en cada apertura baja y descifra con `crypto.subtle` | `ig-saved/app/store.js` (`setBuzon`, `buzonNow`), `app.js` |

### Por qué así

- **La llave va en el fragmento (`#`)**: el navegador no lo manda al servidor
  (ni a GitHub Pages ni al Worker). Enlace: `https://nachosanbenito.com/guardados/#conectar=1.<id>.<lectura>.<llave>`.
  La web lo borra de la barra al leerlo.
- **Lectura con id + token de lectura** (y no solo con el id): el id viaja en la
  URL de cada petición, y las URL acaban en registros (de Cloudflare, de una red
  de empresa…). Con el token en la cabecera `Authorization`, quien vea un id no
  puede bajar ni las cajas cerradas. El token de lectura no sirve para escribir;
  el de escritura no sale nunca del Mac.
- **Subir solo si ha cambiado**: el Mac compara la huella de los datos y qué
  portadas ya subió; sin cambios, ni una petición. Los datos van primero (el
  móvil ya los ve) y el índice se actualiza tras cada paquete de portadas. El
  paquete de datos viejo se borra al subir el nuevo.
- **El buzón solo existe si la persona conecta un móvil**: quien no lo usa no
  gasta sitio en la taquilla de Nacho.
- **KV y no R2 (cambiado el 01/10/2026)**: R2 pide un medio de pago y Cloudflare
  no deja poner tope de gasto; Nacho no quiere que le puedan cobrar nada, pase lo
  que pase. KV va en el plan gratis **sin tarjeta**: si se pasa (1 GB, 1.000
  escrituras o 100.000 lecturas al día), Cloudflare rechaza la operación y ya está.
  Precio: caben unas 15 personas en vez de 180.
- **Topes en el Worker** (`wrangler.toml`): 25 MB por subida (KV admite 25 MiB),
  60 MB por persona y 15 buzones → 900 MB como mucho, por debajo del 1 GB. Crear
  un buzón no pide cuenta (no hay registro, como pidió Nacho), así que los topes
  son lo que impide que un desconocido llene la taquilla.
- **La cuenta va en la ficha de cada buzón** (`m/<id>`, campo `sz`): la lista de KV
  tarda hasta un minuto en enseñar lo recién subido, y con ella el tope de 60 MB
  dejaba pasar 84 MB subidos seguidos (probado en real el 01/10/2026). La ficha se
  lee al momento. KV solo deja reescribir la misma clave una vez por segundo: si
  dos subidas caen en el mismo segundo, el Worker espera y reintenta (probado: 6
  subidas seguidas en 1,5 s, todas bien). El número de buzones sí sale de la lista,
  así que una ráfaga de altas podría pasar de 15 por poco; sin tarjeta, el peor
  caso es que se llene el 1 GB y se rechacen subidas, nunca una factura.
- **Cloudflare corta el User-Agent por defecto de Python** (403, error 1010): la
  app manda `Guardados-Mac/1` y las pruebas `Guardados-Prueba/1`.
- **CORS**: solo `https://nachosanbenito.com` y el localhost de pruebas
  (`127.0.0.1:8781`) pueden leer desde un navegador, y solo con GET; otro origen
  recibe 403. Subir y borrar solo se hace sin navegador (la app del Mac).
- **Sin registros de contenido**: el Worker no tiene ni un `console.log` y la
  observabilidad va apagada. Los errores devuelven «error», sin detalles.
- **Configurable**: `BUZON_URL` en `nube.py` y en `ig-saved/app/buzon-config.js`
  (provisional: `https://guardados-sync.CUENTA.workers.dev`); `cloud/deploy.sh`
  escribe la buena. Para pruebas, `GUARDADOS_BUZON_URL` y `GUARDADOS_WEB_URL`
  (solo se aceptan `http://127.0.0.1` o `localhost`, como la URL de Gemini), y
  el QR añade `&u=` con el buzón local; la web solo acepta ese `u=` si es local.
- **Lo de Nacho no cambia**: `syncNow` sigue igual por fuera; su cuerpo pasó a
  una función común (`pull`) que también usa el buzón. Sin buzón conectado no se
  hace ni una petición nueva. Comprobado contra la web de antes (git HEAD) con
  paquetes de prueba: `docs/seguridad.md`, (m). `SYNC_POSTS` no sube porque su
  formato no ha cambiado; el buzón recuerda lo suyo en `guardados.buzon.posts.v1`.
  `SHELL` sube a `shell-v42` (fichero nuevo `buzon-config.js` en la caché).

### Cuánto ocupa una persona con ~2.500 guardados

| | Cuenta | Tamaño |
|---|---|---|
| Portadas | 2.500 × ~19 KB (las de Nacho a 270 px pesan 19 KB de media) | **≈ 48 MB** |
| Datos (captions, subtítulos de TikTok, carpetas, mapa), en gzip | los de Nacho: ~2 MB para 3.776 con transcripciones | **≈ 1-1,5 MB** |
| **Total** | cifrar añade 28 bytes por caja | **≈ 50 MB** |

Con el 1 GB gratis de KV caben **unas 15 personas** (los topes cortan antes; sin
tarjeta, nunca se paga nada). Operaciones: la primera subida son ~15 escrituras;
después, ~3 por importación con cambios → muy lejos de las 1.000 al día. Cada vez que se abre la web: 1 lectura (el
índice) si no hay nada nuevo. La primera vez el móvil baja ~50 MB: mejor con Wi-Fi.

### Lo que no cubre

- **Desplegado el 01/10/2026** en `https://guardados-sync.guardados-sync.workers.dev`
  (KV, plan gratis sin tarjeta) y la web publicada; probado de punta a punta en real. El límite de CPU del plan gratis (10 ms por petición) no se puede
  medir en local; el Worker solo hace un SHA-256 y pasa el cuerpo a KV.
- Si la persona borra `movil.json` o reinstala sin él, el buzón viejo se queda
  huérfano en la taquilla (cifrado; nadie tiene la llave). No hay caducidad
  automática todavía.
- El buzón no sabe quién es nadie: si alguien consigue el QR (foto de la
  pantalla), ve los guardados hasta que la persona pulse «Desconectar móviles».

## Decisión 10: ordenar mejor sin IA (01/10/2026)

Nacho: «que sea más preciso sin tener que usar inteligencia artificial». El
bibliotecario de la decisión 5 buscaba **trocitos de texto**: veía «cook» dentro
de «cookies», «etf» dentro de «netflix» (finanzas) y «bar» en «pull ups on the
bar» (bar de copas). Ahora **lee palabra a palabra**, como alguien con las gafas
puestas. Mismo árbol de carpetas, mismas listas de `rules.py` (compartido con
ig-saved, no se toca); cambia cómo se leen.

| Técnica | Qué arregla | Dónde (`carpetas.py`) |
|---|---|---|
| Minúsculas y sin acentos (NFKD, también letras «𝗔𝗻𝗶𝗺𝗲» de Instagram) | «PELÍCULA» = «pelicula» | `_norm` |
| Plural → singular **solo si el singular está en el diccionario** | «bares» = «bar», pero «care» no es «car» | `_raiz` |
| Palabra entera; «principio de palabra» solo con 5+ letras | «gin» ya no es «ginger», «etf» no es «netflix» | `_Termino` |
| Hashtags y @cuentas troceados (camelCase, `_`, `.` y diccionario) | `#pastarecipe` → pasta + recipe; `@dryaneats` → eats | `_piezas`, `_trocear` |
| Peso por sitio: hashtag 1,5 · descripción 1 · cuenta 1 · subtítulos 0,6; una palabra cuenta 2 veces como mucho | los subtítulos largos no se comen la descripción | `PESO`, `TOPE` |
| Palabras débiles (cuentan la mitad) | «history», «top», «food», «setup» no ganan a una palabra clara | `DEBILES` |
| Reglas de contexto | «ganar pasta» (dinero), «gato hidráulico» (coches), «borrar cookies» (webs), «ruta en coche» (viajes), «(1999)» (peli) | `CONTEXTO` |
| Señales de la cuenta | @…movies, @…eats, @…anime, @…recipes | `CUENTA` |
| Ciudad + comida sin pinta de receta → Sitios | «Top pizzas Madrid» ya no va a Recetas | `rutas`, `RECETA` |
| Diccionario ampliado ES/EN y subcarpetas limpias | dominadas, calistenia, ansiedad, matcha, n8n…; fuera « té » (sin acento es «te») y «uñas» («unas») | `AMPLIA`, `SUB_AMPLIA`, `SUB_KW` |
| Bug arreglado | `SITIO_FUERTE` tenía `re.I` global: «del restaurante con Matthew» contaba como «Restaurante Casa Pepe» | `SITIO_FUERTE` |
| Umbral y desempate fijos | mismo texto → mismas carpetas siempre (empate: el orden de `CARPETAS`) | `UMBRAL`, `rutas` |

Las palabras de las subcarpetas también empujan (a medias) a su carpeta: «press
banca» estaba en Entreno pero no en Fitness, y el vídeo acababa en Otros.

**Medido** (todo en local; los datos de Nacho solo se leen y no se copian):

| | Antes | Después |
|---|---|---|
| **Etiquetado a mano** (`tests/casos_carpetas.py`, 178 captions inventados ES/EN con trampas) — carpeta bien | 88 % | **98 %** |
| … carpeta + subcarpeta bien | 85 % | **97 %** |
| … precisión (de lo que mete en una carpeta, acierta) / cobertura (no lo deja en Otros) | 94 % / 88 % | 99 % / 98 % |
| … solo los 40 escritos al final y medidos una vez, sin afinar (`CASOS_NUEVOS`) | 85 % / 80 % | **92 % / 88 %** |
| **Contra las carpetas de Gemini de Nacho**, mitad «test» que no se miró (1.882) — carpeta igual | 71 % | **75 %** |
| … carpeta + subcarpeta exactas | 41 % | **46 %** |
| … con transcripción de Instagram | 71 % / 41 % | 76 % / 46 % |

Ojo con el 98 %: los primeros 138 casos se escribieron antes de tocar nada, pero
sus fallos sí se usaron para ampliar el diccionario. La cifra limpia es la de los
40 nuevos (92 %) y la de la mitad «test» de Gemini (75 %).

Lo que más mejora (mitad «test» de Gemini): **Anime** encuentra 61 % → 77 % y su
subcarpeta 41 % → 62 %; **Finanzas** 45 % → 67 % (y acierta 51 % → 60 %);
**Sitios** acierta 77 % → 83 % y su subcarpeta 60 % → 66 %. En el etiquetado a
mano: **Fitness** 29 % → 100 % de cobertura (dominadas, press banca, ansiedad),
**Coches** 50 % → 100 % y **Otros** deja de ser cajón de sastre (precisión 20 % → 100 %).
Lo que empeora: **Humor** baja en Gemini (encuentra 39 % → 34 %, acierta 40 % → 33 %): las páginas de
memes que suben trozos de pelis llevan `#meme` y Gemini, que ve el vídeo, dice «peli».

El suelo: `tests/test_precision.py` falla si el etiquetado a mano baja de 98 % /
96 % o la mitad «test» de Gemini de 74 % (este último solo corre si existe
`~/Projects/ig-saved/saved.db`). Para ver la tabla por carpeta y subcarpeta:
`.venv/bin/python tests/test_precision.py -v` y `.venv/bin/python tools/medir.py carpetas --todo`.

## Decisión 11: carpetas a mano (01/10/2026)

Nacho: «que una persona, si quiere añadir un vídeo a cierta carpeta, lo pueda
hacer manualmente». Como una **etiqueta escrita a boli sobre la impresa**: la
máquina puede reimprimir la suya cuantas veces quiera, la de boli no se borra.

- **Dónde se pulsa**: «Mis guardados» → abrir un vídeo → sección **Carpetas**
  (debajo de las etiquetas). Cada carpeta tiene su **×** para quitarla; el
  desplegable «Añadir a una carpeta…» lista todo el árbol (por grupos) y las
  carpetas propias; la última opción, **«＋ Carpeta nueva…»**, pide un nombre y
  si va suelta o **dentro de** otra (p. ej. Recetas › Cenas de domingo).
  «Volver a las carpetas automáticas» deshace lo manual. Al cerrar la ficha, la
  web se rehace con lo nuevo.
- **Se guarda aparte**: tabla `manual (code, rutas)` en `guardados.db`. Si un
  vídeo tiene fila ahí, `feed()` usa esa lista y no `posts.rutas`. Re-importar,
  los subtítulos, el mapa y la IA siguen escribiendo en `posts.rutas`, pero no se
  ve: lo manual manda (probado en `tests/test_manual.py` y en el selftest).
- **Llega al móvil** por la subida normal (`nube.py` sube el mismo `feed()`), con
  el mismo formato (`cat` y `sub`): una carpeta nueva es solo un nombre que la web
  no tiene en su lista, y lo pinta tal cual. La web del móvil no se ha tocado.
- **Cómo habla la ficha con el Mac**: «Mis guardados» no tiene `js_api` (a
  propósito, decisión 1). `server.py` engancha `web/mac/asignar.js` a
  `/guardados/index.html` con el token del arranque en un `<meta>`, y abre
  `/api/<token>/carpetas` y `/api/<token>/post/<code>`. Los POST exigen
  `Origin: http://127.0.0.1:47613` y JSON: Instagram o TikTok no pueden mandarlos
  (ni leer el token: otra web no puede leer páginas de este origen). Probado en
  el selftest (check «o» de `docs/seguridad.md`).
- **Nombres que escribe la persona**: solo letras, números, espacios, emojis y
  `- . ,`, hasta 40; nada de `< > " ' & / :` ni nombres que en JavaScript ya son
  otra cosa (`constructor`, `__proto__`…), ni `todo`/`ideas`. Si escribe una que
  ya existe («recetas», «Pelis y series») se usa esa. Se valida en el Mac al
  guardar y otra vez al mandar a la web (`carpetas.limpia_ruta`, `db._rutas_ok`),
  y la ficha pinta con `textContent`. El selftest intenta crear
  `<img src=x onerror=…>Trampa` desde la web y saltándose la web.
- No hay «carpeta vacía»: una carpeta existe mientras tenga algún vídeo (como las
  de la web). Tampoco se edita desde el móvil (es de solo lectura).

- **Arreglo de paso**: WebKit guarda IndexedDB por app (bundle id) y por origen, así
  que la prueba de seguridad, al usar el mismo puerto 47613 que la app instalada,
  dejaba sus 100 guardados falsos en «Mis guardados» de verdad. Ahora la prueba usa
  el 47615 (`tools/selftest.sh`) y el panel, al pasar los datos a la web, quita los
  que ya no están en la libreta del Mac (`podar` en `web/panel/panel.js`).
