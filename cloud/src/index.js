// Buzón de Guardados (Cloudflare Worker + KV, plan gratis SIN tarjeta).
//
// KV y no R2: R2 pide un medio de pago y no tiene tope de gasto; KV en el plan gratis
// no puede cobrar nada. Si se pasa (1 GB, 1.000 escrituras o 100.000 lecturas al día),
// Cloudflare rechaza la operación y ya está.
//
// Es una taquilla de consigna: guarda cajas cerradas con candado (bytes cifrados
// con AES-GCM en el Mac de cada persona) y se las da a quien enseñe el resguardo.
// La llave del candado no pasa nunca por aquí: va en el fragmento (#) del enlace
// del QR, que el navegador no manda al servidor. Ver ../docs/diseno.md, decisión 9.
//
//   PUT    /v1/<id>          crea el buzón. Cuerpo {"w": sha256(escritura), "r": sha256(lectura)} en hex
//   DELETE /v1/<id>          lo borra entero               (Authorization: Bearer <token de escritura>)
//   PUT    /v1/<id>/<obj>    sube un objeto (index.bin o <16 hex>.bin)   (escritura)
//   DELETE /v1/<id>/<obj>    borra un objeto                             (escritura)
//   GET    /v1/<id>/<obj>    lo baja                       (Authorization: Bearer <token de lectura>)
//
// El servidor solo guarda el hash de cada token. Nada de console.log: no hay
// registro de contenidos ni de tokens (y la observabilidad va apagada en wrangler.toml).

const ID = /^[A-Za-z0-9_-]{43}$/;              // 32 bytes aleatorios en base64url
const OBJ = /^(index|[0-9a-f]{16})\.bin$/;
const HEX64 = /^[0-9a-f]{64}$/;
const META = id => `m/${id}`;                  // las credenciales (hashes) de cada buzón
const OBJS = id => `o/${id}/`;                 // sus cajas: o/<id>/index.bin, o/<id>/<16 hex>.bin

const num = (v, d) => (Number.isFinite(+v) && +v > 0 ? +v : d);

function limits(env) {
  return {
    obj: num(env.MAX_OBJETO, 25e6),            // por subida (un paquete de portadas o los datos); KV admite 25 MiB
    buzon: num(env.MAX_BUZON, 60e6),           // por persona
    buzones: num(env.MAX_BUZONES, 15),         // 15 × 60 MB = 900 MB: por debajo del 1 GB gratis de KV
  };
}

function cors(req, env) {
  const origin = req.headers.get("Origin");
  if (!origin) return { ok: true, h: {} };     // la app del Mac (Python) no manda Origin
  const allowed = (env.ORIGENES || "").split(",").map(s => s.trim()).filter(Boolean);
  if (!allowed.includes(origin)) return { ok: false, h: {} };
  return {
    ok: true,
    h: {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "GET",   // desde un navegador solo se lee
      "Access-Control-Allow-Headers": "Authorization",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    },
  };
}

function out(status, body, extra = {}) {
  const h = {
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    ...extra,
  };
  return new Response(body ?? String(status), { status, headers: h });
}

