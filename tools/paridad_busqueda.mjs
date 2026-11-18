// Paridad del buscador: ejecuta el search.js real de la web sobre busqueda-docs.json
// y apunta los 5 primeros (id y puntos) de 20 consultas fijas en busqueda-esperada.json.
// BuscadorTests.top5ComoSearchJS compara el Buscador de Swift con esto.
import { readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { buildIndex, search } from "../web/guardados/search.js";

const dir = `${homedir()}/Projects/ig-saved/paridad-swift`;
const rules = JSON.parse(readFileSync(new URL("../web/guardados/rules-data.json", import.meta.url)));
const posts = JSON.parse(readFileSync(`${dir}/busqueda-docs.json`));
// como app.js: las palabras clave sin los espacios de borde que usa rules.py
const kw = Object.fromEntries(Object.entries(rules.kw).map(([c, ks]) => [c, ks.map(k => k.trim())]));
const ix = buildIndex({ posts, kw });

const consultas = [
  "quiero un diseño tipo Apple", "ahorrar tokens", "receta de tarta de queso", "ramen madrid",
  "invertir en etf", "prácticas en banca de inversión", "pelis de terror", "anime recomendaciones",
  "automatizar con n8n", "agente de ia con memoria", "ejercicio en casa", "brunch chamberí",
  "outfit invierno", "videojuegos ps5", "memes gracioso", "cómo ganar dinero", "claude code",
  "viaje a japón", "sushi", "rutina de skincare",
];
const out = consultas.map(q => {
  const r = search(ix, q, { limit: 5 }).results;
  return { q, ids: r.map(x => x.p.id), puntos: r.map(x => x.score) };
});
writeFileSync(`${dir}/busqueda-esperada.json`, JSON.stringify(out, null, 1));
console.log(`${out.length} consultas → busqueda-esperada.json`);
