<#
  build-bundle.ps1  -- run ONCE on Windows to stage the distributable tree.
  Produces .\dist\  containing a self-contained Selmo: an embeddable Python
  (the target PC needs NOTHING installed), the minimal deps, the app files and
  a CPU-only llama.cpp. Inno Setup (Selmo.iss) then packages .\dist\ into
  SelmoSetup.exe. Models are NOT bundled -- they download on first run.

  Usage (from the Selmo repo root):
      powershell -ExecutionPolicy Bypass -File installer\build-bundle.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot          # repo root (installer\ is under it)
$Dist = Join-Path $Root "dist"
$PyVer = "3.11.9"                                  # embeddable build to pin
$PyZip = "python-$PyVer-embed-amd64.zip"
$PyUrl = "https://www.python.org/ftp/python/$PyVer/$PyZip"

Write-Host "== Selmo bundle build ==" -ForegroundColor Cyan
if (Test-Path $Dist) { Remove-Item $Dist -Recurse -Force }
New-Item -ItemType Directory -Path $Dist | Out-Null

# ---- 1. embeddable Python -------------------------------------------------
$PyDir = Join-Path $Dist "python"
New-Item -ItemType Directory -Path $PyDir | Out-Null
$zip = Join-Path $env:TEMP $PyZip
Write-Host "Downloading $PyUrl"
Invoke-WebRequest -Uri $PyUrl -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $PyDir -Force

# enable site-packages so pip-installed modules are importable
$pth = Get-ChildItem $PyDir -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName
Add-Content $pth.FullName "import site"

# bootstrap pip
$getpip = Join-Path $env:TEMP "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
& "$PyDir\python.exe" $getpip --no-warn-script-location

# ---- 2. minimal deps (chat + web search + power gauge + HTTPS) ------------
#   NOT bundled on purpose: flask/faster-whisper/kokoro (voice) and torch --
#   too heavy for a "try it" build. Voice/image stay in the full edition.
#   cryptography IS required: selmo_https_proxy.py uses it to mint the
#   self-signed cert on first run (the cert/key are excluded from the bundle).
#   Without it there is no cert -> port 8443 stays down and the phone button
#   (which reads the LAN IP the cert step writes to selmo-cert-ip.txt) vanishes.
& "$PyDir\python.exe" -m pip install --no-warn-script-location `
    trafilatura requests psutil pynvml pystray Pillow cryptography

# ---- 3. app files ---------------------------------------------------------
#   NEVER bundle secrets or per-machine runtime state: selmo.key/selmo.crt
#   (TLS private key + cert, carry the LAN IP), selmo-cert-ip.txt, and the
#   runtime selmo-config.json / selmo-state.json / selmo-image-config.json --
#   all of these regenerate on first run (server/tray write them, cert is
#   minted for the machine's own IP). Shipping selmo.key would leak Fabio's
#   private key. See the Pre-launch checklist in selmo-dev.md.
$appFiles = @(
  "chat.html","chunk_pipeline.py",
  "selmo_tray.py","selmo_server.py","selmo_https_proxy.py","selmo_web.py","selmo_gpu_monitor.py",
  "selmo_whisper.py","selmo_tts.py","selmo_image.py",
  "selmo-i18n.js","selmo-boot.js","selmo-bridges.js","selmo-chat.js","selmo-core.js","selmo-docs.js",
  "selmo-media.js","selmo-model.js","selmo-send.js","selmo-sessions.js","selmo-settings.js",
  "selmo-image-models.ini","selmo-models.ini",
  "selmo.ico",
  "LICENSE","NOTICE","TERMS.md","README.md","QUICKSTART.md","selmo-manifesto.md"
)
foreach ($f in $appFiles) {
  $src = Join-Path $Root $f
  if (Test-Path $src) { Copy-Item $src (Join-Path $Dist $f) -Force }
  else { Write-Warning "missing app file: $f" }
}

# self-hosted font (Share Tech Mono) -- chat.html @font-face points at fonts\;
# no Google Fonts request, so nothing about the user reaches a CDN on load.
$fontsSrc = Join-Path $Root "fonts"
if (Test-Path $fontsSrc) {
  Copy-Item $fontsSrc (Join-Path $Dist "fonts") -Recurse -Force
} else { Write-Warning "missing fonts\ folder" }

# selmo-models.ini ships as-is from the repo (the full model-matching table).
# Selmo is model-agnostic: no model is bundled or seeded. The user drops a
# .gguf into models\ and picks it in the browser. See MODELS.md.

# installer support files (first_run.py, downloads.json, launchers)
New-Item -ItemType Directory -Path (Join-Path $Dist "installer") | Out-Null
# launcher + support scripts under installer\ (the shortcut runs
# python\pythonw.exe with installer\boot.py -- no loose .vbs/.cmd to be
# quarantined by antivirus)
foreach ($f in @("boot.py","first_run.py","downloads.json","MODELS.md",
                 "_dl.py","addon_voice.py","addon_image.py","addon_uninstall.py")) {
  Copy-Item (Join-Path $PSScriptRoot $f) (Join-Path $Dist "installer\$f") -Force
}

# models\ exists but stays empty (filled on first run)
New-Item -ItemType Directory -Path (Join-Path $Dist "models") | Out-Null

# portable clickable launcher in the bundle root: double-click to run Selmo
# (hidden) without installing.
$cmd = "@echo off`r`nstart `"`" `"%~dp0python\pythonw.exe`" `"%~dp0installer\boot.py`"`r`n"
Set-Content -Path (Join-Path $Dist "Selmo.cmd") -Value $cmd -NoNewline -Encoding ASCII

# ---- optional add-on installers (independent, opt-in) ----------------------
#   The base is untouched. Each of these adds ONE capability on top of it and
#   is safe to run (or skip) on its own. They run the bundled python with a
#   VISIBLE console (progress bars), so python.exe -- not pythonw.exe.
#     Install-Voice.cmd            -> Whisper STT + Kokoro TTS
#     Install-Image.cmd            -> stable-diffusion.cpp image gen (needs a GPU)
#     Install-Hardware-Monitor.cmd -> LibreHardwareMonitor (real CPU watts)
Copy-Item (Join-Path $Root "setup-lhm.ps1") (Join-Path $Dist "setup-lhm.ps1") -Force
New-Item -ItemType Directory -Path (Join-Path $Dist "tts")   -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Dist "image") -Force | Out-Null

$voice = "@echo off`r`ntitle Selmo - Install Voice`r`n`"%~dp0python\python.exe`" `"%~dp0installer\addon_voice.py`"`r`n"
Set-Content -Path (Join-Path $Dist "Install-Voice.cmd") -Value $voice -NoNewline -Encoding ASCII

