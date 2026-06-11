"""
selmo_whisper.py — local Whisper via faster-whisper
Port 8083. Pipeline: audio blob → transcription → text.

Installation (one time only):
    pip install faster-whisper flask --break-system-packages

On first launch it downloads the model ~150MB (tiny) or ~500MB (small).
The model can be changed with --model (default: small).

Usage:
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
    print("Flask not found. Install with: pip install flask --break-system-packages")
    sys.exit(1)

# faster-whisper
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("faster-whisper not found. Install with: pip install faster-whisper --break-system-packages")
    sys.exit(1)

# ── Arguments ────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Selmo Whisper bridge")
parser.add_argument("--model", default="small",
                    help="Whisper model: tiny, base, small, medium, large-v3 (default: small)")
parser.add_argument("--port", type=int, default=8083)
parser.add_argument("--device", default="cpu",
                    help="cuda or cpu (default: cpu — cuda needs cublas64_12.dll)")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("selmo_whisper")

# ── Model loading ────────────────────────────────────────────────
device = args.device
compute_type = "float16" if device == "cuda" else "int8"

log.info(f"Loading Whisper model '{args.model}' on {device}...")
try:
    model = WhisperModel(args.model, device=device, compute_type=compute_type)
    log.info("Model loaded.")
except Exception as e:
    if device == "cuda":
        log.warning(f"CUDA not available ({e}), falling back to CPU...")
        device = "cpu"
        compute_type = "int8"
        model = WhisperModel(args.model, device=device, compute_type=compute_type)
        log.info("Model loaded on CPU.")
    else:
        log.error(f"Model loading error: {e}")
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
        return jsonify({"error": "Field 'audio' missing"}), 400

    f = request.files["audio"]
    filename = f.filename or "audio.webm"
    ext = os.path.splitext(filename)[1].lower() or ".webm"

    if ext not in ALLOWED_EXTS:
        return jsonify({"error": f"Unsupported format: {ext}"}), 400

    # Save to a temporary file (faster-whisper wants a path or WAV file-like object)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            language=None,          # auto-detect language
            vad_filter=True,        # skip silence
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        lang = info.language
        log.info(f"Transcribed ({lang}, {info.duration:.1f}s): {text[:80]}...")
        return jsonify({"text": text, "language": lang, "duration": round(info.duration, 2)})
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── CORS (for access from chat.html on 8080) ─────────────────────
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
    log.info(f"Selmo Whisper listening on http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
