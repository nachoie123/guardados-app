"""Traer lo guardado de Instagram y lo favorito de TikTok, como un recadero.

El recadero (este módulo) no tiene llaves de nadie: le pide a la ventana de
Instagram o de TikTok, donde la persona ya ha iniciado sesión, que haga la
llamada ella misma (fetch dentro de la página, con su sesión). Él solo apunta
lo que vuelve en la libreta (db.py), va despacio y, si se corta, sabe por qué
página iba.

- Instagram: /api/v1/feed/saved/posts/?count=50&max_id=…  (X-IG-App-ID 936619743392459)
- TikTok:    /api/user/collect/item_list/?…&secUid=…      (sin firma, como el marcador)

Incremental: se para tras 15 conocidos seguidos (un guardado viejo que vuelves a
guardar sube arriba sin ser nuevo). Reanudable: el cursor de la página siguiente
se apunta en kv tras guardar cada página; si la app se cierra, la próxima vez
sigue desde ahí. Pausas de 1-3 s entre páginas; reintentos ante 429 (esperas de
1, 2, 3… min) y ante fallos de red ("Load failed", tiempo agotado: 10, 20… s).
"""
import json
import random
import time

import db as dbmod

IG_APP_ID = "936619743392459"
# Dónde tiene que estar la ventana para que la app le pida algo (selftest los cambia por un servidor falso).
IG_HOST = "www.instagram.com"
TT_HOST_RE = r"(^|\.)tiktok\.com$"
STREAK_STOP = 15
MAX_PAGES = 400
TRIES = 6


class NoSession(Exception):
    pass


class Blocked(Exception):
    """La web devolvió algo que no es lo esperado (HTML, firma, 4xx…)."""


# ---------------------------------------------------------------- JS en la página
# Se ejecuta DENTRO de la ventana de Instagram/TikTok. Devuelve texto JSON con
# los campos mínimos (la página de 50 guardados en crudo pesa megas). Lo que
# vuelve se trata como dato no fiable: Python lo valida todo otra vez.

IG_PAGE_JS = r"""
if (location.hostname !== %(host)s) return JSON.stringify({wrong_host: location.hostname});
const ck = Object.fromEntries(document.cookie.split('; ').filter(Boolean).map(c => [c.slice(0, c.indexOf('=')), c.slice(c.indexOf('=') + 1)]));
if (!ck.ds_user_id) return JSON.stringify({no_session: true});
let r, t;
try {
  r = await fetch(%(url)s, {credentials: 'include', headers: {'X-IG-App-ID': '%(app)s', 'X-Requested-With': 'XMLHttpRequest'}});
  t = await r.text();
} catch (e) { return JSON.stringify({neterr: String(e && e.message || e)}); }
const ctype = r.headers.get('content-type') || '';
let j = null; try { j = JSON.parse(t); } catch (e) {}
if (!j) return JSON.stringify({status: r.status, ctype, html: /<html|<!doctype/i.test(t.slice(0, 600)), head: t.slice(0, 120)});
const pick = m => { const c = ((m.image_versions2 || (m.carousel_media && m.carousel_media[0] && m.carousel_media[0].image_versions2) || {}).candidates) || [];
  const ok = c.filter(x => x.width >= 320).sort((a, b) => a.width - b.width); return (ok[0] || c[0] || {}).url || null; };
const items = (j.items || []).map(i => i.media || i).filter(m => m && m.code).map(m => ({
  code: m.code, pk: m.pk_id || (typeof m.id === 'string' ? m.id.split('_')[0] : String(m.pk || '')),
  user: m.user && m.user.username, name: m.user && m.user.full_name, caption: (m.caption && m.caption.text) || '',
  taken_at: m.taken_at, type: m.media_type, product: m.product_type, likes: m.like_count,
  plays: m.play_count || m.ig_play_count || 0, video_url: (m.video_versions && m.video_versions[0] && m.video_versions[0].url) || null,
  thumb: pick(m), cols: m.saved_collection_ids || []}));
return JSON.stringify({status: r.status, ctype, json: true, msg: j.message || null, items,
  more: !!j.more_available, next: j.next_max_id || null, raw_n: (j.items || []).length});
"""

IG_WHO_JS = r"""
const ck = Object.fromEntries(document.cookie.split('; ').filter(Boolean).map(c => [c.slice(0, c.indexOf('=')), c.slice(c.indexOf('=') + 1)]));
return JSON.stringify({host: location.hostname, uid: ck.ds_user_id || null});
"""

