r"""
selmo_image.py — local image generation via stable-diffusion.cpp [port 8086]
Pipeline: prompt -> stable-diffusion.cpp CLI (Z-Image-Turbo, Apache 2.0) -> PNG.

Everything stays on this machine. No model has a built-in content filter;
the only gate is the permissive license (manifesto rule). Apache 2.0 all the
way down: stable-diffusion.cpp (MIT runtime), Z-Image-Turbo weights (Apache 2.0),
Qwen3-4B text encoder (Apache 2.0), FLUX.1-schnell VAE (Apache 2.0).

VRAM note (RTX 4070 Ti 12 GB): the LLM (~10.5 GB) and the image model do NOT
fit on the GPU at the same time, so the CLI is launched with --offload-to-cpu:
weights live in system RAM and stream to the GPU per step. Slower, but it
coexists with a loaded llama-server. Drop the flag in selmo-models style if you
ever run image gen with no LLM loaded.

External binary (place in Selmo\bin\):
    sd-cli.exe  (or sd.exe) — stable-diffusion.cpp CUDA build
        https://github.com/leejet/stable-diffusion.cpp/releases

Model files (place in Selmo\image\):
    z_image_turbo-Q6_K.gguf          diffusion model (leejet/Z-Image-Turbo-GGUF)
    Qwen3-4B-Instruct-2507-Q4_K_M.gguf  text encoder (unsloth/Qwen3-4B-...-GGUF)
    ae.safetensors                   VAE (black-forest-labs/FLUX.1-schnell)

Installation (one time):
    pip install flask --break-system-packages

Usage:
    python selmo_image.py [--port 8086] [--steps 8] [--cfg 1.0] [--no-offload]
"""

import sys
import os
import time
import uuid
import shutil
import argparse
import logging
import threading
import subprocess
from pathlib import Path

try:
    from flask import Flask, request, Response, jsonify
except ImportError:
    print("Flask not found. Install with: pip install flask --break-system-packages")
    sys.exit(1)

# -- Arguments -----------------------------------------------------------------
parser = argparse.ArgumentParser(description="Selmo image bridge (stable-diffusion.cpp / Z-Image-Turbo)")
parser.add_argument("--port",  type=int,   default=8086)
parser.add_argument("--steps", type=int,   default=8,    help="Z-Image-Turbo is distilled to ~8 steps")
parser.add_argument("--cfg",   type=float, default=1.0,  help="Turbo models want cfg ~1.0 (no guidance)")
parser.add_argument("--no-offload", action="store_true",
                    help="Keep weights on the GPU (only if no LLM is loaded; needs the full ~8 GB free)")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("selmo_image")

# -- Paths ---------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BIN_DIR    = SCRIPT_DIR / "bin"
IMG_DIR    = SCRIPT_DIR / "image"
OUT_DIR    = IMG_DIR / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# stable-diffusion.cpp renamed the CLI from sd.exe to sd-cli.exe; accept either.
def _find_binary():
    env = os.environ.get("SELMO_SD")
    cands = ([Path(env)] if env else []) + [
        BIN_DIR / "sd-cli.exe", BIN_DIR / "sd.exe",
        BIN_DIR / "sd-cli",     BIN_DIR / "sd",
    ]
    for c in cands:
        if c and c.exists():
            return c
    found = shutil.which("sd-cli") or shutil.which("sd")
    return Path(found) if found else None

SD_BIN = _find_binary()