$image = "@echo off`r`ntitle Selmo - Install Image Generation`r`n`"%~dp0python\python.exe`" `"%~dp0installer\addon_image.py`"`r`n"
Set-Content -Path (Join-Path $Dist "Install-Image.cmd") -Value $image -NoNewline -Encoding ASCII

$hw = "@echo off`r`ntitle Selmo - Install Hardware Monitor`r`npowershell -ExecutionPolicy Bypass -File `"%~dp0setup-lhm.ps1`"`r`npause`r`n"
Set-Content -Path (Join-Path $Dist "Install-Hardware-Monitor.cmd") -Value $hw -NoNewline -Encoding ASCII

# uninstallers -- each add-on is reversible. Voice/Image remove only their own
# files + exclusive pip packages; the hardware monitor also drops its task.
$uv = "@echo off`r`ntitle Selmo - Uninstall Voice`r`n`"%~dp0python\python.exe`" `"%~dp0installer\addon_uninstall.py`" voice`r`n"
Set-Content -Path (Join-Path $Dist "Uninstall-Voice.cmd") -Value $uv -NoNewline -Encoding ASCII

$ui = "@echo off`r`ntitle Selmo - Uninstall Image Generation`r`n`"%~dp0python\python.exe`" `"%~dp0installer\addon_uninstall.py`" image`r`n"
Set-Content -Path (Join-Path $Dist "Uninstall-Image.cmd") -Value $ui -NoNewline -Encoding ASCII

$uh = "@echo off`r`ntitle Selmo - Uninstall Hardware Monitor`r`npowershell -ExecutionPolicy Bypass -File `"%~dp0setup-lhm.ps1`" -Uninstall`r`npause`r`n"
Set-Content -Path (Join-Path $Dist "Uninstall-Hardware-Monitor.cmd") -Value $uh -NoNewline -Encoding ASCII

# ---- 4. llama.cpp backend -- NOT bundled, downloaded on first run ----------
#   first_run.py fetches the matching backend (CUDA for NVIDIA, Vulkan
#   otherwise) from the official llama.cpp releases, so the installer stays
#   tiny and every machine gets the right, version-matched binaries.
New-Item -ItemType Directory -Path (Join-Path $Dist "bin") | Out-Null

Write-Host ""
Write-Host "Bundle staged at: $Dist" -ForegroundColor Green
$size = (Get-ChildItem $Dist -Recurse | Measure-Object Length -Sum).Sum/1MB
Write-Host ("Approx size (no models): {0:N0} MB" -f $size)
Write-Host "Next: zip dist\ for the download link, e.g.:"
Write-Host "    Compress-Archive -Path dist\* -DestinationPath Selmo-portable.zip -Force"
