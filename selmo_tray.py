"""
selmo_tray.py  --  Selmo tray launcher  (v0.9)

Replaces Selmo.bat.  Reads selmo-models.ini, shows the same text
console picker, then detaches from the console and runs as a
pure system-tray app.

Behaviour
  - Console window is used for the model picker and startup messages,
    then automatically closed via FreeConsole() -- the process keeps
    running (tray stays).  No need to keep a terminal open.
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
#  Console detach  (FreeConsole)
# ============================================================

def _detach_console():
    """
    Redirect stdout/stderr to devnull, then call FreeConsole().
    The console window closes; the process (and tray) keeps running.
    Must be called from the main thread, after all console I/O is done.
    """
    if sys.platform != "win32":
        return
    # Flush and redirect before releasing the console handle
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    try:
        nul = open(os.devnull, "w")
        sys.stdout = nul
        sys.stderr = nul
    except Exception:
        pass
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    # FreeConsole() removed: keeping process attached so that
    # closing this window sends CTRL_CLOSE_EVENT -> _ctrl_handler
    if hwnd:
        print("Selmo is running in the tray.  "
              "Close this window to quit.", flush=True)
        ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    # Do NOT send WM_CLOSE here -- that can kill the host terminal.
    # The window is already gone because FreeConsole released it;
    # the tray icon is now the only way to quit Selmo.


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
        _tray_icon.title = f"Selmo  --  {_current['name']}  [unloaded]"


def _launch_llama(model_path: str, srv_str: str, mmproj: str | None):
    global _llama_proc
    cmd = _build_cmd(model_path, srv_str, mmproj)
    p   = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with _llama_lock:
        _llama_proc = p
    _current["loaded"] = True
    if _tray_icon:
        _tray_icon.title = f"Selmo  --  {_current['name']}"
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
        icon.title = f"Selmo  --  {_current['name']}  [unloaded]"


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
        _tray_icon.title = f"Selmo  --  {model['name']}"


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
    """64x64 RGBA: rounded navy square + bold white S."""
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
    icon.stop()


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
                    f"Selmo  --  {_current['name'][:32]}"
                    + ("  [unloaded]" if not _current["loaded"] else "")
                ),
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,

            pystray.MenuItem("Open Selmo in browser", _open_browser),
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

    # -- single-instance guard --------------------------------------------
    if not _claim_instance():
        print("Selmo is already running.  Check the system tray.", flush=True)
        time.sleep(3)
        sys.exit(0)

    ini_path          = BASE / "selmo-models.ini"
    sections, default = _parse_ini(ini_path)
    models            = _scan_models(BASE)

    border  = "  +" + "-" * 44 + "+"
    boxline = lambda s: "  |" + s.center(44) + "|"
    print()
    print(border)
    print(boxline("Selmo  --  local AI, GDPR by design"))
    print(boxline("Your data stays on your computer."))
    print(border)
    print()

    sel, srv, csize = _text_picker(models, sections, default)
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

    # -- tray path: detach console and hand off to pystray ----------------
    if HAS_TRAY:
        ini_data = {"sections": sections, "default": default}
        menu_fn  = _build_menu(models, ini_data)

        icon = pystray.Icon(
            name  = "selmo",
            icon  = _make_icon_image(),
            title = f"Selmo  --  {sel['name']}",
            menu  = pystray.Menu(menu_fn),
        )
        _tray_icon = icon

        print()
        print("  Tray icon active -- moving to tray now.")
        print("  Right-click tray icon to switch models, view log, or exit.")
        print()
        time.sleep(1)       # let the user read the last messages

        _detach_console()   # closes console window; process keeps running

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
