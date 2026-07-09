#!/usr/bin/env python3
"""Create a Selmo shortcut (Selmo.lnk) with the Selmo icon on the Desktop and in
the Start menu, so a non-technical user gets a clickable "Selmo face" to launch -
and to pin to the taskbar - instead of hunting for Selmo.cmd.

Windows-only and stdlib-only: it shells out to PowerShell's WScript.Shell to make
the .lnk (no pywin32 in the embeddable bundle). The shortcut targets the bundled
pythonw.exe with installer\\boot.py as its argument - because the target is a real
.exe, Windows allows pinning it to the taskbar (a .cmd cannot be pinned).

Called once on first launch from boot.py, and also runnable on its own via
Create-Selmo-Shortcut.cmd in the Selmo folder. Safe to re-run: it overwrites.
"""
import os, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PYW  = BASE / "python" / "pythonw.exe"
BOOT = BASE / "installer" / "boot.py"
ICO  = BASE / "selmo.ico"

_PS = r'''
$W = New-Object -ComObject WScript.Shell
$targets = @([Environment]::GetFolderPath('Desktop'))
$progs = Join-Path ([Environment]::GetFolderPath('Programs')) 'Selmo'
New-Item -ItemType Directory -Force -Path $progs | Out-Null
$targets += $progs
foreach ($d in $targets) {
  $lnk = $W.CreateShortcut((Join-Path $d 'Selmo.lnk'))
  $lnk.TargetPath = __TARGET__
  $lnk.Arguments = __ARGS__
  $lnk.WorkingDirectory = __WORKDIR__
  $lnk.IconLocation = __ICON__
  $lnk.Description = 'Selmo - local AI on your own PC'
  $lnk.Save()
}
'''

def _q(s):
    # PowerShell single-quoted literal (escape ' by doubling it)
    return "'" + str(s).replace("'", "''") + "'"

def make_shortcut():
    """Create/refresh the Selmo shortcut. Returns True on success. Never raises."""
    if os.name != "nt":
        return False
    target = PYW if PYW.exists() else Path(sys.executable)
    ps = (_PS
          .replace("__TARGET__", _q(target))
          .replace("__ARGS__", _q('"' + str(BOOT) + '"'))
          .replace("__WORKDIR__", _q(BASE))
          .replace("__ICON__", _q(str(ICO) + ",0")))
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=True)
        return True
    except Exception as e:
        print(f"  [skip] could not create the Selmo shortcut ({e})")
        return False

if __name__ == "__main__":
    if make_shortcut():
        print("  Done - the Selmo icon is on your Desktop (and in the Start menu).")
        print("  Tip: right-click it and choose 'Pin to taskbar' to keep it handy.")
    else:
        print("  Could not create the shortcut on this system.")
    try:
        if sys.stdin and sys.stdin.isatty():
            input("\n  Press ENTER to close...")
    except Exception:
        pass
