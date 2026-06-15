# make-shortcut.ps1 -- create a pinnable Selmo shortcut with the Selmo icon.
# Run once:  right-click -> Run with PowerShell  (or:  powershell -ExecutionPolicy Bypass -File make-shortcut.ps1)
# Makes Selmo.lnk in this folder and on the Desktop; both launch the tray with
# no console window and show selmo.ico.  Right-click the .lnk to pin it.
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
$vbs  = Join-Path $base 'Selmo.vbs'
$ico  = Join-Path $base 'selmo.ico'
if (-not (Test-Path $vbs)) { throw "Selmo.vbs not found next to this script." }
if (-not (Test-Path $ico)) { throw "selmo.ico not found next to this script." }

$ws = New-Object -ComObject WScript.Shell

function New-SelmoShortcut($path) {
    $sc = $ws.CreateShortcut($path)
    $sc.TargetPath       = Join-Path $env:WINDIR 'System32\wscript.exe'
    $sc.Arguments        = '"' + $vbs + '"'
    $sc.WorkingDirectory = $base
    $sc.IconLocation     = "$ico,0"
    $sc.Description       = 'Selmo - local AI'
    $sc.Save()
    Write-Host "Created: $path"
}

New-SelmoShortcut (Join-Path $base 'Selmo.lnk')
New-SelmoShortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Selmo.lnk')
Write-Host 'Done. Right-click Selmo.lnk -> Pin to taskbar (or Pin to Start).'
