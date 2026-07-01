"""
selmo_server.py — Selmo backend launcher
Starts all the Python services in the background (no window)
and llama-server in the foreground in this window.
Closing this window (or Ctrl+C) shuts everything down.

Usage (called by Selmo.bat):
  python selmo_server.py --model <path> --srv "<llama-server flags>" [--mmproj <path>] [--voice <name>] [--chunk-ratio <f>] [--chunk-maxtok <N>]
"""

import subprocess
import sys
import os
import atexit
import time
import threading
import argparse
import json
import shlex
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

# Windows flags
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # 0x08000000

# List of child processes (for graceful-shutdown messages)
_procs: list[subprocess.Popen] = []


# -- Windows Job Object --------------------------------------------------------
# All child processes are assigned to this job.  When this process exits for
# ANY reason (normal, exception, window X, Task Manager kill), Windows closes
# the job handle and automatically terminates every process in the job.
# This is more reliable than any cleanup handler.

_WIN_JOB = None   # HANDLE; stays None on non-Windows or if creation fails

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    _k32 = ctypes.windll.kernel32

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit",     ctypes.c_int64),
            ("LimitFlags",             ctypes.c_uint32),
            ("MinimumWorkingSetSize",  ctypes.c_size_t),
            ("MaximumWorkingSetSize",  ctypes.c_size_t),
            ("ActiveProcessLimit",     ctypes.c_uint32),
            ("Affinity",               ctypes.c_size_t),
            ("PriorityClass",          ctypes.c_uint32),
            ("SchedulingClass",        ctypes.c_uint32),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount",  ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount",   ctypes.c_uint64),
            ("WriteTransferCount",  ctypes.c_uint64),
            ("OtherTransferCount",  ctypes.c_uint64),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo",                _IO_COUNTERS),
            ("ProcessMemoryLimit",    ctypes.c_size_t),
            ("JobMemoryLimit",        ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed",     ctypes.c_size_t),
        ]

    def _init_win_job():
        global _WIN_JOB
        job = _k32.CreateJobObjectW(None, None)
        if not job:
            return
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info.BasicLimitInformation.LimitFlags = 0x00002000
        ok = _k32.SetInformationJobObject(
            job,
            9,                    # JobObjectExtendedLimitInformation
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if ok:
            _WIN_JOB = job
            print("  [job] Child-kill job object created.", flush=True)
        else:
            _k32.CloseHandle(job)

    _init_win_job()

    def _assign_to_job(pid: int):
        """Assign a child PID to the kill-on-close job."""
        if not _WIN_JOB:
            return
        # Need at least PROCESS_SET_QUOTA | PROCESS_TERMINATE; use ALL_ACCESS.
        h = _k32.OpenProcess(0x001F0FFF, False, pid)
        if h:
            _k32.AssignProcessToJobObject(_WIN_JOB, h)
            _k32.CloseHandle(h)

else:
    def _assign_to_job(pid: int):
        pass


# -- Cleanup (graceful, belt-and-suspenders) -----------------------------------

def _cleanup():
    """Gracefully terminate child processes and print status.
    The Job Object handles anything this misses."""
    if not _procs:
        return
    print("\n[Selmo] Stopping services...", flush=True)
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.5)
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

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    def _ctrl_handler(event):
        # CTRL_C=0, CTRL_BREAK=1, CTRL_CLOSE=2, CTRL_LOGOFF=5, CTRL_SHUTDOWN=6
        _cleanup()
        os._exit(0)
        return True

    _k32.SetConsoleCtrlHandler(_ctrl_handler, True)


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
    _assign_to_job(p.pid)
    _procs.append(p)
    return p


# -- LibreHardwareMonitor (system-power source on port 8085) -------------------
# Provides CPU package power + GPU power (vendor-agnostic) that selmo_gpu_monitor
# reads from http://127.0.0.1:8085/data.json. It needs admin rights (RAPL) and
# its Remote Web Server enabled once in the app (Options > Remote Web Server >
# Run, plus "Run web server"/"Start minimized" so it persists). We only launch
# it; we don't add it to _procs (shared tray app, and an elevated child can't be
# killed by a non-elevated parent). Override the exe location with SELMO_LHM.

def _lhm_path():
    cands = []
    env = os.environ.get("SELMO_LHM")
    if env:
        cands.append(Path(env))
    cands += [
        BASE / "bin" / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe",  # setup-lhm.ps1 default
        BASE / "bin" / "LibreHardwareMonitor.exe",
        BASE / "tools" / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe",
        BASE / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe",
        Path(r"C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitor.exe"),
    ]
    for c in cands:
        try:
            if c and c.exists():
                return c
        except Exception:
            pass
    return None

def _lhm_running():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq LibreHardwareMonitor.exe"],
            capture_output=True, text=True, creationflags=NO_WINDOW,
        ).stdout or ""
        return "LibreHardwareMonitor.exe" in out
    except Exception:
        return False

