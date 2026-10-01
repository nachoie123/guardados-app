// «Mis guardados» en el Mac: meter un vídeo en una carpeta a mano (y sacarlo, o crear una nueva).
// Solo existe aquí: server.py lo engancha a /guardados/index.html con el token en un <meta>.
// La web del móvil es de solo lectura y le llega lo mismo por la sincronización normal.
// Todo nombre se pinta con textContent (nunca innerHTML) y el Mac vuelve a validarlo (carpetas.py).
import * as store from "/guardados/store.js";
import { makeRules } from "/guardados/rules.js";

const T = document.querySelector('meta[name="guardados-mac"]')?.content;
const sheet = document.getElementById("sheet");
const CODE = /^(tt_\d{6,30}|[A-Za-z0-9_-]{5,40})$/;
let arbol = null, nombres = {}, propias = [], actual = null, cambiado = false, turno = 0;

const api = (path, body) => fetch(`/api/${T}/${path}`, body === undefined ? { cache: "no-store" } : {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
  .then(async r => ({ status: r.status, ...(await r.json().catch(() => ({}))) }));
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };
const nombre = r => r.split("/").map(p => nombres[p] || p).join(" › ");

// --- la sección, debajo de las carpetas de la ficha ---
const lista = el("ul", { id: "d-carp-list" });
const elegir = el("select", { name: "ruta", ariaLabel: "Carpeta" });
const add = el("form", { className: "d-lug-add d-carp-add" }, elegir, el("button", { type: "submit", className: "btn-mini", textContent: "Añadir" }));
const nueva = el("input", { type: "text", name: "nombre", placeholder: "Nombre de la carpeta nueva", maxLength: 40, autocomplete: "off" });
const dentro = el("select", { name: "dentro", ariaLabel: "Dentro de" });
const crear = el("form", { className: "d-lug-add d-carp-add", hidden: true }, nueva, dentro,
  el("button", { type: "submit", className: "btn-mini", textContent: "Crear" }));
const msg = el("p", { className: "d-lug-msg", hidden: true });
const auto = el("button", { type: "button", className: "link", textContent: "Volver a las carpetas automáticas", hidden: true });
const sec = el("section", { className: "d-lug d-carp", id: "d-carp" },
  el("h3", { textContent: "Carpetas" }), lista, add, crear, auto, msg);

function avisa(t) { msg.textContent = t || ""; msg.hidden = !t; }

function pintaOpciones() {
  elegir.replaceChildren(el("option", { value: "", textContent: "Añadir a una carpeta…" }));
  dentro.replaceChildren(el("option", { value: "", textContent: "Carpeta suelta" }));
  for (const c of arbol) {
    if (c.k === "otros") continue;
    if (c.subs.length) elegir.append(el("optgroup", { label: c.n }, ...c.subs.map(s => el("option", { value: s.k, textContent: s.n }))));
    else elegir.append(el("option", { value: c.k, textContent: c.n }));
    dentro.append(el("option", { value: c.k, textContent: `Dentro de ${c.n}` }));
  }
  if (propias.length) elegir.append(el("optgroup", { label: "Tus carpetas" }, ...propias.map(r => el("option", { value: r, textContent: nombre(r) }))));
  for (const r of propias) if (!r.includes("/")) dentro.append(el("option", { value: r, textContent: `Dentro de ${r}` }));
  elegir.append(el("option", { value: "+", textContent: "＋ Carpeta nueva…" }));
}

function pinta(rutas, manual) {
  actual.rutas = rutas;
  lista.replaceChildren(...rutas.map(r => el("li", {},
    el("span", { className: "ico", textContent: "📁" }),
    el("span", { className: "l-main", textContent: nombre(r) }),
    r === "otros" ? "" : el("button", { type: "button", className: "l-x", ariaLabel: `Quitar de ${nombre(r)}`, textContent: "×", onclick: () => guarda(rutas.filter(x => x !== r)) }))));
  auto.hidden = !manual;
  // las etiquetas de arriba de la ficha (las de app.js), al día
  const chips = document.getElementById("d-cats");
  chips.replaceChildren(...[...new Set(rutas.map(r => r.split("/")[0]))].map(c => {
    const b = el("button", { type: "button", className: "chip", textContent: nombres[c] || c });
    b.dataset.cat = c;
    return b;
  }));
}

async function guarda(rutas, extra) {
  avisa("");
  const r = await api(`post/${encodeURIComponent(actual.id)}`, rutas === null ? { auto: true } : { rutas: rutas.length ? rutas : ["otros"] });
  if (!r.ok) return avisa(r.error || "No se ha podido guardar. ¿Sigue abierta la app?");
  cambiado = true;
  if (extra) { propias = (await api("carpetas")).propias || propias; pintaOpciones(); }
  pinta(r.rutas, r.manual);
}

add.addEventListener("submit", e => {
  e.preventDefault();
  const v = elegir.value;
  if (!v || v === "+") return;
  if (!actual.rutas.includes(v)) guarda(actual.rutas.filter(x => x !== "otros").concat(v));
  elegir.value = "";
});
elegir.addEventListener("change", () => {
  crear.hidden = elegir.value !== "+";
  if (!crear.hidden) nueva.focus();
});
crear.addEventListener("submit", e => {
  e.preventDefault();
  const n = nueva.value.trim().replace(/\s+/g, " ");
  if (!n) return nueva.focus();
  if (/[<>"'`&\/\\:]/.test(n)) return avisa("Ese nombre no vale: usa letras, números, espacios o emojis.");
  const r = dentro.value ? `${dentro.value}/${n}` : n;
  guarda(actual.rutas.filter(x => x !== "otros").concat(r), true).then(() => {
    if (msg.hidden) { nueva.value = ""; crear.hidden = true; elegir.value = ""; }
  });
});
auto.addEventListener("click", () => guarda(null));

async function abre() {
  const id = decodeURIComponent(location.hash.slice(1)), mio = ++turno;
  if (!CODE.test(id)) { sec.hidden = true; return; }
  if (!arbol) {
    const c = await api("carpetas");
    if (!c.arbol) return;
    arbol = c.arbol;
    for (const t of arbol) { nombres[t.k] = t.n; for (const s of t.subs) nombres[s.k.split("/")[1]] = s.n; }
    propias = c.propias || [];
    pintaOpciones();
  }
  const r = await api(`post/${encodeURIComponent(id)}`);
  if (mio !== turno) return;   // ya se abrió otra ficha
  if (!r.ok) { sec.hidden = true; return; }
  actual = { id };
  sec.hidden = false;
  crear.hidden = true; elegir.value = ""; avisa("");
  if (!sec.isConnected) document.getElementById("d-cats").after(sec);
  pinta(r.rutas, r.manual);
}

// al cerrar la ficha, si algo cambió: los datos nuevos a la web (IndexedDB, como hace el panel) y se repinta
async function refresca() {
  const feed = await (await fetch(`/feed/${T}/items.json`, { cache: "no-store" })).json();
  const parsed = store.parseFile(feed);
  if (parsed?.items.length) await store.importItems(parsed, makeRules(await (await fetch("/guardados/rules-data.json")).json()));
  location.reload();
}

if (T && sheet) {
  new MutationObserver(() => { if (sheet.open) abre(); }).observe(sheet, { attributes: true, attributeFilter: ["open"] });
  new MutationObserver(() => { if (sheet.open) abre(); }).observe(document.getElementById("d-title"), { childList: true });
  sheet.addEventListener("close", () => { if (cambiado) { cambiado = false; refresca(); } });
}
