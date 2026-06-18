"""
selmo_tray.py  --  Selmo tray launcher  (v0.9)

Replaces Selmo.bat.  Reads selmo-models.ini, shows the same text
console picker, then detaches from the console and runs as a
pure system-tray app.

Behaviour
  - Runs under pythonw.exe (via Selmo.vbs) so no console window is ever
    created -- no black window, no taskbar button.  Model selection is a
    small Tkinter dialog; after that Selmo lives purely in the system tray.
  - All child processes (llama-server + bridges) are placed in a Windows
    Job Object with KILL_ON_JOB_CLOSE, so they are torn down when the tray
    process exits for any reason (Exit, logoff, shutdown, crash).
  - "View log file" in the tray opens selmo-llama.log in Notepad.
  - "Unload model" stops llama-server to free VRAM; "Reload model"
    restarts it with the same model and flags.
  - Only one instance is allowed (named mutex guard).
  - "Exit" in the tray kills everything cleanly.

New dependencies (everything else already required):
    pip install pystray Pillow --break-system-packages
"""

import atexit
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Tray dependencies -- graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE    = Path(__file__).resolve().parent
PYTHON  = Path(sys.executable)
PYTHONW = PYTHON.parent / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = PYTHON

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LLAMA_LOG = BASE / "selmo-llama.log"
LLAMA_EXE = BASE / "bin" / "llama-server.exe"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_SRV = (
    "--ctx-size 8192 -ngl 99 --parallel 1 --no-mmap --no-warmup "
    "--timeout 600 --metrics --reasoning-format deepseek"
)
DEFAULT_CSIZE = 2000

# ---------------------------------------------------------------------------
# Mutable state shared between tray callbacks and background threads
# ---------------------------------------------------------------------------
_current = {
    "name":   "",     # active model display name
    "srv":    "",     # active srv string
    "mmproj": None,   # active mmproj path or None
    "loaded": False,  # True while llama-server is running
}

_services: list[subprocess.Popen] = []      # background bridges (started once)
_llama_proc: subprocess.Popen | None = None
_llama_lock = threading.Lock()

_tray_icon   = None   # pystray.Icon, set before icon.run()
_mutex_handle = None  # Win32 mutex for single-instance guard


# ============================================================
#  Single-instance guard  (named Win32 mutex)
# ============================================================

def _claim_instance() -> bool:
    """Returns True if this is the first instance; False if already running."""
    if sys.platform != "win32":
        return True
    import ctypes
    m   = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\SelmoTrayApp_v1")
    err = ctypes.windll.kernel32.GetLastError()
    if err == 183:       # ERROR_ALREADY_EXISTS
        return False
    global _mutex_handle
    _mutex_handle = m    # keep reference alive -- released on process exit
    return True


# ============================================================
#  Output redirect  (pythonw has no console)
# ============================================================

def _redirect_output_to_log():
    """
    Under pythonw.exe there is no console and sys.stdout / sys.stderr are
    None, so any print() would raise.  Point both at a tray log file (or
    devnull as a last resort) so the existing print() diagnostics are safe.
    Must be the FIRST thing main() does, before any output.
    """
    try:
        f = open(BASE / "selmo-tray.log", "w", encoding="utf-8", errors="replace")
        sys.stdout = f
        sys.stderr = f
    except Exception:
        try:
            nul = open(os.devnull, "w")
            sys.stdout = nul
            sys.stderr = nul
        except Exception:
            pass


# ============================================================
#  Job Object  -- kill all children when the tray process dies
# ============================================================
#
#  With no console (pythonw), the SetConsoleCtrlHandler below never fires,
#  so logoff/shutdown can't lean on it.  A Job Object with
#  KILL_ON_JOB_CLOSE is the robust replacement: every child we assign to it
#  is killed by the OS the moment our process exits, for *any* reason.

_job_handle = None


