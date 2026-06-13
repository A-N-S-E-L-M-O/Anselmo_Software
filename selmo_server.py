"""
selmo_server.py — Selmo backend launcher
Starts all the Python services in the background (no window)
and llama-server in the foreground in this window.
Closing this window (or Ctrl+C) shuts everything down.

Usage (called by Selmo.bat):
  python selmo_server.py --model <path> --ngl <N> --ctx <N> [--mmproj <path>] [--voice <name>]
"""

import subprocess
import sys
import os
import atexit
import time
import threading
import argparse
import json
from pathlib import Path

BASE   = Path(__file__).parent
PYTHON = Path(sys.executable)

# Persistent llama-server log: stdout+stderr go here as well as to the screen.
# Needed to diagnose multimodal 400s (e.g. image from the phone) by reading
# the real server error. See BUG-IMG-02.
LLAMA_LOG = BASE / "selmo-llama.log"


def _tee(proc, logpath):
    """Read llama-server output and write it both to the screen and to a file."""
    try:
        with open(logpath, "w", encoding="utf-8", errors="replace") as lf:
            for raw in iter(proc.stdout.readline, b""):
                s = raw.decode("utf-8", errors="replace")
                sys.stdout.write(s)
                sys.stdout.flush()
                lf.write(s)
                lf.flush()
    except Exception:
        pass

# pythonw.exe = Python without a console window (preferred if available)
PYTHONW = PYTHON.parent / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = PYTHON

# Windows flag: create the process without a console window
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# List of child processes to terminate on exit
_procs: list[subprocess.Popen] = []


# -- Cleanup -------------------------------------------------------------------

def _cleanup():
    """Terminate all child processes started by this launcher."""
    if not _procs:
        return
    print("\n[Selmo] Stopping services...", flush=True)
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.8)
    for p in _procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass
    print("[Selmo] Everything stopped.", flush=True)


atexit.register(_cleanup)


# -- Window-close (X button) handling on Windows ------------------------------

if sys.platform == "win32":
    import ctypes

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    def _ctrl_handler(event):
        # CTRL_C=0, CTRL_BREAK=1, CTRL_CLOSE=2, CTRL_LOGOFF=5, CTRL_SHUTDOWN=6
        _cleanup()
        os._exit(0)
        return True

    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler, True)


# -- Service startup -----------------------------------------------------------