# Model components. Override any of them with SELMO_SD_DIFF / _LLM / _VAE.
DIFFUSION = Path(os.environ.get("SELMO_SD_DIFF", IMG_DIR / "z_image_turbo-Q6_K.gguf"))
TEXT_ENC  = Path(os.environ.get("SELMO_SD_LLM",  IMG_DIR / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"))
VAE       = Path(os.environ.get("SELMO_SD_VAE",  IMG_DIR / "ae.safetensors"))

# One generation at a time (the GPU/CPU can't run two diffusions in parallel).
_lock = threading.Lock()


def _missing():
    """Return a list of human-readable missing prerequisites, or []."""
    miss = []
    if SD_BIN is None:
        miss.append("sd-cli.exe (stable-diffusion.cpp) in bin\\")
    for label, p in (("diffusion model", DIFFUSION), ("text encoder", TEXT_ENC), ("VAE", VAE)):
        if not p.exists():
            miss.append(f"{label}: {p.name} in image\\")
    return miss


app = Flask(__name__)


@app.route("/status")
def status():
    miss = _missing()
    return jsonify({
        "ok": not miss,
        "engine": "stable-diffusion.cpp",
        "model": "Z-Image-Turbo",
        "binary": str(SD_BIN) if SD_BIN else None,
        "steps": args.steps,
        "cfg": args.cfg,
        "offload_to_cpu": not args.no_offload,
        "missing": miss,
    })


@app.route("/generate", methods=["OPTIONS"])
def generate_options():
    return "", 204


@app.route("/generate", methods=["POST"])
def generate():
    miss = _missing()
    if miss:
        return jsonify({"error": "Image generation not ready", "missing": miss}), 503

    data   = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    # img2img: an optional base64 init image + strength (0..1, higher = further
    # from the source). When an init image is present, the prompt is optional.
    init_b64 = data.get("init_image") or ""
    if not prompt and not init_b64:
        return jsonify({"error": "Field 'prompt' missing or empty"}), 400
    init_path = None
    if init_b64:
        try:
            import base64
            if init_b64.startswith("data:") and "," in init_b64:
                init_b64 = init_b64.split(",", 1)[1]
            init_path = OUT_DIR / f"{uuid.uuid4().hex}_init.png"
            init_path.write_bytes(base64.b64decode(init_b64))
        except Exception as e:
            return jsonify({"error": "bad init_image: %s" % e}), 400
    try:
        strength = float(data.get("strength")) if data.get("strength") not in (None, "") else 0.6
    except (TypeError, ValueError):
        strength = 0.6
    strength = max(0.05, min(1.0, strength))

    # Clamp geometry to sane, multiple-of-16 values; default 1024x1024.
    def _dim(v, d):
        try:
            v = int(v)
        except (TypeError, ValueError):
            v = d
        v = max(256, min(1536, v))
        return v - (v % 16)
    width  = _dim(data.get("width"),  1024)
    height = _dim(data.get("height"), 1024)
    steps  = max(1, min(50, int(data.get("steps") or args.steps)))
    cfg    = float(data.get("cfg") or args.cfg)
    seed   = data.get("seed")
    seed   = int(seed) if seed not in (None, "") else -1

    out_path = OUT_DIR / f"{uuid.uuid4().hex}.png"
    cmd = [
        str(SD_BIN),
        "--diffusion-model", str(DIFFUSION),
        "--llm",             str(TEXT_ENC),
        "--vae",             str(VAE),
        "-p",                prompt,
        "--cfg-scale",       str(cfg),
        "--steps",           str(steps),
        "-W",                str(width),
        "-H",                str(height),
        "--seed",            str(seed),
        "--diffusion-fa",
        "-o",                str(out_path),
    ]
    if init_path is not None:
        # New sd.cpp CLI: image gen is the default "img_gen" mode; supplying an
        # init image (not a "-M img2img" mode, which was removed) triggers img2img.
        cmd += ["--init-img", str(init_path), "--strength", str(strength)]
    if not args.no_offload:
        cmd.append("--offload-to-cpu")

    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    _mode = f"img2img s={strength} init={init_path.name}" if init_path is not None else "txt2img"
    log.info(f"{_mode} {width}x{height} steps={steps} cfg={cfg} seed={seed}: {prompt[:80]}")

    with _lock:
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=600, creationflags=NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            log.error("sd-cli timed out (>600s)")
            return jsonify({"error": "Generation timed out (>600s)"}), 504
        except Exception as e:
            log.error(f"sd-cli launch error: {e}")
            return jsonify({"error": str(e)}), 500

        if proc.returncode != 0 or not out_path.exists():
            tail = (proc.stderr or proc.stdout or "").strip()[-800:]
            log.error(f"sd-cli failed (rc={proc.returncode}): {tail}")
            return jsonify({"error": "Generation failed", "detail": tail}), 500

        png = out_path.read_bytes()
        dt  = time.time() - t0

    for _p in (out_path, init_path):
        try:
            if _p is not None:
                _p.unlink()
        except Exception:
            pass

    log.info(f"Done in {dt:.1f}s ({len(png)} bytes)")
    resp = Response(png, mimetype="image/png")
    resp.headers["X-Selmo-Gen-Seconds"] = f"{dt:.1f}"
    return resp


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Expose-Headers"] = "X-Selmo-Gen-Seconds"
    return resp


if __name__ == "__main__":
    log.info(f"Selmo image (stable-diffusion.cpp) listening on http://0.0.0.0:{args.port}")
    miss = _missing()
    if miss:
        log.warning("Not ready yet — missing: " + "; ".join(miss))
    # threaded=True so /status answers while a long generation holds the lock.
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
