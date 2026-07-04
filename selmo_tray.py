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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
    "swapped_for_image": False,  # True when the image bridge unloaded the LLM
                                 # to free VRAM; the next chat reloads it lazily
}

CTRL_PORT = 8087  # tray control API (LLM load/unload coordination)

_services: list[subprocess.Popen] = []      # background bridges (started once)
_llama_proc: subprocess.Popen | None = None
_llama_lock = threading.Lock()
_ctrl_lock  = threading.Lock()   # serialises load/unload across tray + control API

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
        "note": "", "tip": "", "chunking_size": DEFAULT_CSIZE, "think": "",
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
            "tip":           cur.get("tip",           ""),
            "chunking_size": int(cur.get("chunking_size", DEFAULT_CSIZE)),
            "think":         cur.get("think",          ""),
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


# -- last-used model persistence (selmo-state.json) -----------------------
STATE_FILE = BASE / "selmo-state.json"

def _load_last_model() -> str:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("last_model", "")
    except Exception:
        return ""

def _save_last_model(name: str):
    try:
        STATE_FILE.write_text(json.dumps({"last_model": name}), encoding="utf-8")
    except Exception:
        pass


# ============================================================
#  Image / generative model scanning  (twin of the LLM scan)
# ============================================================

# Substrings that mark an auxiliary file (text encoder / VAE), not a diffusion
# model. The scan keeps only the diffusion weights, like the LLM scan skips mmproj.
# NB: match "instruct", not bare "qwen" -- the Qwen-Image *diffusion* file is
# named Qwen-Image-*.gguf, while the text encoders (Qwen3-4B-Instruct, the
# Qwen2.5-VL-7B-Instruct used by Qwen-Image) carry "instruct".
_IMG_AUX = ("instruct", "clip", "t5", "umt5", "mmproj", "encoder", "text_enc")
_IMG_SKIP_DIRS = (".cache", "vae", "split_files", "out")


