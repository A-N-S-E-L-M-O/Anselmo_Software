#Requires -Version 5.1
<#
  setup-lhm.ps1  --  Selmo: install & configure LibreHardwareMonitor as the
  system-power source. It exposes CPU package + GPU watts (vendor-agnostic) at
  http://127.0.0.1:8085/data.json, which selmo_gpu_monitor.py reads.

  Fully reproducible, no manual GUI step:
    1. download a PINNED LHM release into bin\LibreHardwareMonitor\
    2. write LibreHardwareMonitor.config (web server on :8085, start minimized, tray)
    3. register a Scheduled Task that runs LHM ELEVATED at logon (RAPL needs admin),
       so there is no UAC prompt on every boot.

  Run once (self-elevates if needed):
    powershell -ExecutionPolicy Bypass -File setup-lhm.ps1

  Flags:
    -Version v0.9.4   pin a different release
    -Port 8085        web server port (must match selmo_gpu_monitor.py)
    -NoTask           do not create the scheduled task (selmo_server.py launches it on demand)
    -NoDownload       assume the exe is already in bin\LibreHardwareMonitor\
#>
[CmdletBinding()]
param(
  [string]$Version = "v0.9.4",
  [int]$Port = 8085,
  [switch]$NoTask,
  [switch]$NoDownload,
  [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$Base   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dest   = Join-Path $Base "bin\LibreHardwareMonitor"
$Exe    = Join-Path $Dest "LibreHardwareMonitor.exe"
$Config = Join-Path $Dest "LibreHardwareMonitor.config"
$Asset  = "LibreHardwareMonitor-net472.zip"
$Url    = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/$Version/$Asset"

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

# Self-elevate: registering the task and the first RAPL read need admin.
if (-not (Test-Admin)) {
  Write-Host "Elevating (admin needed for the scheduled task / RAPL driver)..."
  $a = "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" -Version $Version -Port $Port"
  if ($NoTask)     { $a += " -NoTask" }
  if ($NoDownload) { $a += " -NoDownload" }
  if ($Uninstall)  { $a += " -Uninstall" }
  Start-Process powershell -Verb RunAs -ArgumentList $a
  return
}

# Uninstall: stop LHM, remove the scheduled task, delete the folder.
if ($Uninstall) {
  $taskName = "SelmoLibreHardwareMonitor"
  Write-Host "Removing scheduled task '$taskName'..."
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
  Get-Process LibreHardwareMonitor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  if (Test-Path $Dest) {
    Write-Host "Deleting $Dest ..."
    Remove-Item $Dest -Recurse -Force -ErrorAction SilentlyContinue
  }
  Write-Host "LibreHardwareMonitor removed. The energy monitor falls back to the on-screen estimate."
  return
}

# 1) Download + extract (pinned -> reproducible)
if (-not $NoDownload) {
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  $zip = Join-Path $env:TEMP $Asset
  Write-Host "Downloading $Asset ($Version)..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
  Write-Host "Extracting to $Dest ..."
  Expand-Archive -Path $zip -DestinationPath $Dest -Force
  Remove-Item $zip -ErrorAction SilentlyContinue
}

# Locate the exe (the zip is flat, but tolerate a nested folder just in case)
$found = Get-ChildItem -Path $Dest -Recurse -Filter "LibreHardwareMonitor.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($found) {
  $Exe = $found.FullName
  $Dest = $found.DirectoryName
  $Config = Join-Path $Dest "LibreHardwareMonitor.config"
}
if (-not (Test-Path $Exe)) {
  throw "LibreHardwareMonitor.exe not found under $Dest. Re-run without -NoDownload, or place it there."
}

# 2) Config: web server on, start minimized, live in the tray (no manual GUI step)
Write-Host "Writing config (web server on :$Port, start minimized)..."
$cfg = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <appSettings>
    <add key="runWebServerMenuItem" value="true" />
    <add key="listenerPort" value="$Port" />
    <add key="startMinMenuItem" value="true" />
    <add key="minTrayMenuItem" value="true" />
    <add key="minCloseMenuItem" value="true" />
  </appSettings>
</configuration>
"@
Set-Content -Path $Config -Value $cfg -Encoding UTF8

# 3) Scheduled task: run LHM elevated at logon -> no UAC on every boot
if (-not $NoTask) {
  $taskName = "SelmoLibreHardwareMonitor"
  Write-Host "Registering scheduled task '$taskName' (elevated, at logon)..."
  $action    = New-ScheduledTaskAction -Execute $Exe
  $trigger   = New-ScheduledTaskTrigger -AtLogOn
  $user      = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
  $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Write-Host "Starting it now..."
  Start-ScheduledTask -TaskName $taskName
} else {
  Write-Host "Skipped scheduled task (-NoTask). selmo_server.py will launch LHM on demand."
}

Write-Host ""
Write-Host "Done. In a few seconds check  http://127.0.0.1:$Port/data.json"
Write-Host "You should see CPU Package and GPU power values in watts."