def _start(label: str, args: list) -> subprocess.Popen:
    """Start a Python service without a window and without visible output."""
    cmd = [str(PYTHONW)] + args
    print(f"  -> {label}", flush=True)
    p = subprocess.Popen(
        cmd,
        creationflags=NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(p)
    return p


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Selmo Backend Launcher")
    parser.add_argument("--model",  required=True,  help="Path to the .gguf file")
    parser.add_argument("--ngl",    type=int, default=99,       help="GPU layers (99 = offload all, let llama.cpp fit what it can)")
    parser.add_argument("--ctx",    type=int, default=0,        help="Context size (0 = use the model's training context, let the model decide)")
    parser.add_argument("--cpumoe",      type=int,   default=0,    help="MoE experts kept on CPU/RAM (--n-cpu-moe N). 0 = off (all on GPU per -ngl)")
    parser.add_argument("--mmproj",      default=None,             help="mmproj path (vision)")
    parser.add_argument("--voice",       default="im_nicola",      help="TTS voice")
    parser.add_argument("--chunk-ratio", type=float, default=0.25, help="Fraction of ctx used for input per chunk (rest = reasoning+output budget)")
    parser.add_argument("--chunk-maxtok",type=int,   default=6000, help="Hard cap on output tokens per chunk (reasoning included)")
    args = parser.parse_args()

    # Write selmo-config.json so chat.html can read per-model chunking params at startup.
    # llama-server serves static files from --path BASE, so /selmo-config.json is reachable.
    config = {"chunk_ratio": args.chunk_ratio, "chunk_maxtok": args.chunk_maxtok}
    (BASE / "selmo-config.json").write_text(json.dumps(config), encoding="utf-8")

    model_name = Path(args.model).name

    border = "  +" + "-" * 42 + "+"
    def boxline(s):
        return "  |" + s.center(42) + "|"

    print()
    print(border)
    print(boxline("Selmo  --  local AI, GDPR by design"))
    print(boxline("Your data stays on your computer."))
    print(border)
    print()
    ctx_label = "model default" if args.ctx == 0 else str(args.ctx)
    print(f"  Model    : {model_name}")
    print(f"  -ngl     : {args.ngl}   ctx: {ctx_label}")
    if args.cpumoe > 0:
        print(f"  n-cpu-moe: {args.cpumoe} expert layers on RAM (MoE offload)")
    if args.mmproj:
        print(f"  Vision   : on  ({Path(args.mmproj).name})")
    else:
        print("  Vision   : text only")
    print()
    print("  Starting Python services (no separate window)...")

    _start("GPU Monitor   [port 8082]", [str(BASE / "selmo_gpu_monitor.py")])
    _start("Web Bridge    [port 8081]", [str(BASE / "selmo_web.py")])
    _start("Whisper STT   [port 8083]", [str(BASE / "selmo_whisper.py")])
    _start("TTS Kokoro    [port 8084]", [str(BASE / "selmo_tts.py"), "--voice", args.voice])
    _start("HTTPS Proxy   [port 8443]", [str(BASE / "selmo_https_proxy.py")])

    # Small pause to give the services time to start
    time.sleep(2)

    # Open the browser
    try:
        os.startfile("http://127.0.0.1:8080/chat.html")
    except Exception:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "http://127.0.0.1:8080/chat.html"],
            creationflags=NO_WINDOW,
        )

    # -- Build the llama-server command ---------------------------------------
    llama = str(BASE / "bin" / "llama-server.exe")
    cmd = [
        llama,
        "--model",              args.model,
        "--host",               "0.0.0.0",
        "--port",               "8080",
        "--ctx-size",           str(args.ctx),
        "-ngl",                 str(args.ngl),
        "--parallel",           "1",
        "--no-warmup",
        # BUG-IMG-02: --timeout 0 zeroes cpp-httplib's read timeout. On
        # localhost the body arrives all at once and that's fine, but over the
        # network (phone) a large body (image ~200KB, Whisper audio) arrives in
        # many packets with micro-gaps: with the timeout at 0 the read fails on
        # the first packet that isn't ready yet and httplib replies 400 with an
        # empty body (no content-type, len 0) BEFORE the handler. A generous
        # value: it does not cut off long generations (the client aborts at 300s)
        # but lets slow bodies be read.
        "--timeout",            "600",
        "--metrics",
        "--path",               str(BASE),
        # No forced sampling (--temp/--top-p removed): the client sends its own
        # per-request values, so the model's defaults apply otherwise. Neutral
        # for benchmarking against LM Studio. Only --reasoning-format is kept,
        # so the reasoning window keeps working.
        "--reasoning-format",   "deepseek",
    ]
    if args.cpumoe > 0:
        # MoE expert offload: keep the experts of N layers in system RAM while the
        # dense backbone (attention/router) stays on the GPU. Only a few experts
        # activate per token, so a big MoE (e.g. Qwen3-30B-A3B) runs on 12GB VRAM.
        cmd += ["--n-cpu-moe", str(args.cpumoe)]
    if args.mmproj:
        cmd += [
            "--mmproj",             args.mmproj,
            "--batch-size",         "2048",
            "--ubatch-size",        "2048",
        ]
        # No per-model image-token forcing: every vision model uses its native
        # resolution (neutral). batch/ubatch 2048 stays so the image tokens fit
        # in a single ubatch (avoids the Gemma GGML_ASSERT crash, BUG-IMG-01).

    print()
    print("  Starting llama-server...")
    print("  -----------------------------------------------------")
    print("  Ctrl+C  or  close this window  to stop everything.")
    print()

    # llama-server in foreground: output to screen (via tee) + to selmo-llama.log
    print(f"  llama-server log: {LLAMA_LOG.name}")
    print()
    llama_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _procs.append(llama_proc)
    threading.Thread(target=_tee, args=(llama_proc, LLAMA_LOG), daemon=True).start()

    try:
        llama_proc.wait()
    except KeyboardInterrupt:
        pass
    # _cleanup() is called by atexit


if __name__ == "__main__":
    main()
