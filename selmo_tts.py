"""
selmo_tts.py — local TTS via Kokoro-ONNX (MIT/Apache 2.0)
Port 8084. Pipeline: text → Kokoro → WAV → HTTP response.

Installation (one time only):
    pip install kokoro-onnx soundfile flask --break-system-packages

Required model files (download and place in Selmo\tts\):
    kokoro-v1.0.onnx  → https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
    voices-v1.0.bin   → https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Available Italian voices:
    if_sara   — female voice (default)
    im_nicola — male voice

Usage:
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
    print("Flask not found. Install with: pip install flask --break-system-packages")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    print("soundfile not found. Install with: pip install soundfile --break-system-packages")
    sys.exit(1)

try:
    from kokoro_onnx import Kokoro
except ImportError:
    print("kokoro-onnx not found. Install with: pip install kokoro-onnx --break-system-packages")
    sys.exit(1)

# ── Arguments ─────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Selmo TTS bridge (Kokoro-ONNX)")
parser.add_argument("--voice", default="if_sara",
                    help="Kokoro voice: if_sara (F) or im_nicola (M) (default: if_sara)")
parser.add_argument("--speed", type=float, default=1.0,
                    help="Speech speed (default: 1.0)")
parser.add_argument("--port", type=int, default=8084)
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("selmo_tts")

# ── Model path ────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.join(SCRIPT_DIR, "tts")
ONNX_PATH = os.path.join(TTS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(TTS_DIR, "voices-v1.0.bin")

if not os.path.exists(ONNX_PATH) or not os.path.exists(VOICES_PATH):
    log.error("Model files missing in the tts/ folder")
    log.error(f"  Expected: {ONNX_PATH}")
    log.error(f"          {VOICES_PATH}")
    log.error("Download from: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0")
    sys.exit(1)

# ── Model loading ─────────────────────────────────────────────────
log.info(f"Loading Kokoro ONNX (voice={args.voice})...")
try:
    kokoro = Kokoro(ONNX_PATH, VOICES_PATH)
    log.info("Kokoro ready.")
except Exception as e:
    log.error(f"Kokoro loading error: {e}")
    sys.exit(1)


# Map langdetect → Kokoro language code
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

# Default Kokoro voice per detected language + gender. Used ONLY when the text
# is in a different language than the user's chosen --voice, so their pick (and
# its gender) is respected for its own language.
VOICE_BY_LANG = {
    "it":    {"f": "if_sara",  "m": "im_nicola"},
    "en-us": {"f": "af_sarah", "m": "am_michael"},
}

# Kokoro voice names encode language (1st char) + gender (2nd char): e.g.
# im_nicola = Italian male, af_sarah = American-English female.
_VOICE_LANG = {"i": "it", "a": "en-us", "b": "en-us", "f": "fr-fr",
               "e": "es", "p": "pt-br", "j": "ja", "z": "zh", "h": "hi"}

def _voice_lang(v):
    return _VOICE_LANG.get((v or "")[:1].lower(), "")

def _voice_gender(v):
    g = (v or "  ")[1:2].lower()
    return g if g in ("f", "m") else "f"

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

    if not text:
        return jsonify({"error": "Field 'text' missing or empty"}), 400

    text = clean_text(text)
    if not text:
        return jsonify({"error": "Text empty after cleanup"}), 400

    # Language follows the TEXT (models often answer in another language than the
    # UI). Detect it, then pick a matching voice + a small Italian speed bump --
    # unless the client passed an explicit override.
    lang  = data.get("lang") or detect_lang(text)
    # Respect the user's chosen voice for ITS language; only switch (keeping the
    # same gender) when the text is in a different language.
    if data.get("voice"):
        voice = data["voice"]
    elif _voice_lang(args.voice) == lang:
        voice = args.voice
    else:
        vmap  = VOICE_BY_LANG.get(lang)
        voice = (vmap.get(_voice_gender(args.voice)) if vmap else None) or args.voice
    _spd  = data.get("speed")
    speed = float(_spd) if _spd is not None else args.speed * (1.10 if lang == "it" else 1.0)

    log.info(f"Synthesis ({voice}, speed={speed:.2f}, lang={lang}): {text[:80]}...")
    try:
        samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format='WAV', subtype='PCM_16')
        buf.seek(0)
        return Response(buf.read(), mimetype="audio/wav")
    except Exception as e:
        log.error(f"Synthesis error: {e}")
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
    # Loopback only: reached via the front door /proxy/8084, not directly. (security review)
    log.info(f"Selmo TTS (Kokoro-ONNX) listening on http://127.0.0.1:{args.port}")
    log.info(f"Voice: {args.voice} | Speed: {args.speed}")
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=False)
