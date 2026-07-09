#!/usr/bin/env python3
"""
Selmo boot entry. The shortcut runs this with the bundled pythonw.exe (a signed
executable -- no loose .vbs/.cmd for antivirus to quarantine). On first run it
opens a visible console for first_run.py (downloads the llama.cpp engine
with a progress bar); then it starts Selmo via the system tray (selmo_tray.py),
which gives the tray icon and the 8087 control API the browser UI needs.
"""
import os, subprocess, sys
from pathlib import Path

BASE   = Path(__file__).resolve().parent.parent
PY     = BASE / "python" / "python.exe"
PYW    = BASE / "python" / "pythonw.exe"
SERVER = BASE / "bin" / "llama-server.exe"   # the engine; models are user-supplied
py     = PY  if PY.exists()  else Path(sys.executable)
pyw    = PYW if PYW.exists() else Path(sys.executable)

def ready():
    return SERVER.exists()

# First run: download the engine (backend) in a visible console window.
if not ready():
    subprocess.run([str(py), str(BASE / "installer" / "first_run.py")],
                   creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))

if not ready():
    sys.exit(0)   # user cancelled or download failed

# First launch only: drop a Selmo icon (Selmo.lnk, the Selmo face) on the
# Desktop + Start menu so there is a clickable, taskbar-pinnable launcher
# instead of the bare .cmd. Guarded by a marker so it runs just once; any
# failure here must never block the launch.
_marker = BASE / ".selmo-shortcut-done"
if os.name == "nt" and not _marker.exists():
    try:
        sys.path.insert(0, str(BASE / "installer"))
        from make_shortcut import make_shortcut
        make_shortcut()
    except Exception:
        pass
    try:
        _marker.write_text("1", encoding="utf-8")
    except Exception:
        pass

# Start Selmo via the tray (icon + 8087 control API + auto-loads the model).
subprocess.Popen([str(pyw), str(BASE / "selmo_tray.py")], cwd=str(BASE))