TT_WHO_JS = r"""
if (!new RegExp(%(hostre)s).test(location.hostname)) return JSON.stringify({host: location.hostname, sec: null});
const pick = t => { try { const u = JSON.parse(t).__DEFAULT_SCOPE__['webapp.app-context'].user; return u && u.secUid || null; } catch (e) { return null; } };
let sec = null;
const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
if (el) sec = pick(el.textContent);
if (!sec && %(deep)s) {
  try {
    const h = await (await fetch('/', {credentials: 'include'})).text();
    const m = h.match(/<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([\s\S]*?)<\/script>/);
    if (m) sec = pick(m[1]);
  } catch (e) {}
}
return JSON.stringify({host: location.hostname, sec});
"""

TT_PAGE_JS = r"""
if (!new RegExp(%(hostre)s).test(location.hostname)) return JSON.stringify({wrong_host: location.hostname});
let r, t;
try { r = await fetch(%(url)s, {credentials: 'include'}); t = await r.text(); }
catch (e) { return JSON.stringify({neterr: String(e && e.message || e)}); }
const ctype = r.headers.get('content-type') || '';
let j = null; try { j = JSON.parse(t); } catch (e) {}
if (!j) return JSON.stringify({status: r.status, ctype, empty: !t.length, html: /<html|<!doctype/i.test(t.slice(0, 600)), head: t.slice(0, 120)});
const items = (j.itemList || []).filter(m => m && m.id).map(m => { const ip = m.imagePost; return {
  id: String(m.id), user: (m.author && m.author.uniqueId) || '', name: (m.author && m.author.nickname) || '',
  caption: [ip && ip.title, m.desc].filter(Boolean).join('\n'), taken_at: m.createTime || null, photo: !!ip,
  plays: +((m.statsV2 && m.statsV2.playCount) || (m.stats && m.stats.playCount) || 0),
  thumb: (m.video && m.video.cover) || (ip && ip.cover && ip.cover.imageURL && ip.cover.imageURL.urlList && ip.cover.imageURL.urlList[0]) || null,
  lang: m.textLanguage || '',
  subs: ((m.video && m.video.subtitleInfos) || []).map(s => ({u: s.Url, l: s.LanguageCodeName || '', s: s.Source || ''}))}; });
return JSON.stringify({status: r.status, ctype, json: true, code: j.statusCode || 0, items,
  more: !!j.hasMore, next: j.cursor ? String(j.cursor) : null, total: j.total || null});
"""

# Subtítulos de TikTok (su propio ASR): el CDN solo deja leerlos desde tiktok.com (CORS).
TT_SUBS_JS = r"""
const vtt = t => [...new Set(t.split(/\r?\n/).filter(l => l.trim() && !/-->|^WEBVTT|^\d+$|^NOTE/.test(l.trim())).map(l => l.replace(/<[^>]+>/g, '').trim()))].join(' ').slice(0, 3000);
const out = {};
await Promise.all(%(jobs)s.map(async ([id, u]) => { try { const r = await fetch(u); if (r.ok) out[id] = vtt(await r.text()); } catch (e) {} }));
return JSON.stringify(out);
"""


def _pause(sleep):
    sleep(1 + random.random() * 2)  # 1-3 s, como una persona pasando páginas


