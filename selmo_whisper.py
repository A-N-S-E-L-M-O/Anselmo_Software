"""
selmo_whisper.py — Whisper locale via faster-whisper
Porta 8083. Pipeline: audio blob → trascrizione → testo.

Installazione (una volta sola):
    pip install faster-whisper flask --break-system-packages

Al primo avvio scarica il modello ~150MB (tiny) o ~500MB (small).
Il modello si può cambiare con --model (default: small).

Uso:
    python selmo_whisper.py [--model tiny|small|medium|large-v3]
"""

import sys
import os
import io
import tempfile
import argparse
import logging

# Flask
try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Flask non trovato. Installa con: pip install flask --break-system-packages")
    sys.exit(1)

# faster-whisper
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("faster-whisper non trovato. Installa con: pip install faster-whisper --break-system-packages")
    sys.exit(1)

# ── Argomenti ────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Selmo Whisper bridge")
parser.add_argument("--model", default="small",
                    help="Modello Whisper: tiny, base, small, medium, large-v3 (default: small)")
parser.add_argument("--port", type=int, default=8083)
parser.add_argument("--device", default="cpu",
                    help="cuda o cpu (default: cpu — per cuda serve cublas64_12.dll)")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("selmo_whisper")

# ── Caricamento modello ──────────────────────────────────────────
device = args.device
compute_type = "float16" if device == "cuda" else "int8"

log.info(f"Caricamento modello Whisper '{args.model}' su {device}...")
try:
    model = WhisperModel(args.model, device=device, compute_type=compute_type)
    log.info("Modello caricato.")
except Exception as e:
    if device == "cuda":
        log.warning(f"CUDA non disponibile ({e}), fallback a CPU...")
        device = "cpu"
        compute_type = "int8"
        model = WhisperModel(args.model, device=device, compute_type=compute_type)
        log.info("Modello caricato su CPU.")
    else:
        log.error(f"Errore caricamento modello: {e}")
        sys.exit(1)

# ── App Flask ────────────────────────────────────────────────────
app = Flask(__name__)

ALLOWED_EXTS = {".webm", ".wav", ".mp3", ".ogg", ".flac", ".m4a", ".mp4"}


@app.route("/status")
def status():
    return jsonify({
        "ok": True,
        "model": args.model,
        "device": device,
    })


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "Campo 'audio' mancante"}), 400

    f = request.files["audio"]
    filename = f.filename or "audio.webm"
    ext = os.path.splitext(filename)[1].lower() or ".webm"

    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"Formato non supportato: {ext}"}), 400

    # Salva in file temporaneo (faster-whisper vuole un path o file-like WAV)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            language="it",          # forza italiano
            vad_filter=True,        # salta silenzio
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        lang = info.language
        log.info(f"Trascritto ({lang}, {info.duration:.1f}s): {text[:80]}...")
        return jsonify({"text": text, "language": lang, "duration": round(info.duration, 2)})
    except Exception as e:
        log.error(f"Errore trascrizione: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── CORS (per accesso da chat.html su 8080) ──────────────────────
@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/transcribe", methods=["OPTIONS"])
def transcribe_options():
    return "", 204


if __name__ == "__main__":
    log.info(f"Selmo Whisper in ascolto su http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