def _scan_image_models(base: Path) -> list[dict]:
    """Recursive scan of image\\ for diffusion models (encoders + VAEs skipped)."""
    idir = base / "image"
    if not idir.exists():
        return []
    found = []
    for f in sorted(idir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in (".gguf", ".safetensors"):
            continue
        low = f.name.lower()
        if any(k in low for k in _IMG_AUX):
            continue
        if low == "ae.safetensors" or "vae" in low:
            continue
        if any(seg.lower() in _IMG_SKIP_DIRS for seg in f.relative_to(idir).parts[:-1]):
            continue
        found.append({"name": f.name, "path": str(f), "dir": str(f.parent)})
    return found


def _parse_image_ini(ini_path: Path):
    """
    Twin of _parse_ini for selmo-image-models.ini.
      sections = [(name_lower, {files, params, note}), ...]
      default  = dict with the same keys.
    First-match wins, matched as a substring of the diffusion file name.
    """
    default = {
        "files":  "--vae image\\ae.safetensors",
        "params": "--steps 8 --cfg-scale 1.0",
        "note":   "",
        "tip":    "",
        "offload": "",   # "always" -> bridge forces --offload-to-cpu (big models)
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
            "files":  cur.get("files",  default["files"]),
            "params": cur.get("params", default["params"]),
            "note":   cur.get("note",   ""),
            "tip":    cur.get("tip",    ""),
            "offload": cur.get("offload", default["offload"]),
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


def _image_config(sel_img, isections, idefault, params=None) -> dict | None:
    """Resolve a chosen diffusion model + its ini match into the bridge config."""
    if not sel_img:
        return None
    info = _match_ini(sel_img["name"], isections, idefault)
    return {
        "name":      sel_img["name"],
        "diffusion": sel_img["path"],
        "files":     info["files"],
        "params":    info["params"] if params is None else params,
        "offload":   info.get("offload", ""),
    }


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

def _notify(message: str, title: str = "A.N.S.E.L.M.O"):
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


def _gui_picker(models, sections, default,
                img_models, isections, idefault):
    """
    Two-column Tkinter picker. LEFT = language model (model + server args +
    chunking). RIGHT = image / generative model (model + editable steps/cfg).
    Returns (llm_model, srv_str, chunking_size, img_model_or_None, img_params).
    Cancel / close exits cleanly.
    """
    import tkinter as tk

    if not models:
        _notify("No .gguf model found in the models\\ folder.\n"
                "Download a model and place it there, then relaunch.",
                "A.N.S.E.L.M.O -- no model")
        sys.exit(1)

    result: dict = {}

    root = tk.Tk()
    root.title("A.N.S.E.L.M.O -- choose your models")
    try:
        root.iconbitmap(str(BASE / "selmo.ico"))
    except Exception:
        pass
    root.configure(padx=14, pady=12)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(400, lambda: root.attributes("-topmost", False))

    # ---- LEFT column: language model ------------------------------------
    left = tk.LabelFrame(root, text=" Language model (LLM) ",
                         font=("Segoe UI", 10, "bold"), padx=10, pady=8)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

    lb = tk.Listbox(left, height=min(max(len(models), 4), 12), width=58,
                    activestyle="dotbox", exportselection=False)
    for m in models:
        info = _match_ini(m["name"], sections, default)
        note = info.get("note", "")
        lb.insert("end", f"{m['name']}  --  {note}" if note else m["name"])
    lb.selection_set(0)
    lb.grid(row=0, column=0, columnspan=2, sticky="we")

    note_var = tk.StringVar()
    srv_var  = tk.StringVar()
    cs_var   = tk.StringVar()

    tk.Label(left, textvariable=note_var, fg="#555", wraplength=420,
             justify="left").grid(row=1, column=0, columnspan=2,
                                  sticky="w", pady=(6, 8))
    tk.Label(left, text="Server args").grid(row=2, column=0, sticky="w")
    tk.Entry(left, textvariable=srv_var, width=56) \
        .grid(row=3, column=0, columnspan=2, sticky="we", pady=(0, 8))
    tk.Label(left, text="Chunking size").grid(row=4, column=0, sticky="w")
    tk.Entry(left, textvariable=cs_var, width=12) \
        .grid(row=4, column=1, sticky="w")

    def _on_llm(_evt=None):
        idx = lb.curselection()
        if not idx:
            return
        info = _match_ini(models[idx[0]]["name"], sections, default)
        note_var.set(f"Native max ctx: {info.get('max', 'unknown')}")
        srv_var.set(info["srv"])
        cs_var.set(str(info["chunking_size"]))

    lb.bind("<<ListboxSelect>>", _on_llm)
    _on_llm()

    # ---- hover tooltip: the long bird description per model -------------
    _tip = {"win": None, "idx": -1}

    def _tip_hide(_evt=None):
        if _tip["win"] is not None:
            _tip["win"].destroy()
            _tip["win"] = None
        _tip["idx"] = -1

    def _tip_motion(ev):
        if not models:
            return
        idx = lb.nearest(ev.y)
        if idx < 0 or idx >= len(models):
            _tip_hide()
            return
        if idx == _tip["idx"]:
            return
        info = _match_ini(models[idx]["name"], sections, default)
        text = info.get("tip", "") or info.get("note", "")
        _tip_hide()
        if not text:
            return
        tw = tk.Toplevel(lb)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{lb.winfo_pointerx() + 16}+{lb.winfo_pointery() + 14}")
        tk.Label(tw, text=text, justify="left", bg="#ffffe0", fg="#333",
                 relief="solid", borderwidth=1, wraplength=340,
                 font=("Segoe UI", 9), padx=6, pady=4).pack()
        _tip["win"] = tw
        _tip["idx"] = idx

    lb.bind("<Motion>", _tip_motion)
    lb.bind("<Leave>", _tip_hide)

    # ---- RIGHT column: image / generative model -------------------------
    right = tk.LabelFrame(root, text=" Image model (generative) ",
                          font=("Segoe UI", 10, "bold"), padx=10, pady=8)
    right.grid(row=0, column=1, sticky="nsew")

    inote_var   = tk.StringVar()
    ifiles_var  = tk.StringVar()
    iparams_var = tk.StringVar()

    ilb = tk.Listbox(right, height=min(max(len(img_models), 4), 12), width=58,
                     activestyle="dotbox", exportselection=False)
    if img_models:
        for m in img_models:
            info = _match_ini(m["name"], isections, idefault)
            note = info.get("note", "")
            ilb.insert("end", f"{m['name']}  --  {note}" if note else m["name"])
        ilb.selection_set(0)
    else:
        ilb.insert("end", "(no diffusion model found in image\\)")
        ilb.configure(state="disabled", fg="#999")
    ilb.grid(row=0, column=0, columnspan=2, sticky="we")

    tk.Label(right, textvariable=inote_var, fg="#555", wraplength=420,
             justify="left").grid(row=1, column=0, columnspan=2,
                                  sticky="w", pady=(6, 4))
    tk.Label(right, textvariable=ifiles_var, fg="#888", wraplength=420,
             justify="left", font=("Consolas", 8)) \
        .grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
    tk.Label(right, text="Params (steps, cfg)").grid(row=3, column=0, sticky="w")
    tk.Entry(right, textvariable=iparams_var, width=56) \
        .grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 8))

    def _on_img(_evt=None):
        if not img_models:
            return
        idx = ilb.curselection()
        if not idx:
            return
        info = _match_ini(img_models[idx[0]]["name"], isections, idefault)
        inote_var.set(info.get("note", "") or "(no note)")
        ifiles_var.set("fixed: " + info["files"])
        iparams_var.set(info["params"])

    if img_models:
        ilb.bind("<<ListboxSelect>>", _on_img)
        _on_img()

    # ---- hover tooltip: the long description per image model ------------
    _itip = {"win": None, "idx": -1}

    def _itip_hide(_evt=None):
        if _itip["win"] is not None:
            _itip["win"].destroy()
            _itip["win"] = None
        _itip["idx"] = -1

    def _itip_motion(ev):
        if not img_models:
            return
        idx = ilb.nearest(ev.y)
        if idx < 0 or idx >= len(img_models):
            _itip_hide()
            return
        if idx == _itip["idx"]:
            return
        info = _match_ini(img_models[idx]["name"], isections, idefault)
        text = info.get("tip", "") or info.get("note", "")
        _itip_hide()
        if not text:
            return
        tw = tk.Toplevel(ilb)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{ilb.winfo_pointerx() + 16}+{ilb.winfo_pointery() + 14}")
        tk.Label(tw, text=text, justify="left", bg="#ffffe0", fg="#333",
                 relief="solid", borderwidth=1, wraplength=340,
                 font=("Segoe UI", 9), padx=6, pady=4).pack()
        _itip["win"] = tw
        _itip["idx"] = idx

    if img_models:
        ilb.bind("<Motion>", _itip_motion)
        ilb.bind("<Leave>", _itip_hide)

    # ---- buttons ---------------------------------------------------------
    def _launch(_evt=None):
        idx = lb.curselection()
        if not idx:
            return
        m    = models[idx[0]]
        info = _match_ini(m["name"], sections, default)
        srv  = srv_var.get().strip() or info["srv"]
        cs   = cs_var.get().strip()
        csize = int(cs) if cs.isdigit() else int(info["chunking_size"])
        sel_img = None
        iparams = ""
        if img_models:
            iidx = ilb.curselection()
            if iidx:
                sel_img = img_models[iidx[0]]
                iparams = iparams_var.get().strip()
        result.update({"sel": m, "srv": srv, "csize": csize,
                       "img": sel_img, "iparams": iparams})
        root.destroy()

    def _cancel(_evt=None):
        root.destroy()

    btns = tk.Frame(root)
    btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
    tk.Button(btns, text="Launch", width=12, default="active",
              command=_launch).pack(side="right", padx=(6, 0))
    tk.Button(btns, text="Cancel", width=10,
              command=_cancel).pack(side="right")

    root.bind("<Return>", _launch)
    root.bind("<Escape>", _cancel)
    lb.bind("<Double-Button-1>", _launch)
    if img_models:
        ilb.bind("<Double-Button-1>", _launch)
    root.mainloop()

    if "sel" not in result:
        sys.exit(0)        # cancelled / closed
    return (result["sel"], result["srv"], result["csize"],
            result["img"], result["iparams"])