class Importer:
    """pages = {"ig": ventana, "tt": ventana}; ventana.run(js) -> dict. db: db.DB. note(str): avisa al panel.
    on_new(list[(code, thumb, headers)]): portadas nuevas para bajar ya (caducan)."""

    def __init__(self, db, pages, note=lambda s: None, sleep=time.sleep, on_covers=lambda items: None, prog=None):
        self.db, self.pages, self.note, self.sleep, self.on_covers = db, pages, note, sleep, on_covers
        self.prog = prog or _NoProg()
        self.stop = False

    # ---------- llamada con reintentos ----------
    def _call(self, page, js, what):
        for attempt in range(TRIES):
            if self.stop:
                raise InterruptedError("parado")
            try:
                r = page.run(js)
            except TimeoutError:
                r = {"neterr": "timeout"}
            except Exception as e:  # evaluate_js roto, ventana recargando…
                r = {"neterr": str(e)[:120]}
            if not isinstance(r, dict):
                r = {"neterr": "respuesta rara"}
            if r.get("wrong_host"):
                raise NoSession(f"La ventana de {what} está en otra web ({r['wrong_host']}). Vuelve a {what}.")
            if r.get("no_session"):
                raise NoSession(f"Inicia sesión en la ventana de {what}.")
            if r.get("neterr"):
                wait = 10 * (attempt + 1)
                self.note(f"{what}: fallo de red ({r['neterr'][:40]}), reintento en {wait}s…")
                self.sleep(wait)
                continue
            if r.get("status") == 429:
                wait = 60 * (attempt + 1)
                self.note(f"{what} pide calma (429): espero {wait}s…")
                self.sleep(wait)
                continue
            return r
        raise Blocked(f"{what} no responde tras {TRIES} intentos. Se reanudará donde se quedó.")

    # ---------- Instagram ----------
    def instagram(self):
        st = self.db.get("ig.run") or {}
        resumed = bool(st.get("cursor"))
        known = self.db.known("instagram")
        cursor = st.get("cursor") or ""
        streak, pages, new, seen = st.get("streak", 0), st.get("pages", 0), st.get("new", 0), st.get("seen", 0)
        self.note("Instagram: reanudo donde me quedé…" if resumed else "Instagram: leyendo tus guardados…")
        self.prog.start("ig", None, seen)
        while pages < MAX_PAGES:
            url = "/api/v1/feed/saved/posts/?count=50" + ("&max_id=" + _q(cursor) if cursor else "")
            r = self._call(self.pages["ig"], IG_PAGE_JS % {"url": json.dumps(url), "app": IG_APP_ID, "host": json.dumps(IG_HOST)}, "Instagram")
            if not r.get("json"):
                if r.get("status") in (401, 403) or r.get("html"):
                    raise NoSession("Instagram devuelve HTML o pide login: inicia sesión en su ventana."
                                    f" (status {r.get('status')}, {r.get('ctype')})")
                raise Blocked(f"Instagram respondió {r.get('status')} sin JSON")
            if r.get("status") != 200:
                if r.get("msg") in ("login_required", "checkpoint_required"):
                    raise NoSession(f"Instagram: {r['msg']}. Entra en su ventana y repite.")
                raise Blocked(f"Instagram respondió {r.get('status')}: {r.get('msg')}")
            fresh = []
            stop = False
            for it in r.get("items") or []:
                code = it.get("code")
                if not dbmod.valid_code(code) or code.startswith("tt_"):
                    continue
                seen += 1
                if code in known:
                    streak += 1
                    if streak >= STREAK_STOP:
                        stop = True
                        break
                    continue
                streak = 0
                it["url"] = f"https://www.instagram.com/p/{code}/"
                if self.db.add(it):
                    new += 1
                    known.add(code)
                    fresh.append((code, it.get("thumb")))
            pages += 1
            nxt = r.get("next") if r.get("more") else None
            done = stop or not nxt or not isinstance(nxt, str)
            # se apunta DESPUÉS de guardar la página: si se corta aquí, se repite esta como mucho
            self.db.put("ig.run", None if done else {"cursor": nxt, "streak": streak, "pages": pages, "new": new,
                                                     "seen": seen})
            self.on_covers([(c, t, "instagram") for c, t in fresh if t])
            self.prog.update("ig", done=seen)
            self.note(f"Instagram: {new} nuevos ({pages} páginas)")
            if done:
                break
            cursor = nxt
            _pause(self.sleep)
        self.db.put("ig.last_ok", int(time.time()))
        self.prog.finish("ig", "ok", f"{new} nuevos")
        return {"new": new, "pages": pages, "resumed": resumed}

    # ---------- TikTok ----------
    def tiktok(self):
        who = self._call(self.pages["tt"], TT_WHO_JS % {"deep": "true", "hostre": json.dumps(TT_HOST_RE)}, "TikTok")
        sec = who.get("sec")
        if not isinstance(sec, str) or not sec or len(sec) > 200:
            raise NoSession("Inicia sesión en la ventana de TikTok (y recarga la página si ya lo hiciste).")
        st = self.db.get("tt.run") or {}
        resumed = bool(st.get("cursor")) and st.get("sec") == sec
        cursor = st.get("cursor") if resumed else "0"
        streak, pages, new, seen, total = (st.get("streak", 0), st.get("pages", 0), st.get("new", 0), st.get("seen", 0),
                                           st.get("total")) if resumed else (0, 0, 0, 0, None)
        known = self.db.known("tiktok")
        self.note("TikTok: reanudo donde me quedé…" if resumed else "TikTok: leyendo tus favoritos…")
        self.prog.start("tt", total, seen, "favoritos")
        base = ("/api/user/collect/item_list/?aid=1988&app_name=tiktok_web&device_platform=web_pc&count=30&secUid="
                + _q(sec) + "&cursor=")
        while pages < MAX_PAGES:
            r = self._call(self.pages["tt"], TT_PAGE_JS % {"url": json.dumps(base + _q(cursor)), "hostre": json.dumps(TT_HOST_RE)}, "TikTok")
            if not r.get("json"):
                hint = "vacía (pide firma X-Bogus)" if r.get("empty") else ("HTML" if r.get("html") else "sin JSON")
                raise Blocked(f"TikTok respondió {r.get('status')} {hint}.")
            if r.get("code"):
                raise Blocked(f"TikTok respondió statusCode {r.get('code')} (sesión caducada o firma).")
            if isinstance(r.get("total"), int) and 0 < r["total"] < 10_000_000:
                total = r["total"]
            fresh = []
            stop = False
            for m in r.get("items") or []:
                seen += 1
                tid = str(m.get("id") or "")
                code = "tt_" + tid
                if not dbmod.valid_code(code):
                    continue
                if code in known:
                    streak += 1
                    if streak >= STREAK_STOP:
                        stop = True
                        break
                    continue
                streak = 0
                user = m.get("user") if isinstance(m.get("user"), str) and dbmod.TT_USER.match(m.get("user") or "") else ""
                item = {"code": code, "user": user, "name": m.get("name"), "caption": m.get("caption"),
                        "taken_at": m.get("taken_at"), "type": 1 if m.get("photo") else 2, "plays": m.get("plays"),
                        "url": f"https://www.tiktok.com/@{user or '_'}/{'photo' if m.get('photo') else 'video'}/{tid}",
                        "thumb": m.get("thumb"), "product": "tiktok"}
                item["tr"] = ""
                if self.db.add(item):
                    new += 1
                    known.add(code)
                    fresh.append((code, m))
            # subtítulos de los nuevos, de 4 en 4, desde la propia página
            jobs = [(c, _pick_sub(m)) for c, m in fresh]
            jobs = [(c, u) for c, u in jobs if u]
            for k in range(0, len(jobs), 4):
                try:
                    got = self.pages["tt"].run(TT_SUBS_JS % {"jobs": json.dumps(jobs[k:k + 4])}) or {}
                except Exception:
                    got = {}
                for c, text in (got.items() if isinstance(got, dict) else []):
                    if dbmod.valid_code(c) and isinstance(text, str) and text:
                        self.db.set_transcript(c, text[:3000], "")
                self.sleep(0.3)
            pages += 1
            nxt = r.get("next") if r.get("more") else None
            done = stop or not nxt or nxt == cursor
            self.db.put("tt.run", None if done else {"cursor": nxt, "sec": sec, "streak": streak, "pages": pages, "new": new,
                                                     "seen": seen, "total": total})
            self.on_covers([(c, m.get("thumb"), "tiktok") for c, m in fresh if m.get("thumb")])
            self.prog.update("tt", done=seen, total=total)
            self.note(f"TikTok: {new} nuevos ({pages} páginas)")
            if done:
                break
            cursor = nxt
            _pause(self.sleep)
        self.db.put("tt.last_ok", int(time.time()))
        self.prog.finish("tt", "ok", f"{new} nuevos")
        return {"new": new, "pages": pages, "resumed": resumed}


class _NoProg:
    def start(self, *a, **k):
        pass

    update = finish = start


def _pick_sub(m):
    subs = [s for s in (m.get("subs") or []) if isinstance(s, dict) and isinstance(s.get("u"), str)
            and s["u"].startswith("https://")]
    if not subs:
        return None
    lang = (m.get("lang") or "")[:2]
    for test in (lambda s: s["l"].startswith(lang) and s["s"] == "ASR" if lang else False,
                 lambda s: s["l"].startswith(lang) if lang else False,
                 lambda s: s["l"][:3] in ("spa", "es-", "eng", "en-") or s["l"][:2] in ("es", "en")):
        for s in subs:
            if test(s):
                return s["u"]
    return subs[0]["u"]


def _q(s):
    from urllib.parse import quote
    return quote(str(s), safe="")
