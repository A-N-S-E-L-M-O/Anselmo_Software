' Selmo launcher -- starts the tray under pythonw.exe with NO console.
' Window style 0 = hidden, so nothing flashes at startup and there is
' no taskbar button.  Double-click this file (or put a shortcut to it in
' shell:startup) to run Selmo.  Requires Python on PATH (same as before).
Option Explicit
Dim sh, base, full
Set sh = CreateObject("WScript.Shell")
full = WScript.ScriptFullName
base = Left(full, InStrRev(full, "\"))
sh.CurrentDirectory = base
sh.Run "pythonw """ & base & "selmo_tray.py""", 0, False