# ============================================================
#  llama-server management
# ============================================================

STRUCTURAL = {"--model", "-m", "--host", "--port", "--path"}

_HAS_NVIDIA = None  # cached hardware probe (None = not yet checked)


def _has_nvidia_gpu() -> bool:
    """True if an NVIDIA GPU is present (nvidia-smi). Cached for the run --
    hardware does not change during a session."""
    global _HAS_NVIDIA
    if _HAS_NVIDIA is None:
        try:
            out = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                                 text=True, timeout=8, creationflags=NO_WINDOW)
            _HAS_NVIDIA = (out.returncode == 0 and "GPU" in out.stdout)
        except Exception:
            _HAS_NVIDIA = False
    return _HAS_NVIDIA


def _adapt_srv_for_cpu(srv_str: str) -> str:
    """No NVIDIA GPU -> rewrite GPU-tuned flags so a model still loads well on a
    CPU-only PC: -ngl 0 (keep every layer on CPU), drop --no-mmap (let the
    weights be memory-mapped / evictable under low RAM), drop --n-cpu-moe (a GPU
    offload knob, meaningless on CPU). Purely a textual switch on the srv string;
    on a GPU box it is returned unchanged. The launcher still shows/edits the
    original srv, so this only changes what is actually handed to llama-server."""
    if _has_nvidia_gpu():
        return srv_str
    toks = shlex.split(srv_str) if srv_str else []
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in ("-ngl", "--n-gpu-layers", "--gpu-layers"):
            out += [t, "0"]; i += 2; continue
        if t == "--no-mmap":
            i += 1; continue
        if t == "--n-cpu-moe":
            i += 2; continue
        out.append(t); i += 1
    adapted = " ".join(out)
    if adapted != srv_str:
        try:
            print(f"  [cpu] no NVIDIA GPU -> CPU-safe flags: {adapted}")
        except Exception:
            pass
    return adapted