def _setup_job():
    global _job_handle
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    h = k.CreateJobObjectW(None, None)
    if not h:
        return

    class _BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit",     wintypes.LARGE_INTEGER),
            ("LimitFlags",              wintypes.DWORD),
            ("MinimumWorkingSetSize",   ctypes.c_size_t),
            ("MaximumWorkingSetSize",   ctypes.c_size_t),
            ("ActiveProcessLimit",      wintypes.DWORD),
            ("Affinity",                ctypes.c_size_t),
            ("PriorityClass",           wintypes.DWORD),
            ("SchedulingClass",         wintypes.DWORD),
        ]

    class _IO(ctypes.Structure):
        _fields_ = [("ReadOperationCount",  ctypes.c_ulonglong),
                    ("WriteOperationCount", ctypes.c_ulonglong),
                    ("OtherOperationCount", ctypes.c_ulonglong),
                    ("ReadTransferCount",   ctypes.c_ulonglong),
                    ("WriteTransferCount",  ctypes.c_ulonglong),
                    ("OtherTransferCount",  ctypes.c_ulonglong)]

    class _EXT(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BASIC),
                    ("IoInfo",                _IO),
                    ("ProcessMemoryLimit",    ctypes.c_size_t),
                    ("JobMemoryLimit",        ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed",     ctypes.c_size_t)]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectExtendedLimitInformation  = 9
    info = _EXT()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if k.SetInformationJobObject(h, JobObjectExtendedLimitInformation,
                                 ctypes.byref(info), ctypes.sizeof(info)):
        _job_handle = h


def _assign_to_job(proc):
    if _job_handle is None or sys.platform != "win32" or proc is None:
        return
    import ctypes
    try:
        ctypes.windll.kernel32.AssignProcessToJobObject(
            _job_handle, int(proc._handle))
    except Exception:
        pass


# ============================================================
#  INI parsing  (Python port of Selmo.bat logic)
# ============================================================

def _parse_ini(ini_path: Path):
    """
    Returns (sections, default).
      sections = [(name_lower, {srv, max, note, chunking_size}), ...]
      default  = dict with same keys from [default] or hard-coded values.
    First-match wins, same as the bat.
    """
    default = {
        "srv": DEFAULT_SRV, "max": "unknown",
        "note": "", "chunking_size": DEFAULT_CSIZE,
    }
    sections: list[tuple[str, dict]] = []

    if not ini_path.exists():
        return sections, default

    cur_name: str | None = None
    cur: dict = {}

    def _commit():
        nonlocal cur_name, cur
        if cur_name is None:
            return
        d = {
            "srv":           cur.get("srv",           DEFAULT_SRV),
            "max":           cur.get("max",           "unknown"),
            "note":          cur.get("note",          ""),
            "chunking_size": int(cur.get("chunking_size", DEFAULT_CSIZE)),
        }
        if cur_name == "default":
            default.update(d)
        else:
            sections.append((cur_name, d))
        cur_name = None
        cur = {}

    with open(ini_path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("["):
                _commit()
                cur_name = line[1:].rstrip("]").strip().lower()
                cur = {}
            elif "=" in line:
                k, _, v = line.partition("=")
                cur[k.strip().lower()] = v.strip()
    _commit()

    return sections, default


def _match_ini(model_name: str, sections, default) -> dict:
    """First-match substring lookup -- same logic as bat's :lookup subroutine."""
    lo = model_name.lower()
    for sec_name, sec_data in sections:
        if sec_name in lo:
            return sec_data
    return default


# ============================================================
#  Model scanning
# ============================================================

def _scan_models(base: Path) -> list[dict]:
    """Recursive GGUF scan (LM-Studio style).  Excludes mmproj files."""
    mdir = base / "models"
    if not mdir.exists():
        return []
    found = []
    for gguf in sorted(mdir.rglob("*.gguf")):
        if "mmproj" in gguf.name.lower():
            continue
        found.append({"name": gguf.name, "path": str(gguf), "dir": str(gguf.parent)})
    return found


def _find_mmproj(model_dir: str) -> str | None:
    for f in Path(model_dir).glob("*mmproj*.gguf"):
        return str(f)
    return None


# ============================================================
#  Console text picker  (same UX as Selmo.bat)
# ============================================================

def _text_picker(models, sections, default) -> tuple[dict, str, int]:
    if not models:
        print("  ERROR: no .gguf file found in models\\")
        print("  Download a model and place it in models\\")
        sys.exit(1)

    if len(models) == 1:
        sel = models[0]
        print(f"  Only one model found: {sel['name']}")
        print()
    else:
        print("  Available models:")
        print()
        for i, m in enumerate(models, 1):
            info  = _match_ini(m["name"], sections, default)
            label = m["name"][:42].ljust(42)
            print(f"    [{i}] {label}  --  {info.get('note', '')}")
        print()
        while True:
            raw = input(f"  Choose the model [1-{len(models)}]: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(models):
                sel = models[int(raw) - 1]
                break
            print("  Invalid choice.")

    info  = _match_ini(sel["name"], sections, default)
    srv   = info["srv"]
    csize = info["chunking_size"]

    print()
    print(f"  Native max ctx : {info.get('max', 'unknown')}"
          f"   (keep --ctx-size at or below this)")
    print()
    print("  Server args (forwarded verbatim to llama-server):")
    print(f"    {srv}")
    print()
    print("  Press ENTER to keep, or paste a full replacement line.")
    new_srv = input("  srv> ").strip()
    if new_srv:
        srv = new_srv
    print()
    new_cs = input(f"  Chunking size [{csize}]: ").strip()
    if new_cs.isdigit():
        csize = int(new_cs)
    print()

    return sel, srv, csize


# ============================================================
#  GUI model picker  (Tkinter -- no console needed)
# ============================================================

def _notify(message: str, title: str = "SelmoAI"):
    """Small modal message box (used when there is no console)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        try:
            root.iconbitmap(str(BASE / "selmo.ico"))
        except Exception:
            pass
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass


def _gui_picker(models, sections, default) -> tuple[dict, str, int]:
    """
    Tkinter replacement for the console picker.  Lists the models, lets the
    user edit the server args and chunking size, and returns
    (model_dict, srv_str, chunking_size).  Cancel / close exits cleanly.
    """
    import tkinter as tk

    if not models:
        _notify("No .gguf model found in the models\\ folder.\n"
                "Download a model and place it there, then relaunch.",
                "SelmoAI -- no model")
        sys.exit(1)

    result: dict = {}

    root = tk.Tk()
    root.title("SelmoAI -- choose a model")
    try:
        root.iconbitmap(str(BASE / "selmo.ico"))
    except Exception:
        pass
    root.configure(padx=16, pady=14)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(400, lambda: root.attributes("-topmost", False))

    tk.Label(root, text="Local model", font=("Segoe UI", 11, "bold")) \
        .grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

    lb = tk.Listbox(root, height=min(len(models), 10), width=100,
                    activestyle="dotbox", exportselection=False)
    for m in models:
        info = _match_ini(m["name"], sections, default)
        note = info.get("note", "")
        lb.insert("end", f"{m['name']}  --  {note}" if note else m["name"])
    lb.selection_set(0)
    lb.grid(row=1, column=0, columnspan=2, sticky="we")

    note_var = tk.StringVar()
    srv_var  = tk.StringVar()
    cs_var   = tk.StringVar()

    tk.Label(root, textvariable=note_var, fg="#555", wraplength=700,
             justify="left").grid(row=2, column=0, columnspan=2,
                                  sticky="w", pady=(6, 8))

    tk.Label(root, text="Server args").grid(row=3, column=0, sticky="w")
    tk.Entry(root, textvariable=srv_var, width=90) \
        .grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 8))

    tk.Label(root, text="Chunking size").grid(row=5, column=0, sticky="w")
    tk.Entry(root, textvariable=cs_var, width=12) \
        .grid(row=5, column=1, sticky="w")

    def _on_select(_evt=None):
        idx = lb.curselection()
        if not idx:
            return
        info = _match_ini(models[idx[0]]["name"], sections, default)
        note_var.set(f"Native max ctx: {info.get('max', 'unknown')}")
        srv_var.set(info["srv"])
        cs_var.set(str(info["chunking_size"]))

    lb.bind("<<ListboxSelect>>", _on_select)
    _on_select()

    def _launch(_evt=None):
        idx = lb.curselection()
        if not idx:
            return
        m    = models[idx[0]]
        info = _match_ini(m["name"], sections, default)
        srv  = srv_var.get().strip() or info["srv"]
        cs   = cs_var.get().strip()
        csize = int(cs) if cs.isdigit() else int(info["chunking_size"])
        result.update({"sel": m, "srv": srv, "csize": csize})
        root.destroy()

    def _cancel(_evt=None):
        root.destroy()

    btns = tk.Frame(root)
    btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
    tk.Button(btns, text="Launch", width=12, default="active",
              command=_launch).pack(side="right", padx=(6, 0))
    tk.Button(btns, text="Cancel", width=10,
              command=_cancel).pack(side="right")

    root.bind("<Return>", _launch)
    root.bind("<Escape>", _cancel)
    lb.bind("<Double-Button-1>", _launch)
    root.mainloop()

    if "sel" not in result:
        sys.exit(0)        # cancelled / closed
    return result["sel"], result["srv"], result["csize"]


# ============================================================
#  llama-server management
# ============================================================

STRUCTURAL = {"--model", "-m", "--host", "--port", "--path"}


def _build_cmd(model_path: str, srv_str: str, mmproj: str | None) -> list[str]:
    cmd = [
        str(LLAMA_EXE),
        "--model", model_path,
        "--host",  "0.0.0.0",
        "--port",  "8080",
        "--path",  str(BASE),
    ]
    toks = shlex.split(srv_str) if srv_str else []
    i = 0
    while i < len(toks):
        if toks[i] in STRUCTURAL:
            i += 2
            continue
        cmd.append(toks[i])
        i += 1
    if mmproj:
        # Appended LAST so our batch/ubatch win (Gemma vision, BUG-IMG-01)
        cmd += ["--mmproj", mmproj, "--batch-size", "2048", "--ubatch-size", "2048"]
    return cmd


def _tee(proc: subprocess.Popen, logpath: Path):
    """Write llama-server output to log file (and to stdout while console exists)."""
    try:
        with open(logpath, "w", encoding="utf-8", errors="replace") as lf:
            for raw in iter(proc.stdout.readline, b""):
                s = raw.decode("utf-8", errors="replace")
                try:
                    # stdout may be devnull or gone after FreeConsole -- that is fine
                    sys.stdout.write(s)
                    sys.stdout.flush()
                except Exception:
                    pass
                lf.write(s)
                lf.flush()
    except Exception:
        pass
    # Server exited -- update state and tray tooltip
    _current["loaded"] = False
    if _tray_icon:
        _tray_icon.title = f"SelmoAI  --  {_current['name']}  [unloaded]"


def _launch_llama(model_path: str, srv_str: str, mmproj: str | None):
    global _llama_proc
    cmd = _build_cmd(model_path, srv_str, mmproj)
    p   = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=NO_WINDOW,   # llama-server is a console app -- without
                                   # this it pops its own window under pythonw
    )
    _assign_to_job(p)
    with _llama_lock:
        _llama_proc = p
    _current["loaded"] = True
    if _tray_icon:
        _tray_icon.title = f"SelmoAI  --  {_current['name']}"
    threading.Thread(target=_tee, args=(p, LLAMA_LOG), daemon=True).start()
    return p


def _stop_llama():
    global _llama_proc
    with _llama_lock:
        p = _llama_proc
        _llama_proc = None
    _current["loaded"] = False
    if p is None:
        return
    if p.poll() is None:
        p.terminate()
        time.sleep(1.5)
        if p.poll() is None:
            p.kill()


# ============================================================
#  Tray actions
# ============================================================

def _action_unload(icon, item):
    """Stop llama-server to free VRAM; all other services keep running."""
    if not _current["loaded"]:
        return
    _stop_llama()
    if icon:
        icon.title = f"SelmoAI  --  {_current['name']}  [unloaded]"


def _action_reload(icon, item):
    """Restart llama-server with the currently configured model."""
    if _current["loaded"]:
        return
    models = _scan_models(BASE)
    m = next((x for x in models if x["name"] == _current["name"]), None)
    if m is None:
        return
    _launch_llama(m["path"], _current["srv"], _current["mmproj"])


def _action_switch(model: dict, ini_data: dict):
    """Stop current llama-server and start a new one."""
    _stop_llama()

    sections = ini_data["sections"]
    default  = ini_data["default"]
    info     = _match_ini(model["name"], sections, default)
    srv      = info["srv"]
    csize    = info["chunking_size"]
    mmproj   = _find_mmproj(model["dir"])

    (BASE / "selmo-config.json").write_text(
        json.dumps({"chunking_size": csize}), encoding="utf-8"
    )
    _current.update({"name": model["name"], "srv": srv, "mmproj": mmproj})

    _launch_llama(model["path"], srv, mmproj)

    if _tray_icon:
        _tray_icon.title = f"SelmoAI  --  {model['name']}"


# ============================================================
#  Background Python services
# ============================================================

def _start_service(label: str, args: list):
    cmd = [str(PYTHONW)] + args
    print(f"  -> {label}", flush=True)
    p = subprocess.Popen(
        cmd,
        creationflags=NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _assign_to_job(p)
    _services.append(p)
    return p


def _start_lhm():
    if sys.platform != "win32":
        return

    def _running():
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq LibreHardwareMonitor.exe"],
                capture_output=True, text=True, creationflags=NO_WINDOW,
            ).stdout or ""
            return "LibreHardwareMonitor.exe" in out
        except Exception:
            return False

    if _running():
        print("  -> LibreHardwareMonitor [port 8085] (already running)", flush=True)
        return
    cands = []
    env = os.environ.get("SELMO_LHM")
    if env:
        cands.append(Path(env))
    cands += [
        BASE / "bin" / "LibreHardwareMonitor" / "LibreHardwareMonitor.exe",
        BASE / "bin" / "LibreHardwareMonitor.exe",
        Path(r"C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitor.exe"),
    ]
    exe = next((c for c in cands if c and c.exists()), None)
    if not exe:
        print("  -> LibreHardwareMonitor not found (CPU power estimated)", flush=True)
        return
    try:
        import ctypes
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "open", str(exe), None, str(exe.parent), 7)
        if rc <= 32:
            raise OSError(f"ShellExecute returned {rc}")
        print("  -> LibreHardwareMonitor [port 8085] (started)", flush=True)
    except Exception as e:
        print(f"  -> LibreHardwareMonitor launch failed ({e})", flush=True)


def _start_all_services(voice: str = "im_nicola"):
    _start_service("GPU Monitor   [port 8082]", [str(BASE / "selmo_gpu_monitor.py")])
    _start_service("Web Bridge    [port 8081]", [str(BASE / "selmo_web.py")])
    _start_service("Whisper STT   [port 8083]", [str(BASE / "selmo_whisper.py")])
    _start_service("TTS Kokoro    [port 8084]",
                   [str(BASE / "selmo_tts.py"), "--voice", voice])
    _start_service("Image SD.cpp  [port 8086]", [str(BASE / "selmo_image.py")])
    _start_service("HTTPS Proxy   [port 8443]", [str(BASE / "selmo_https_proxy.py")])
    _start_lhm()


# ============================================================
#  Cleanup
# ============================================================

def _cleanup():
    all_procs = list(_services)
    with _llama_lock:
        if _llama_proc:
            all_procs.append(_llama_proc)
    if not all_procs:
        return
    for p in all_procs:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.8)
    for p in all_procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass


atexit.register(_cleanup)

# Ctrl+C / logoff / shutdown handler (console may or may not exist at this point)
if sys.platform == "win32":
    import ctypes as _ctypes

    @_ctypes.WINFUNCTYPE(_ctypes.c_bool, _ctypes.c_uint)
    def _ctrl_handler(event):
        _cleanup()
        os._exit(0)
        return True

    _ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler, True)


# ============================================================
#  Tray icon
# ============================================================

def _make_icon_image() -> "Image.Image":
    """Tray icon: prefer the bundled selmo.ico, else draw a navy square + white S."""
    ico = BASE / "selmo.ico"
    if ico.exists():
        try:
            return Image.open(ico).convert("RGBA")
        except Exception:
            pass
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                           radius=14, fill=(16, 38, 112, 255))
    font = None
    for fname in ("arialbd.ttf", "calibrib.ttf", "segoeuib.ttf", "verdanab.ttf"):
        try:
            font = ImageFont.truetype(fname, 46)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "S", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - 2),
        "S", font=font, fill=(255, 255, 255, 255),
    )
    return img


def _open_browser(icon, item):
    try:
        os.startfile("http://127.0.0.1:8080/chat.html")
    except Exception:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "http://127.0.0.1:8080/chat.html"],
            creationflags=NO_WINDOW,
        )


def _view_log(icon, item):
    try:
        os.startfile(str(LLAMA_LOG))
    except Exception:
        subprocess.Popen(["notepad.exe", str(LLAMA_LOG)], creationflags=NO_WINDOW)


def _do_exit(icon, item):
    _cleanup()
    os._exit(0)   # icon.stop() can hang on Windows; _cleanup() already killed children


def _build_menu(models: list[dict], ini_data: dict):
    """
    Returns a callable that pystray re-evaluates each time the menu opens.
    Dynamic state (loaded flag, model name) is read fresh via lambdas.
    """

    def _make_switch(m):
        def _do(icon, item):
            threading.Thread(
                target=_action_switch, args=(m, ini_data), daemon=True
            ).start()
        return _do

    def build():
        return [
            # live status header
            pystray.MenuItem(
                lambda item: (
                    f"SelmoAI  --  {_current['name'][:32]}"
                    + ("  [unloaded]" if not _current["loaded"] else "")
                ),
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Open SelmoAI in browser", _open_browser),
            pystray.MenuItem("View log file",          _view_log),
            pystray.Menu.SEPARATOR,

            # model switcher submenu
            pystray.MenuItem(
                "Switch model",
                pystray.Menu(*[
                    pystray.MenuItem(
                        m["name"][:52],
                        _make_switch(m),
                        checked=lambda item, mn=m["name"]: _current["name"] == mn,
                        radio=True,
                    )
                    for m in models
                ]),
            ),
            pystray.Menu.SEPARATOR,

            pystray.MenuItem(
                "Unload model  (free VRAM)",
                lambda icon, item: threading.Thread(
                    target=_action_unload, args=(icon, item), daemon=True
                ).start(),
                enabled=lambda item: _current["loaded"],
            ),
            pystray.MenuItem(
                "Reload model",
                lambda icon, item: threading.Thread(
                    target=_action_reload, args=(icon, item), daemon=True
                ).start(),
                enabled=lambda item: not _current["loaded"],
            ),
            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Exit", _do_exit),
        ]

    return build


# ============================================================
#  Entry point
# ============================================================

def main():
    global _tray_icon

    _redirect_output_to_log()   # MUST be first: no console under pythonw
    _setup_job()                # OS kills our children when we exit

    # -- single-instance guard --------------------------------------------
    if not _claim_instance():
        _notify("SelmoAI is already running.\nCheck the system tray.")
        sys.exit(0)

    ini_path          = BASE / "selmo-models.ini"
    sections, default = _parse_ini(ini_path)
    models            = _scan_models(BASE)

    border  = "  +" + "-" * 44 + "+"
    boxline = lambda s: "  |" + s.center(44) + "|"
    print()
    print(border)
    print(boxline("SelmoAI  --  local AI, GDPR by design"))
    print(boxline("Your data stays on your computer."))
    print(border)
    print()

    sel, srv, csize = _gui_picker(models, sections, default)
    mmproj = _find_mmproj(sel["dir"])

    vis = f"on  ({Path(mmproj).name})" if mmproj else "text only"
    print(f"  Launching:  {sel['name']}")
    print(f"  Vision   :  {vis}")
    print(f"  Chunking :  {csize} tokens / chunk")
    print()

    (BASE / "selmo-config.json").write_text(
        json.dumps({"chunking_size": csize}), encoding="utf-8"
    )
    _current.update({"name": sel["name"], "srv": srv, "mmproj": mmproj, "loaded": False})

    print("  Starting Python services...")
    _start_all_services()
    time.sleep(2)

    try:
        os.startfile("http://127.0.0.1:8080/chat.html")
    except Exception:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "http://127.0.0.1:8080/chat.html"],
            creationflags=NO_WINDOW,
        )

    print()
    print("  Starting llama-server...")
    print(f"  Log: {LLAMA_LOG.name}")
    _launch_llama(sel["path"], srv, mmproj)

    # -- tray path: hand off to pystray (no console to detach) ------------
    if HAS_TRAY:
        ini_data = {"sections": sections, "default": default}
        menu_fn  = _build_menu(models, ini_data)

        icon = pystray.Icon(
            name  = "selmo",
            icon  = _make_icon_image(),
            title = f"SelmoAI  --  {sel['name']}",
            menu  = pystray.Menu(menu_fn),
        )
        _tray_icon = icon

        print("  Tray icon active -- SelmoAI is now running in the tray.")
        icon.run()          # blocks until _do_exit calls icon.stop()

    # -- fallback: no tray, stay in console -------------------------------
    else:
        print()
        print("  [pystray / Pillow not installed -- running without tray]")
        print("  pip install pystray Pillow --break-system-packages")
        print("  Ctrl+C or close this window to stop everything.")
        print()
        try:
            with _llama_lock:
                p = _llama_proc
            if p:
                p.wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
