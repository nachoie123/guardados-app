#!/usr/bin/python3
"""Apple Maps FALSO para las pruebas (selftest y tests): mismo formato que tools/geo.swift.
Contesta al instante y sin internet. Un nombre con "Trampa" vuelve con un nombre hostil
(<img onerror>) para comprobar que la web lo escapa."""
import json
import sys
import zlib

EVIL = '<img src=x onerror="window.__pwned=(window.__pwned||0)+1">Bar Trampa'
for q in json.loads(sys.stdin.read() or "[]"):
    text = q.get("q", "")
    if q.get("ciudad"):
        print(json.dumps({"id": q["id"], "ok": True, "c": [{"name": text, "lat": 40.4168, "lng": -3.7038, "addr": "",
                                                            "city": text, "poi": False, "calle": False}]}))
        continue
    if "Nada" in text:
        print(json.dumps({"id": q["id"], "ok": False, "err": "sin resultados", "vacio": True}))
        continue
    name = text.split(",")[0].strip()
    h = zlib.crc32(name.encode()) % 1000 / 100000
    cat = "MKPOICategoryNightlife" if ("Bar" in name or "Trampa" in name) else "MKPOICategoryRestaurant"
    print(json.dumps({"id": q["id"], "ok": True, "c": [{"name": EVIL if "Trampa" in name else name, "lat": 40.42 + h,
                                                        "lng": -3.70 - h, "addr": "Calle Falsa 123", "city": "Madrid",
                                                        "country": "ES", "poi": True, "calle": True, "cat": cat}]}))
    sys.stdout.flush()
