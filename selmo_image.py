r"""
selmo_image.py — local image generation via stable-diffusion.cpp [port 8086]
Pipeline: prompt -> stable-diffusion.cpp CLI (Z-Image-Turbo, Apache 2.0) -> PNG.

Everything stays on this machine. No model has a built-in content filter;
the only gate is the permissive license (manifesto rule). Apache 2.0 all the
way down: stable-diffusion.cpp (MIT runtime), Z-Image-Turbo weights (Apache 2.0),
Qwen3-4B text encoder (Apache 2.0), FLUX.1-schnell VAE (Apache 2.0).

VRAM note (RTX 4070 Ti 12 GB): the LLM (~10.5 GB) and the image model do NOT
fit on the GPU at the same time. By default the bridge asks the tray control
API (8087) to UNLOAD the LLM before generating, so the image model gets the
whole GPU at full speed; the next chat reloads the LLM lazily. If that
coordination is unavailable it falls back to --offload-to-cpu (weights stream
from RAM, slower, but coexists with a loaded llama-server). --no-swap forces the
offload fallback; --no-offload forces GPU and skips coordination entirely.

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
import json
import time
import uuid
import shlex
import shutil
import argparse
import logging
import threading
import subprocess
import urllib.request
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
                    help="Force weights on the GPU and skip LLM coordination (assumes no LLM loaded)")
parser.add_argument("--no-swap", action="store_true",
                    help="Never ask the tray to unload the LLM; always stream from RAM (--offload-to-cpu)")
args = parser.parse_args()

# Tray control API (selmo_tray.py): lets us free the GPU by unloading the LLM
# before generating, then the next chat reloads it lazily. Same machine, so
# 127.0.0.1 regardless of how the client reached this bridge.
CTRL_URL = os.environ.get("SELMO_CTRL", "http://127.0.0.1:8087")

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
        # the Install-Image add-on keeps sd.cpp isolated in bin\sd\ (its bundled
        # ggml-*.dll would otherwise clash with llama.cpp's in bin\); prefer it.
        BIN_DIR / "sd" / "sd-cli.exe", BIN_DIR / "sd" / "sd.exe",
        BIN_DIR / "sd-cli.exe",        BIN_DIR / "sd.exe",
        BIN_DIR / "sd-cli",            BIN_DIR / "sd",
    ]
    for c in cands:
        if c and c.exists():
            return c
    found = shutil.which("sd-cli") or shutil.which("sd")
    return Path(found) if found else None

SD_BIN = _find_binary()

# ---------------------------------------------------------------------------
# Model selection (v0.831): which generative model + parameters to run is chosen
# at startup in the tray's two-column picker, which writes selmo-image-config.json
#   { name, diffusion, files, params }
# - diffusion : absolute path to the diffusion weights (the menu pick)
# - files     : FIXED companion flags (text encoder + VAE), from the image ini
# - params    : EDITABLE tuning flags (--steps / --cfg-scale)
# If the config file is absent we fall back to the old hard-coded Z-Image-Turbo
# layout (and SELMO_SD_DIFF / _LLM / _VAE overrides), so nothing breaks.
# ---------------------------------------------------------------------------
CONFIG_FILE = SCRIPT_DIR / "selmo-image-config.json"


def _load_model():
    diff = os.environ.get("SELMO_SD_DIFF") or str(IMG_DIR / "z_image_turbo-Q6_K.gguf")
    enc  = os.environ.get("SELMO_SD_LLM")  or str(IMG_DIR / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf")
    vae  = os.environ.get("SELMO_SD_VAE")  or str(IMG_DIR / "ae.safetensors")
    name   = Path(diff).name
    files  = f'--llm "{enc}" --vae "{vae}"'
    params = f"--steps {args.steps} --cfg-scale {args.cfg}"
    offload = ""   # "always" -> stream from RAM even on a freed GPU (big models)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            diff    = cfg.get("diffusion") or diff
            files   = cfg.get("files", files)
            params  = cfg.get("params", params)
            name    = cfg.get("name") or Path(diff).name
            offload = cfg.get("offload", offload)
        except Exception as e:
            log.warning(f"bad {CONFIG_FILE.name} ({e}); using built-in default model")
    return {"name": name, "diffusion": diff, "files": files, "params": params,
            "offload": offload}


MODEL = _load_model()

# sd-cli flags the bridge manages itself; stripped from files/params if present.
_SD_BOOL   = {"--offload-to-cpu", "--diffusion-fa"}
_SD_VALUED = {"--diffusion-model", "-p", "--prompt", "-W", "--width", "-H",
              "--height", "--seed", "-o", "--output", "--init-img",
              "--strength", "-M", "--mode"}


def _strip_struct(tokens):
    """Drop flags the bridge controls (geometry, prompt, output, offload, fa)."""
    out, i = [], 0
    while i < len(tokens):
        t = tokens[i]
        if t in _SD_BOOL:
            i += 1
        elif t in _SD_VALUED:
            i += 2
        else:
            out.append(t)
            i += 1
    return out


# One generation at a time (the GPU/CPU can't run two diffusions in parallel).
_lock = threading.Lock()


def _missing():
    """Return a list of human-readable missing prerequisites, or []."""
    miss = []
    if SD_BIN is None:
        miss.append("sd-cli.exe (stable-diffusion.cpp) in bin\\")
    if not Path(MODEL["diffusion"]).exists():
        miss.append(f"diffusion model: {Path(MODEL['diffusion']).name} in image\\")
    return miss


def _llm_unload() -> bool:
    """
    Ask the tray (8087) to unload the LLM so the image model gets the whole GPU.
    Returns True when the GPU is free (run with no offload); False on any failure,
    so the caller falls back to --offload-to-cpu and still generates alongside a
    loaded LLM. The LLM is NOT reloaded here -- the next chat does that lazily.
    """
    try:
        req = urllib.request.Request(CTRL_URL + "/llm/unload", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        if j.get("was_loaded"):
            # Let CUDA actually release the freed VRAM before sd-cli claims it.
            time.sleep(2.0)
        return bool(j.get("ok"))
    except Exception as e:
        log.warning(f"LLM unload coordination unavailable ({e}); using --offload-to-cpu")
        return False


app = Flask(__name__)


@app.route("/status")
def status():
    miss = _missing()
    return jsonify({
        "ok": not miss,
        "engine": "stable-diffusion.cpp",
        "model": MODEL["name"],
        "files": MODEL["files"],
        "params": MODEL["params"],
        "binary": str(SD_BIN) if SD_BIN else None,
        # Default policy. The actual per-generation mode is decided live: a GPU
        # swap when the tray unloads the LLM, else CPU offload as a fallback.
        "gpu_swap": (not args.no_offload and not args.no_swap),
        "offload_to_cpu": not args.no_offload,
        "offload": MODEL.get("offload", ""),
        "missing": miss,
    })


@app.route("/generate", methods=["OPTIONS"])
def generate_options():
    return "", 204


@app.route("/generate", methods=["POST"])
def generate():
    # Re-read the model config each call so a browser image-model switch
    # (writes selmo-image-config.json) takes effect without restarting the bridge.
    global MODEL
    MODEL = _load_model()
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
    seed   = data.get("seed")
    seed   = int(seed) if seed not in (None, "") else -1

    out_path = OUT_DIR / f"{uuid.uuid4().hex}.png"
    # The model is config-driven: diffusion pick + fixed companion flags (files)
    # + editable tuning (params, e.g. --steps/--cfg-scale). The bridge owns the
    # geometry / prompt / output / offload flags, stripped from files+params.
    # Normalise Windows backslashes to '/' before shlex (POSIX mode eats '\'),
    # so paths like image\ae.safetensors survive; sd-cli accepts '/' on Windows.
    cmd = [str(SD_BIN), "--diffusion-model", str(MODEL["diffusion"])]
    cmd += _strip_struct(shlex.split(MODEL["files"].replace("\\", "/")))
    cmd += _strip_struct(shlex.split(MODEL["params"].replace("\\", "/")))
    cmd += [
        "-p",    prompt,
        "-W",    str(width),
        "-H",    str(height),
        "--seed", str(seed),
        "--diffusion-fa",
        "-o",    str(out_path),
    ]
    if init_path is not None:
        # New sd.cpp CLI: image gen is the default "img_gen" mode; supplying an
        # init image (not a "-M img2img" mode, which was removed) triggers img2img.
        cmd += ["--init-img", str(init_path), "--strength", str(strength)]

    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    _mode = f"img2img s={strength} init={init_path.name}" if init_path is not None else "txt2img"
    log.info(f"{MODEL['name']} {_mode} {width}x{height} seed={seed} [{MODEL['params']}]: {prompt[:80]}")

    with _lock:
        # Decide GPU vs CPU offload now (one generation at a time under the lock).
        # Default: free the GPU by unloading the LLM. --no-offload forces GPU and
        # skips coordination; --no-swap disables the swap (always offload).
        if args.no_offload:
            use_gpu = True
        elif args.no_swap:
            use_gpu = False
        else:
            use_gpu = _llm_unload()
        # Some models (e.g. Qwen-Image, 20B) do not fit 12 GB even with the LLM
        # unloaded; their config sets offload=always so weights stream from RAM.
        # An explicit --no-offload still wins (forces GPU, skips coordination).
        force_offload = (not args.no_offload) and \
                        (str(MODEL.get("offload", "")).lower() == "always")
        if force_offload or not use_gpu:
            cmd.append("--offload-to-cpu")
        if force_offload and use_gpu:
            log.info("GPU freed (LLM unloaded) + --offload-to-cpu (model too big to be resident)")
        else:
            log.info("GPU (LLM unloaded)" if use_gpu else "CPU offload (LLM coexists)")
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=600, creationflags=NO_WINDOW,
                cwd=str(SCRIPT_DIR),   # so relative image\ companion paths resolve
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
    # Loopback only: reached via the front door /proxy/8086, not directly. (security review)
    log.info(f"Selmo image (stable-diffusion.cpp) listening on http://127.0.0.1:{args.port}")
    log.info(f"Model: {MODEL['name']}  files=[{MODEL['files']}]  params=[{MODEL['params']}]")
    miss = _missing()
    if miss:
        log.warning("Not ready yet — missing: " + "; ".join(miss))
    # threaded=True so /status answers while a long generation holds the lock.
    app.run(host="127.0.0.1", port=args.port, debug=False, threaded=True)
