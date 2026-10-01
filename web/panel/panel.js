// Panel de la app. Habla con Python (window.pywebview.api) y, cuando entra algo
// nuevo, lo mete en la web de guardados con el mismo store.js que usa
// nachosanbenito.com/guardados (mismo origen = mismo IndexedDB que "Mis guardados").
import * as store from "/guardados/store.js";
import { makeRules } from "/guardados/rules.js";

const $ = id => document.getElementById(id);
// Todo lo que viene de Instagram/TikTok (nombres, captions) pasa por aquí antes de ir a HTML.
export const esc = s => String(s ?? "").replace(/[&<>"'`]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" })[c]);
const fmt = n => new Intl.NumberFormat("es-ES").format(n || 0);
const ago = t => {
  if (!t) return "nunca";
  const m = Math.round((Date.now() / 1000 - t) / 60);
  return m < 1 ? "ahora mismo" : m < 60 ? `hace ${m} min` : m < 1440 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} días`;
};

let api, rules, lastVersion = -1, pushing = false, feedURL = null;

// --- barra de progreso: una fila por etapa. Todo con textContent (nada de HTML con datos). ---
const tiempo = s => s < 60 ? "menos de un minuto" : s < 90 * 60 ? `unos ${Math.round(s / 60)} min`
  : `unas ${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min`;
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
export function stageText(g) {
  const u = g.unidad || "guardados";
  const num = g.total ? `${fmt(g.done)} de ${fmt(g.total)} ${u}` : `${fmt(g.done)} ${u}`;
  let sub;
  if (g.state === "ok") sub = "Hecho" + (g.msg ? ` · ${g.msg}` : "");
  else if (g.state === "stop") sub = "Parado. Seguirá donde se quedó.";
  else if (g.state === "error") sub = g.msg || "Ha fallado. Se reintentará.";
  else if (g.total) {
    const ritmo = g.rate_min ? ` · va a ${fmt(Math.round(g.rate_min))} por minuto` : "";
    sub = (g.eta != null ? `Quedan ${tiempo(g.eta)}` : "Calculando cuánto falta…") + ritmo;
  } else {
    // Instagram no dice cuántos guardados hay: no se inventa un total
    sub = (g.k === "ig" ? "Instagram no dice cuántos tienes: la barra se llena al terminar" : "Contando…")
      + (g.rate_min ? ` · va a ${fmt(Math.round(g.rate_min))} por minuto` : "");
  }
  if (g.state === "run" && g.msg) sub += ` · ${g.msg}`;
  const pct = g.state === "ok" ? 100 : g.total ? Math.min(100, Math.round(100 * g.done / g.total)) : null;
  return { num, sub, pct };
}
// las filas se reutilizan (por etapa): así la barra se desliza y la animación no se reinicia cada 1,5 s
const rows = new Map();
function renderStages(list) {
  const box = $("stages");
  box.hidden = !list?.length;
  const keep = new Set();
  for (const g of list || []) {
    keep.add(g.k);
    let r = rows.get(g.k);
    if (!r) {
      r = { row: el("div", "stage"), name: el("b"), num: el("span", "st-num"), bar: el("div", "bar"), fill: el("span"), sub: el("div", "st-sub") };
      const top = el("div", "st-top");
      top.append(r.name, r.num);
      r.bar.setAttribute("role", "progressbar");
      r.bar.append(r.fill);
      r.row.append(top, r.bar, r.sub);
      rows.set(g.k, r);
    }
    const { num, sub, pct } = stageText(g);
    r.row.className = "stage" + (g.state === "error" ? " err" : "");
    r.name.textContent = g.label;
    r.num.textContent = num;
    r.sub.textContent = sub;
    r.bar.className = "bar" + (g.state === "ok" ? " ok" : pct == null && g.state === "run" ? " indet" : "");
    r.bar.setAttribute("aria-label", g.label);
    if (pct != null) r.bar.setAttribute("aria-valuenow", String(pct)); else r.bar.removeAttribute("aria-valuenow");
    r.fill.style.width = pct != null && g.state !== "ok" ? pct + "%" : "";
    box.append(r.row);  // en el orden que manda Python
  }
  for (const [k, r] of rows) if (!keep.has(k)) { r.row.remove(); rows.delete(k); }
}
function renderIA(x) {
  const st = $("ia-state");
  st.className = "small " + (x.error ? "bad" : x.has_key ? "on" : "");
  st.textContent = x.error ? x.error : x.has_key
    ? `Clave guardada ✓ · ${fmt(x.done)} de ${fmt(x.total)} guardados afinados con IA`
    : "Sin clave: todo con reglas.";
  $("ia-del").hidden = !x.has_key;
}

// --- el móvil: el QR solo llega aquí cuando la persona lo pide; nunca va en status() ---
let qrTimer = null, resetArmed = false;
function renderMovil(m) {
  const st = $("movil-state");
  st.className = "small " + (m.error ? "bad" : m.subido ? "on" : "");
  st.textContent = !m.on ? "Sin móvil conectado."
    : m.error ? m.error
    : m.subiendo ? "Subiendo lo nuevo al móvil…"
    : m.subido ? `Móvil al día ✓ · ${fmt(m.posts)} guardados y ${fmt(m.covers)} portadas (${String(m.mb).replace(".", ",")} MB cifrados) · ${ago(m.subido)}`
    : "Preparando tu buzón cifrado…";
  $("movil-reset").hidden = !m.on;
  $("movil-qr").textContent = m.on ? "Enseñar el código otra vez" : "Conectar el móvil";
}
function showQR(r) {
  if (!r?.ok) { $("movil-state").className = "small bad"; $("movil-state").textContent = r?.error || "No he podido preparar el código."; return; }
  $("qr").src = r.qr;
  $("qr-box").hidden = false;
  clearTimeout(qrTimer);
  qrTimer = setTimeout(hideQR, 5 * 60 * 1000);   // que no se quede en pantalla
}
function hideQR() { $("qr-box").hidden = true; $("qr").removeAttribute("src"); }

// «Mis guardados» del Mac enseña lo que hay en este Mac: lo que ya no está en su libreta (p. ej. los
// guardados falsos que dejaba la prueba de seguridad cuando usaba el mismo puerto) se quita de la web.
async function podar(ids) {
  if (!ids.size) return;
  const d = await new Promise((ok, mal) => { const r = indexedDB.open("guardados"); r.onsuccess = () => ok(r.result); r.onerror = () => mal(r.error); });
  const tx = d.transaction(["posts", "covers"], "readwrite");
  const keys = await new Promise(ok => { const q = tx.objectStore("posts").getAllKeys(); q.onsuccess = () => ok(q.result); });
  for (const k of keys) if (!ids.has(k)) { tx.objectStore("posts").delete(k); tx.objectStore("covers").delete(k); }
  await new Promise((ok, mal) => { tx.oncomplete = ok; tx.onerror = tx.onabort = () => mal(tx.error); });
  d.close();
}

async function pushToWeb() {
  if (pushing || !feedURL) return;
  pushing = true;
  try {
    const json = await (await fetch(feedURL, { cache: "no-store" })).json();
    const parsed = store.parseFile(json);
    if (parsed?.items.length) {
      const r = await store.importItems(parsed, rules);
      await podar(new Set(parsed.items.map(i => i.code)));
      $("web").textContent = `En "Mis guardados": ${fmt(r.total)} (${fmt(r.isNew)} nuevos en esta pasada, ${fmt(r.covers)} portadas).`;
      await api.reload_viewer();
    }
  } catch (e) {
    $("web").textContent = "No he podido pasar los datos a la web: " + e;
  } finally { pushing = false; }
}

function render(s) {
  feedURL = s.feed;
  for (const k of ["ig", "tt"]) {
    const x = s[k], el = $(k + "-sess");
    el.className = "sess " + (x.session ? "on" : "off");
    el.textContent = x.session === null ? "Abriendo la ventana…" : x.session ? "Sesión iniciada ✓" : "Sin sesión: inicia sesión en su ventana";
    const n = s.counts[k === "ig" ? "instagram" : "tiktok"] || { n: 0, covers: 0, tr: 0 };
    $(k + "-stat").textContent = `${fmt(n.n)} importados · ${fmt(n.covers)} portadas · con texto ${fmt(n.tr)} · última vez: ${ago(x.last_ok)}` + (x.pending ? " · a medias, se reanudará" : "");
  }
  const t = s.task;
  $("note").textContent = t.running ? t.note || "Trabajando…" : t.note || (s.whisper ? "Listo para importar" : "Listo para importar (sin transcripción de Instagram en esta versión)");
  $("err").hidden = !t.error;
  $("err").textContent = t.error || "";
  $("stop").hidden = !t.running;
  document.querySelectorAll("[data-imp]").forEach(b => { b.disabled = t.running; });
  renderStages(s.progress);
  if (s.ia) renderIA(s.ia);
  if (s.movil) renderMovil(s.movil);
  $("recent").innerHTML = s.recent.map(p => `<li><span class="t">${esc(p.title || p.caption || "(sin texto)")}</span>
    <span class="u">${p.src === "tiktok" ? "TikTok" : "Instagram"} · @${esc(p.username)}${p.fullname ? " · " + esc(p.fullname) : ""} · ${esc(p.category || "")}</span></li>`).join("")
    || `<li class="mute">Aún nada. Inicia sesión y espera unos segundos.</li>`;
  if (s.version !== lastVersion && !t.running) { lastVersion = s.version; pushToWeb(); }
}

async function tick() {
  try { render(await api.status()); } catch (e) { $("note").textContent = "Error: " + e; }
  setTimeout(tick, 1500);
}

document.addEventListener("click", async e => {
  const b = e.target.closest("button");
  if (!b || !api) return;
  if (b.dataset.show) api.show(b.dataset.show);
  else if (b.dataset.imp) api.import_now(b.dataset.imp);
  else if (b.id === "stop") api.stop();
  else if (b.id === "open-viewer") { await pushToWeb(); api.show("viewer"); }
  else if (b.id === "ia-save") guardarClave();
  else if (b.id === "ia-del") { await api.delete_gemini_key(); render(await api.status()); }
  else if (b.id === "movil-qr") showQR(await api.movil_qr());
  else if (b.id === "qr-hide") hideQR();
  else if (b.id === "movil-reset") {
    // dos toques: el primero avisa, el segundo cambia la llave
    if (!resetArmed) {
      resetArmed = true; b.textContent = "¿Seguro? Los móviles conectados dejarán de recibir. Pulsa otra vez"; b.classList.add("danger");
      setTimeout(() => { resetArmed = false; b.textContent = "Desconectar móviles y cambiar la llave"; b.classList.remove("danger"); }, 6000);
      return;
    }
    resetArmed = false; b.textContent = "Desconectar móviles y cambiar la llave"; b.classList.remove("danger");
    showQR(await api.movil_cambiar());
    $("movil-state").textContent = "Llave cambiada. Los móviles de antes ya no reciben nada: escanea el código nuevo.";
  }
});

async function guardarClave() {
  const inp = $("ia-key"), k = inp.value.trim();
  inp.value = "";            // que la clave no se quede en la página
  if (!k) return;
  const r = await api.set_gemini_key(k);
  $("ia-state").className = "small " + (r?.ok ? "on" : "bad");
  $("ia-state").textContent = r?.ok ? "Clave guardada ✓. Afinando carpetas y mapa…" : (r?.error || "No se ha podido guardar.");
}
document.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.id === "ia-key") guardarClave(); });

async function start() {
  api = window.pywebview.api;
  rules = makeRules(await (await fetch("/guardados/rules-data.json")).json());
  window.__panelReady = true;
  tick();
}
if (window.pywebview?.api?.status) start();
else window.addEventListener("pywebviewready", start, { once: true });