def _build_cmd(model_path: str, srv_str: str, mmproj: str | None) -> list[str]:
    srv_str = _adapt_srv_for_cpu(srv_str)   # GPU-less PC -> CPU-safe launch flags
    cmd = [
        str(LLAMA_EXE),
        "--model", model_path,
        # llama-server now sits BEHIND the front door (selmo_https_proxy.py
        # owns 8080 and serves chat.html). The LLM listens on a private
        # loopback port; the front door proxies /proxy/8089 -> here. This
        # lets the v0.830 VRAM swap unload/reload the LLM without taking
        # the web UI (now served by the front door) down with it.
        "--host",  "127.0.0.1",
        "--port",  "8089",
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
        _tray_icon.title = f"A.N.S.E.L.M.O  --  {_current['name']}  [unloaded]"


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
        _tray_icon.title = f"A.N.S.E.L.M.O  --  {_current['name']}"
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


def _reload_current_llm() -> bool:
    """
    Relaunch llama-server with the currently selected model + flags.
    Clears the image-swap flag.  Returns True if a (re)launch happened.
    Callers must already hold _ctrl_lock.
    """
    if _current["loaded"]:
        _current["swapped_for_image"] = False
        return False
    models = _scan_models(BASE)
    m = next((x for x in models if x["name"] == _current["name"]), None)
    if m is None:
        return False
    _launch_llama(m["path"], _current["srv"], _current["mmproj"])
    _current["swapped_for_image"] = False
    return True


# ============================================================
#  Control API  (port 8087)  -- LLM load/unload coordination
# ============================================================
#
#  The image bridge (selmo_image.py, 8086) runs in its own process and cannot
#  touch the llama-server the tray owns.  Before an image generation it POSTs
#  /llm/unload here so the LLM frees the GPU; the next chat turn POSTs
#  /llm/reload (via chat.html's ensureLLM) to bring it back -- lazy reload.

class _CtrlHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # silence per-request logging

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _status(self):
        return {
            "loaded":            _current["loaded"],
            "name":              _current["name"],
            "swapped_for_image": _current.get("swapped_for_image", False),
        }

    def _unload(self):
        with _ctrl_lock:
            was = _current["loaded"]
            if was:
                _stop_llama()
                _current["swapped_for_image"] = True
                if _tray_icon:
                    _tray_icon.title = f"A.N.S.E.L.M.O  --  {_current['name']}  [image mode]"
        self._send(200, {"ok": True, "was_loaded": was,
                         "swapped_for_image": _current.get("swapped_for_image", False)})

    def _reload(self):
        with _ctrl_lock:
            relaunched = _reload_current_llm()
        if _tray_icon and _current["loaded"]:
            _tray_icon.title = f"A.N.S.E.L.M.O  --  {_current['name']}"
        self._send(200, {"ok": True, "relaunched": relaunched,
                         "loaded": _current["loaded"]})

    # -- model switching (tray-in-browser, v0.903) ------------------------
    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n <= 0:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception:
            return {}

    def _models(self):
        sections, default = _parse_ini(BASE / "selmo-models.ini")
        out = []
        for m in _scan_models(BASE):
            info = _match_ini(m["name"], sections, default)
            out.append({"name": m["name"], "srv": info["srv"],
                        "chunking_size": info["chunking_size"],
                        "note": info["note"], "tip": info["tip"]})
        return {
            "models":            out,
            "current":           _current["name"],
            "loaded":            _current["loaded"],
            "swapped_for_image": _current.get("swapped_for_image", False),
        }

    def _switch(self):
        body = self._read_json()
        name = (body.get("name") or "").strip()
        if not name:
            self._send(400, {"ok": False, "error": "missing 'name'"})
            return
        model = next((m for m in _scan_models(BASE) if m["name"] == name), None)
        if model is None:
            self._send(404, {"ok": False, "error": "model not found: " + name})
            return
        srv = body.get("srv")
        srv = srv.strip() if isinstance(srv, str) and srv.strip() else None
        csize = body.get("chunking_size")
        try:
            csize = int(csize) if csize not in (None, "") else None
        except (TypeError, ValueError):
            csize = None
        sections, default = _parse_ini(BASE / "selmo-models.ini")
        with _ctrl_lock:
            _action_switch(model, {"sections": sections, "default": default}, srv, csize)
        self._send(200, {"ok": True, "name": name, "loaded": _current["loaded"]})

    def _image_models(self):
        isec, idef = _parse_image_ini(BASE / "selmo-image-models.ini")
        cur = ""
        try:
            cur = json.loads((BASE / "selmo-image-config.json").read_text(
                encoding="utf-8")).get("name", "")
        except Exception:
            pass
        out = []
        for m in _scan_image_models(BASE):
            info = _match_ini(m["name"], isec, idef)
            out.append({"name": m["name"], "params": info["params"],
                        "note": info["note"], "tip": info["tip"]})
        return {"models": out, "current": cur}

    def _image_select(self):
        body = self._read_json()
        name = (body.get("name") or "").strip()
        if not name:
            self._send(400, {"ok": False, "error": "missing 'name'"})
            return
        model = next((m for m in _scan_image_models(BASE) if m["name"] == name), None)
        if model is None:
            self._send(404, {"ok": False, "error": "image model not found: " + name})
            return
        isec, idef = _parse_image_ini(BASE / "selmo-image-models.ini")
        params = body.get("params")
        params = params.strip() if isinstance(params, str) and params.strip() else None
        cfg = _image_config(model, isec, idef, params)
        (BASE / "selmo-image-config.json").write_text(json.dumps(cfg), encoding="utf-8")
        self._send(200, {"ok": True, "name": name})

    def _reveal(self):
        # Open the models directory itself in Windows Explorer (kind = llm ->
        # models\, image -> image\). Opening the folder (not a selected file)
        # means it works even on a fresh install with no models yet. kind is a
        # fixed enum, so no arbitrary path reaches the unauthenticated 8087 port.
        # os.startfile uses the shell "open" verb, which raises a NEW Explorer
        # window to the foreground (focused, not minimized) so the user can't
        # miss it and keep clicking.
        body = self._read_json()
        kind = (body.get("kind") or "llm").strip()
        folder = (BASE / "image") if kind == "image" else (BASE / "models")
        try:
            folder.mkdir(parents=True, exist_ok=True)
            # Windows blocks a background process (the tray) from stealing the
            # foreground, so the Explorer window may only flash in the taskbar
            # rather than pop up. We don't fight that (a foreground-lock override
            # mutates a system-wide setting for little gain); the client shows an
            # in-app notice telling the user to check the taskbar instead.
            os.startfile(str(folder))
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})
            return
        self._send(200, {"ok": True, "folder": str(folder)})

    def _exit(self):
        # Reply first, then tear everything down off-thread so the response
        # actually reaches the browser before the process dies.
        self._send(200, {"ok": True})
        try:
            self.wfile.flush()
        except Exception:
            pass
        threading.Timer(0.4, lambda: (_cleanup(), os._exit(0))).start()

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/status":
            self._send(200, self._status())
        elif p == "/models":
            self._send(200, self._models())
        elif p == "/image/models":
            self._send(200, self._image_models())
        elif p == "/llm/reload":
            self._reload()
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        if p == "/llm/unload":
            self._unload()
        elif p == "/llm/reload":
            self._reload()
        elif p == "/llm/switch":
            self._switch()
        elif p == "/image/select":
            self._image_select()
        elif p == "/reveal":
            self._reveal()
        elif p == "/control/exit":
            self._exit()
        else:
            self._send(404, {"error": "not found"})


