"""La barra de progreso del panel, como el marcador de una carrera.

Cada etapa (Instagram, TikTok, portadas, transcripción, mapa, IA) apunta cuántos
lleva y, si se sabe, cuántos hay. El ritmo se MIDE (cuántos entraron en el
último minuto, contando pausas y esperas), no se supone; de ahí sale el tiempo
que falta. Si no se sabe el total (Instagram no lo da) no se inventa: la barra
va "en movimiento" y se dice el ritmo.
"""
import threading
import time

ORDEN = ["ig", "tt", "covers", "tr", "geo", "ia"]
NOMBRE = {"ig": "Instagram", "tt": "TikTok", "covers": "Portadas", "tr": "Transcripción",
          "geo": "Mapa (Apple Maps)", "ia": "IA (Gemini)"}
VENTANA = 90  # segundos de historia para medir el ritmo


class Progreso:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.st = {}

    def start(self, k, total=None, done=0, unidad="guardados"):
        with self.lock:
            t = self.clock()
            self.st[k] = {"k": k, "label": NOMBRE.get(k, k), "done": int(done), "total": total, "state": "run",
                          "unidad": unidad, "t0": t, "hist": [(t, int(done))], "msg": ""}

    def update(self, k, done=None, total=None, add=0, msg=None):
        with self.lock:
            s = self.st.get(k)
            if not s:
                return
            if done is not None:
                s["done"] = int(done)
            s["done"] += add
            if total is not None:
                s["total"] = int(total) if total else None
            if msg is not None:
                s["msg"] = str(msg)[:120]
            t = self.clock()
            s["hist"].append((t, s["done"]))
            s["hist"] = [h for h in s["hist"] if t - h[0] <= VENTANA] or [(t, s["done"])]

    def finish(self, k, state="ok", msg=""):
        with self.lock:
            s = self.st.get(k)
            if s:
                s["state"], s["msg"] = state, str(msg)[:160]

    def clear(self):
        with self.lock:
            self.st = {}

    def _rate(self, s, t):
        h = s["hist"]
        if len(h) >= 2 and h[-1][1] > h[0][1]:
            # desde la primera muestra de la ventana hasta AHORA (si lleva rato parado, el ritmo baja)
            return (h[-1][1] - h[0][1]) / max(t - h[0][0], 1e-6)
        el = t - s["t0"]
        return s["done"] / el if el > 5 and s["done"] else None

    def snapshot(self):
        t = self.clock()
        out = []
        with self.lock:
            for k in ORDEN + [k for k in self.st if k not in ORDEN]:
                s = self.st.get(k)
                if not s:
                    continue
                rate = self._rate(s, t) if s["state"] == "run" else None
                eta = None
                if s["state"] == "run" and s["total"] and rate:
                    eta = max(0, (s["total"] - s["done"]) / rate)
                out.append({"k": k, "label": s["label"], "done": s["done"], "total": s["total"], "state": s["state"],
                            "unidad": s["unidad"], "msg": s["msg"], "elapsed": round(t - s["t0"]),
                            "rate_min": round(rate * 60, 1) if rate else None,
                            "eta": round(eta) if eta is not None else None})
        return out
