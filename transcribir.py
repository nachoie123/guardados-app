"""Transcripción de los reels de Instagram con faster-whisper, SI está instalado.

Igual que transcribe.py de ig-saved (modelo `small`, int8, en el Mac). En la app
empaquetada (universal2) faster-whisper NO va dentro: ctranslate2 y PyAV no
tienen ruedas universal2 y el modelo pesa ~460 MB. Ahí este paso se salta y lo
dice; TikTok sí trae texto (sus propios subtítulos, que baja importer.py).
Los enlaces de vídeo de IG caducan en horas: se transcribe justo tras importar.
"""
import os
import ssl
import tempfile
import urllib.request

import certifi

import media

MODEL = os.environ.get("IG_WHISPER_MODEL", "small")
MAX_VIDEO = 120_000_000


def available():
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


class Transcriber:
    def __init__(self, db, note=lambda s: None):
        self.db, self.note, self.model = db, note, None

    def _load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            self.note(f"Cargando whisper {MODEL} (la primera vez lo descarga)…")
            self.model = WhisperModel(MODEL, device="cpu", compute_type="int8")
        return self.model

    def text(self, path):
        segs, info = self._load().transcribe(path, beam_size=1, vad_filter=True, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segs).strip(), info.language

    def run(self, should_stop=lambda: False, prog=None):
        if not available():
            return {"skipped": "faster-whisper no está en esta app"}
        todo = self.db.pending_transcripts()
        done = 0
        if prog and todo:
            prog.start("tr", len(todo), 0, "vídeos")
        ctx = ssl.create_default_context(cafile=certifi.where())
        for i, (code, url) in enumerate(todo, 1):
            if should_stop():
                break
            if not media.allowed(url, "instagram"):
                continue
            self.note(f"Transcribiendo {i}/{len(todo)}…")
            if prog:
                prog.update("tr", done=i - 1)
            fd, path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": media.UA, "Referer": media.REFERER["instagram"]})
                with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open(path, "wb") as f:
                    if not (r.headers.get("Content-Type") or "").startswith("video/"):
                        continue
                    f.write(r.read(MAX_VIDEO))
                text, lang = self.text(path)
                self.db.set_transcript(code, text, lang)
                done += 1
            except Exception as e:  # enlace caducado (403), red…: se queda sin texto
                self.note(f"Sin transcripción para {code}: {type(e).__name__}")
                self.db.set_transcript(code, "", "?")  # no reintentar cada vez: el enlace ya no vale
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
        if prog and todo:
            prog.update("tr", done=len(todo))
            prog.finish("tr", "ok")
        return {"done": done, "total": len(todo)}