def _start_control_server():
    try:
        # Loopback only. The control API load/unloads the LLM and can shut the
        # whole app down (/control/exit); it must never be directly reachable
        # from the LAN. The client reaches it through the front door
        # (/proxy/8087), which connects over 127.0.0.1. (security review)
        srv = ThreadingHTTPServer(("127.0.0.1", CTRL_PORT), _CtrlHandler)
    except Exception as e:
        print(f"  -> Control API   [port {CTRL_PORT}] FAILED to bind ({e})", flush=True)
        return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"  -> Control API   [port {CTRL_PORT}] (LLM load/unload)", flush=True)


# ============================================================
#  Tray actions
# ============================================================

def _action_unload(icon, item):
    """Stop llama-server to free VRAM; all other services keep running.
    A manual unload is intentional, so it does NOT set swapped_for_image
    (the next chat must not silently reload)."""
    if not _current["loaded"]:
        return
    with _ctrl_lock:
        _stop_llama()
        _current["swapped_for_image"] = False
    if icon:
        icon.title = f"A.N.S.E.L.M.O  --  {_current['name']}  [unloaded]"


def _action_reload(icon, item):
    """Restart llama-server with the currently configured model."""
    if _current["loaded"]:
        return
    with _ctrl_lock:
        _reload_current_llm()


