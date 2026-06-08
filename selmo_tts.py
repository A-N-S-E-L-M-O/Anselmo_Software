"""
selmo_tts.py — TTS locale via Kokoro-ONNX (MIT/Apache 2.0)
Porta 8084. Pipeline: testo → Kokoro → WAV → risposta HTTP.

Installazione (una volta sola):
    pip install kokoro-onnx soundfile flask --break-system-packages

File modello richiesti (scarica e metti in Selmo\tts\):
    kokoro-v1.0.onnx  → https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
    voices-v1.0.bin   → https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Voci italiane disponibili:
    if_sara   — voce femminile (default)
    im_nicola — voce maschile

Uso:
    python selmo_tts.py [--voice if_sara] [--speed 1.0] [--port 8084]
"""

import sys
import os
import io
import re
import argparse
import logging
import numpy as np
try:
    from langdetect import detect as _langdetect
    LANGDETECT_OK = True
except ImportError:
    LANGDETECT_OK = False

try:
    from flask import Flask, request, Response, jsonify
except ImportError:
    print("Flask non trovato. Installa con: pip install flask --break-system-packages")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    print("soundfile non trovato. Installa con: pip install soundfile --break-system-packages")
    sys.exit(1)

try:
    from kokoro_onnx import Kokoro
except ImportError:
    print("kokoro-onnx non trovato. Installa con: pip install kokoro-onnx --break-system-packages")
    sys.exit(1)

# ── Argomenti ─────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Selmo TTS bridge (Kokoro-ONNX)")
parser.add_argument("--voice", default="if_sara",
                    help="Voce Kokoro: if_sara (F) o im_nicola (M) (default: if_sara)")
parser.add_argument("--speed", type=float, default=1.0,
                    help="Velocità parlato (default: 1.0)")
parser.add_argument("--port", type=int, default=8084)
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("selmo_tts")

# ── Percorso modelli ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(SCRIPT_DIR, "tts")
ONNX_PATH = os.path.join(TTS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(TTS_DIR, "voices-v1.0.bin")

if not os.path.exists(ONNX_PATH) or not os.path.exists(VOICES_PATH):
    log.error("File modello mancanti nella cartella tts/")
    log.error(f"  Attesi: {ONNX_PATH}")
    log.error(f"          {VOICES_PATH}")
    log.error("Scarica da: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0")
    sys.exit(1)

# ── Caricamento modello ───────────────────────────────────────────
log.info(f"Caricamento Kokoro ONNX (voce={args.voice})...")
try:
    kokoro = Kokoro(ONNX_PATH, VOICES_PATH)
    log.info("Kokoro pronto.")
except Exception as e:
    log.error(f"Errore caricamento Kokoro: {e}")
    sys.exit(1)


# Mappa langdetect → codice lingua Kokoro
LANG_MAP = {
    'it': 'it', 'en': 'en-us', 'fr': 'fr-fr',
    'de': 'de', 'es': 'es', 'pt': 'pt-br',
    'ja': 'ja', 'zh-cn': 'zh', 'ko': 'ko',
}

def detect_lang(text):
    if not LANGDETECT_OK:
        return 'it'
    try:
        return LANG_MAP.get(_langdetect(text), 'it')
    except Exception:
        return 'it'

# ── App Flask ─────────────────────────────────────────────────────
app = Flask(__name__)


def clean_text(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@app.route("/status")
def status():
    return jsonify({
        "ok": True,
        "engine": "kokoro-onnx",
        "voice": args.voice,
        "speed": args.speed,
    })


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    voice = data.get("voice", args.voice)
    speed = float(data.get("speed", args.speed))

    if not text:
        return jsonify({"error": "Campo 'text' mancante o vuoto"}), 400

    text = clean_text(text)
    if not text:
        return jsonify({"error": "Testo vuoto dopo pulizia"}), 400

    log.info(f"Sintesi ({voice}, speed={speed}): {text[:80]}...")
    try:
        lang = data.get("lang") or detect_lang(text)
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format='WAV', subtype='PCM_16')
        buf.seek(0)
        return Response(buf.read(), mimetype="audio/wav")
    except Exception as e:
        log.error(f"Errore sintesi: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/speak", methods=["OPTIONS"])
def speak_options():
    return "", 204


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


if __name__ == "__main__":
    log.info(f"Selmo TTS (Kokoro-ONNX) in ascolto su http://0.0.0.0:{args.port}")
    log.info(f"Voce: {args.voice} | Velocità: {args.speed}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=False)
