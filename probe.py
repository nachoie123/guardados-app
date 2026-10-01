"""Sonda contra Instagram y TikTok REALES (GUARDADOS_PROBE=<fichero>).

No importa nada ni guarda guardados: pide UNA página de cada API desde las
ventanas (con la sesión que haya) y apunta solo la forma de la respuesta
(status, tipo de contenido, si es JSON, cuántos items, qué campos llegan).
Si no hay sesión, espera hasta 10 minutos a que la persona inicie sesión.

  tools/probe.sh
"""
import json
import os
import time
from pathlib import Path

import importer


def _shape_ig(r):
    items = r.get("items") or []
    first = items[0] if items else {}
    return {k: r.get(k) for k in ("status", "ctype", "json", "html", "msg", "more", "raw_n")} | {
        "n_items": len(items), "has_next": bool(r.get("next")),
        "campos_con_valor": sorted(k for k, v in first.items() if v not in (None, "", [], 0)),
        "trae_saved_collection_ids": any(i.get("cols") for i in items),
        "trae_video_url": sum(1 for i in items if i.get("video_url")),
        "trae_portada": sum(1 for i in items if i.get("thumb")),
        "head_si_no_json": r.get("head"),
    }


def _shape_tt(r):
    items = r.get("items") or []
    return {k: r.get(k) for k in ("status", "ctype", "json", "empty", "html", "code", "more", "total")} | {
        "n_items": len(items), "has_next": bool(r.get("next")),
        "con_subtitulos": sum(1 for i in items if i.get("subs")),
        "con_portada": sum(1 for i in items if i.get("thumb")),
        "head_si_no_json": r.get("head"),
    }


def run(out, api):
    res = {"at": time.strftime("%Y-%m-%d %H:%M:%S")}
    ig, tt = api.pages["ig"], api.pages["tt"]
    t0 = time.time()
    while time.time() - t0 < int(os.environ.get("GUARDADOS_PROBE_WAIT", "600")):
        s = getattr(api, "_sess", {})
        if s.get("ig") and s.get("tt"):
            break
        time.sleep(3)
    res["sesion"] = dict(getattr(api, "_sess", {}))
    try:
        r = ig.run(importer.IG_PAGE_JS % {"url": json.dumps("/api/v1/feed/saved/posts/?count=50"),
                                          "app": importer.IG_APP_ID, "host": json.dumps(importer.IG_HOST)})
        res["instagram"] = _shape_ig(r) if isinstance(r, dict) else {"raro": str(r)[:200]}
    except Exception as e:
        res["instagram"] = {"error": repr(e)}
    try:
        who = tt.run(importer.TT_WHO_JS % {"deep": "true", "hostre": json.dumps(importer.TT_HOST_RE)})
        sec = (who or {}).get("sec")
        res["tiktok_secUid"] = bool(sec)
        if sec:
            url = ("/api/user/collect/item_list/?aid=1988&app_name=tiktok_web&device_platform=web_pc&count=30&secUid="
                   + importer._q(sec) + "&cursor=0")
            r = tt.run(importer.TT_PAGE_JS % {"url": json.dumps(url), "hostre": json.dumps(importer.TT_HOST_RE)})
            res["tiktok_sin_firma"] = _shape_tt(r) if isinstance(r, dict) else {"raro": str(r)[:200]}
    except Exception as e:
        res["tiktok"] = {"error": repr(e)}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    import webview
    for w in list(webview.windows):
        w.destroy()