def _action_switch(model: dict, ini_data: dict, srv_override=None, csize_override=None):
    """Stop current llama-server and start a new one.

    srv_override / csize_override let the browser settings panel edit the exact
    server flags + chunking size at switch time (the old tray 'show + retype').
    The chosen model is persisted to selmo-state.json so the next startup
    auto-loads it without any picker."""
    _stop_llama()

    sections = ini_data["sections"]
    default  = ini_data["default"]
    info     = _match_ini(model["name"], sections, default)
    srv      = info["srv"]            if srv_override   is None else srv_override
    csize    = info["chunking_size"]  if csize_override is None else csize_override
    mmproj   = _find_mmproj(model["dir"])

    (BASE / "selmo-config.json").write_text(
        json.dumps({"chunking_size": csize, "think": info.get("think", ""), "vision": bool(mmproj)}),
        encoding="utf-8"
    )
    _current.update({"name": model["name"], "srv": srv, "mmproj": mmproj})
    _save_last_model(model["name"])

    _launch_llama(model["path"], srv, mmproj)

    if _tray_icon:
        _tray_icon.title = f"A.N.S.E.L.M.O  --  {model['name']}"


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
    _start_service("Front door    [8080+8443]", [str(BASE / "selmo_https_proxy.py")])
    _start_control_server()
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
                    f"A.N.S.E.L.M.O  --  {_current['name'][:32]}"
                    + ("  [unloaded]" if not _current["loaded"] else "")
                ),
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Open A.N.S.E.L.M.O in browser", _open_browser),
            pystray.MenuItem("View log file",          _view_log),
            pystray.Menu.SEPARATOR,

            # model switching now lives in the browser settings panel; the tray
            # only manages the backend and shows the model in use (status header).
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
        _notify("A.N.S.E.L.M.O is already running.\nCheck the system tray.")
        sys.exit(0)

    ini_path          = BASE / "selmo-models.ini"
    sections, default = _parse_ini(ini_path)
    models            = _scan_models(BASE)

    img_ini_path        = BASE / "selmo-image-models.ini"
    isections, idefault = _parse_image_ini(img_ini_path)
    img_models          = _scan_image_models(BASE)

    border  = "  +" + "-" * 44 + "+"
    boxline = lambda s: "  |" + s.center(44) + "|"
    print()
    print(border)
    print(boxline("A.N.S.E.L.M.O  --  local AI, GDPR by design"))
    print(boxline("Your data stays on your computer."))
    print(border)
    print()

    # No startup picker: auto-load the last-used model (selmo-state.json).
    # Switching models + editing flags now happen in the browser settings panel;
    # the tray only manages the backend and shows the model in use.
    last = _load_last_model()
    sel  = next((m for m in models if m["name"] == last), None) or (models[0] if models else None)
    srv, csize, mmproj = "", DEFAULT_CSIZE, None
    if sel is None:
        print("  No models found in models\\ -- add one, then load it from the browser.")
    else:
        info   = _match_ini(sel["name"], sections, default)
        srv    = info["srv"]
        csize  = info["chunking_size"]
        mmproj = _find_mmproj(sel["dir"])
        vis    = f"on  ({Path(mmproj).name})" if mmproj else "text only"
        print(f"  Auto-loading last model:  {sel['name']}")
        print(f"  Vision   :  {vis}")
        print(f"  Chunking :  {csize} tokens / chunk")
        (BASE / "selmo-config.json").write_text(
            json.dumps({"chunking_size": csize, "think": info.get("think", ""), "vision": bool(mmproj)}),
            encoding="utf-8"
        )
        _current.update({"name": sel["name"], "srv": srv, "mmproj": mmproj, "loaded": False})
        _save_last_model(sel["name"])
    print()

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

    if sel is not None:
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
            title = f"A.N.S.E.L.M.O  --  {sel['name']}" if sel else "A.N.S.E.L.M.O  --  no model (load one in the browser)",
            menu  = pystray.Menu(menu_fn),
        )
        _tray_icon = icon

        print("  Tray icon active -- A.N.S.E.L.M.O is now running in the tray.")
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
