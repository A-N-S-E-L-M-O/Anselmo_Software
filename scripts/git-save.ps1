# git-save.ps1 -- salva un commit veloce con tutte le modifiche correnti
# Uso:  powershell -ExecutionPolicy Bypass -File git-save.ps1 "messaggio del commit"
#   o:  .\git-save.ps1 "messaggio del commit"

param(
    [Parameter(Mandatory = $false)]
    [string]$msg
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".git")) {
    Write-Host "  Nessun repo git qui. Lancia prima setup-git.ps1." -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($msg)) {
    $msg = Read-Host "  Messaggio del commit"
}
if ([string]::IsNullOrWhiteSpace($msg)) {
    Write-Host "  Messaggio vuoto -- annullo." -ForegroundColor Yellow
    exit 1
}

git add -A
$pending = git status --porcelain
if ([string]::IsNullOrWhiteSpace($pending)) {
    Write-Host "  Niente da committare -- working tree pulito." -ForegroundColor Yellow
    exit 0
}

git commit -m "$msg" | Out-Null
Write-Host ""
git log --oneline -1
Write-Host "  Commit salvato." -ForegroundColor Green