async function sha256hex(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function sameHex(a, b) {                       // comparación en tiempo constante
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let x = 0;
  for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
}

async function tokenOk(req, hash) {
  const m = /^Bearer ([A-Za-z0-9_-]{20,100})$/.exec(req.headers.get("Authorization") || "");
  return !!m && sameHex(await sha256hex(m[1]), hash);
}

// Lo que ocupa un buzón va en su propia ficha (m/<id>): sz = {objeto: bytes}. La lista de KV
// tarda hasta un minuto en enseñar lo recién subido, así que no sirve para el tope; la ficha
// se lee al momento en el mismo sitio donde se escribió. KV solo deja reescribir la misma
// clave una vez por segundo: si dos subidas caen en el mismo segundo, la segunda espera.
async function guardarFicha(env, id, meta) {
  for (let i = 0; ; i++) {
    try { return await env.KV.put(META(id), JSON.stringify(meta)); }
    catch (e) { if (i >= 3) throw e; await new Promise(r => setTimeout(r, 1100)); }
  }
}

// Para borrar el buzón entero: la ficha y, por si acaso, la lista (lo que la ficha no nombre).
async function objetos(env, id, meta) {
  const keys = new Set(Object.keys(meta.sz || {}).map(o => `${OBJS(id)}${o}`));
  let cursor;
  do {
    const l = await env.KV.list({ prefix: OBJS(id), cursor });
    l.keys.forEach(k => keys.add(k.name));
    cursor = l.list_complete ? undefined : l.cursor;
  } while (cursor);
  return [...keys];
}

async function contarBuzones(env) {
  let n = 0, cursor;
  do {
    const l = await env.KV.list({ prefix: "m/", cursor });
    n += l.keys.length;
    cursor = l.list_complete ? undefined : l.cursor;
  } while (cursor);
  return n;
}

async function handle(req, env) {
  const c = cors(req, env);
  if (!c.ok) return out(403, "origen no permitido");
  const H = c.h;
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: H });
  // un navegador solo puede leer; subir y borrar es cosa del Mac
  if (req.headers.get("Origin") && req.method !== "GET") return out(403, "solo lectura", H);

  const url = new URL(req.url);
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] !== "v1" || !ID.test(parts[1] || "") || parts.length > 3) return out(404, null, H);
  const id = parts[1], obj = parts[2];
  if (obj !== undefined && !OBJ.test(obj)) return out(404, null, H);
  const L = limits(env);

  const meta = await env.KV.get(META(id), "json");

  // --- crear el buzón ---
  if (obj === undefined && req.method === "PUT") {
    if (meta) return out(409, "ya existe", H);
    const len = +req.headers.get("Content-Length");
    if (!(len > 0 && len < 400)) return out(400, null, H);
    let b;
    try { b = await req.json(); } catch { return out(400, null, H); }
    if (!HEX64.test(b?.w || "") || !HEX64.test(b?.r || "") || b.w === b.r) return out(400, null, H);
    if ((await contarBuzones(env)) >= L.buzones) return out(507, "no caben más buzones", H);
    await env.KV.put(META(id), JSON.stringify({ w: b.w, r: b.r, t: Date.now(), sz: {} }));
    return out(201, "creado", H);
  }

  if (!meta) return out(404, "sin buzón", H);

  // --- leer ---
  if (req.method === "GET") {
    if (!obj) return out(404, null, H);
    if (!(await tokenOk(req, meta.r))) return out(401, null, H);
    const o = await env.KV.getWithMetadata(`${OBJS(id)}${obj}`, { type: "arrayBuffer" });
    if (!o.value) return out(404, "aún no está", H);   // el buzón existe pero el Mac no lo ha subido (todavía)
    return new Response(o.value, {
      status: 200,
      headers: { ...H, "Content-Type": "application/octet-stream", "Content-Length": String(o.value.byteLength),
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" },
    });
  }

  // a partir de aquí, solo con el token de escritura
  if (!(await tokenOk(req, meta.w))) return out(401, null, H);

  if (req.method === "DELETE" && obj === undefined) {
    for (const k of await objetos(env, id, meta)) await env.KV.delete(k);
    await env.KV.delete(META(id));
    return out(200, "borrado", H);
  }

  const key = `${OBJS(id)}${obj}`;
  if (req.method === "DELETE") {
    await env.KV.delete(key);
    const sz = { ...(meta.sz || {}) };
    delete sz[obj];
    await guardarFicha(env, id, { ...meta, sz });
    return out(200, "borrado", H);
  }

  if (req.method === "PUT") {
    const len = +req.headers.get("Content-Length");
    if (!Number.isInteger(len) || len <= 0) return out(411, null, H);
    if (len > L.obj) return out(413, "demasiado grande", H);
    const sz = { ...(meta.sz || {}) };
    const used = Object.entries(sz).reduce((n, [o, b]) => n + (o === obj ? 0 : +b || 0), 0);
    if (used + len > L.buzon) return out(507, "buzón lleno", H);
    const body = await req.arrayBuffer();
    if (body.byteLength !== len) return out(400, null, H);
    sz[obj] = len;
    await guardarFicha(env, id, { ...meta, sz });   // primero la cuenta: si falla, no queda nada sin contar
    await env.KV.put(key, body);
    return out(201, "guardado", H);
  }

  return out(405, null, H);
}

export default {
  async fetch(req, env) {
    try {
      return await handle(req, env);
    } catch {
      return out(500, "error");                // sin detalles: nada del contenido sale en la respuesta
    }
  },
};