def start_lhm():
    """Launch LibreHardwareMonitor minimized (if present and not already up)."""
    if sys.platform != "win32":
        return
    if _lhm_running():
        print("  -> LibreHardwareMonitor [port 8085] (already running)", flush=True)
        return
    exe = _lhm_path()
    if not exe:
        print("  -> LibreHardwareMonitor not found: CPU power unavailable "
              "(set SELMO_LHM or drop it in bin\\). System gauge still estimates GPU+losses.",
              flush=True)
        return
    try:
        import ctypes
        # ShellExecute honours LHM's admin manifest (RAPL needs it); 7 = SW_SHOWMINNOACTIVE.
        rc = ctypes.windll.shell32.ShellExecuteW(None, "open", str(exe), None, str(exe.parent), 7)
        if rc <= 32:
            raise OSError(f"ShellExecute returned {rc}")
        print("  -> LibreHardwareMonitor [port 8085] (started minimized)", flush=True)
    except Exception as e:
        print(f"  -> LibreHardwareMonitor launch failed ({e})", flush=True)


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Selmo Backend Launcher")
    parser.add_argument("--model",  required=True,  help="Path to the .gguf file")
    parser.add_argument("--srv",    default="",  help="Raw llama-server flags from selmo-models.ini, forwarded verbatim. Everything except the 4 structural flags managed here (--model/--host/--port/--path).")
    parser.add_argument("--mmproj",      default=None,             help="mmproj path (vision)")
    parser.add_argument("--voice",       default="im_nicola",      help="TTS voice")
    parser.add_argument("--chunking-size", type=int, default=2000, help="Input tokens per chunk (model-specific ceiling; output gets what's left)")
    parser.add_argument("--think", default="", help="How the THINK button toggles reasoning for this model: instr | kwarg | native | '' (auto-detect). SELMO-only, written to selmo-config.json for chat.html.")
    args = parser.parse_args()

    # Write selmo-config.json so chat.html can read per-model chunking params at startup.
    # llama-server serves static files from --path BASE, so /selmo-config.json is reachable.
    config = {"chunking_size": args.chunking_size, "think": args.think}
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
    print(f"  Model    : {model_name}")
    print(f"  Server   : {args.srv or '(structural flags only)'}")
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
    _start("Image SD.cpp  [port 8086]", [str(BASE / "selmo_image.py")])
    _start("Front door    [8080+8443]", [str(BASE / "selmo_https_proxy.py")])
    start_lhm()  # system-power source (CPU+GPU watts) on port 8085

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
    # Selmo manages only 4 STRUCTURAL flags the app can't run without:
    #   --model (the menu pick) · --host/--port (chat.html talks to
    #   0.0.0.0:8080) · --path (static serving of chat.html). EVERYTHING else
    #   -- ctx, ngl, cpumoe, sampling, flash-attn, reasoning-format, timeout,
    #   metrics... -- comes from the editable `srv` string in selmo-models.ini
    #   and is forwarded verbatim. Full control lives in the ini.
    #   Note: keep --reasoning-format (THINK panel), --timeout 600 (phone
    #   uploads, BUG-IMG-02) and --metrics in srv, features depend on them.
    # Backend dir is overridable so the home edition can pick CUDA vs Vulkan
    # at runtime (SELMO_BIN_DIR=bin|bin-vulkan). Default "bin" keeps the
    # production launcher (Selmo.bat) byte-for-byte unchanged.
    _bindir = os.environ.get("SELMO_BIN_DIR", "bin")
    llama = str(BASE / _bindir / "llama-server.exe")
    cmd = [
        llama,
        "--model",  args.model,
        # Behind the front door now: selmo_https_proxy.py owns 8080 and
        # serves chat.html; the LLM listens on private loopback 8089 and the
        # front door proxies /proxy/8089 -> here.
        "--host",   "127.0.0.1",
        "--port",   "8089",
        "--path",   str(BASE),
    ]
    # Forward the user's server string, dropping any structural flag they may
    # have typed (those are owned above; a stray --port would break chat.html).
    STRUCTURAL = {"--model", "-m", "--host", "--port", "--path"}
    toks = shlex.split(args.srv) if args.srv else []
    i = 0
    while i < len(toks):
        if toks[i] in STRUCTURAL:
            i += 2          # drop the flag and its value
            continue
        cmd.append(toks[i])
        i += 1
    if args.mmproj:
        # Appended LAST so our batch/ubatch win: Gemma's vision encoder uses
        # non-causal attention, all image tokens must fit a single ubatch or it
        # GGML_ASSERTs (BUG-IMG-01). Vision models use their native resolution.
        cmd += [
            "--mmproj",      args.mmproj,
            "--batch-size",  "2048",
            "--ubatch-size", "2048",
        ]

    print()
    print("  Starting llama-server...")
    print("  -----------------------------------------------------")
    print("  Ctrl+C  or  close this window  to stop everything.")
    print()

    # llama-server in foreground: output to screen (via tee) + to selmo-llama.log
    print(f"  llama-server log: {LLAMA_LOG.name}")
    print()
    llama_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _assign_to_job(llama_proc.pid)   # also kill llama-server when we die
    _procs.append(llama_proc)
    threading.Thread(target=_tee, args=(llama_proc, LLAMA_LOG), daemon=True).start()

    try:
        llama_proc.wait()
    except KeyboardInterrupt:
        pass
    # _cleanup() is called by atexit


if __name__ == "__main__":
    main()
