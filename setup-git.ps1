# Setup-git.ps1 -- (re)inizializza il repo git locale per Selmo
# Esegui con:  powershell -ExecutionPolicy Bypass -File setup-git.ps1
#
# Sicuro da rieseguire: se trova un .git rotto o parziale lo rimuove e
# ricostruisce da zero, poi fa il primo commit e tagga v0.31.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "  Selmo -- inizializzazione repository git locale" -ForegroundColor Cyan
Write-Host "  $root"
Write-Host ""

# 1) git installato?
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  ERRORE: git non trovato." -ForegroundColor Red
    Write-Host "  Scarica da https://git-scm.com e riavvia lo script."
    Read-Host "  Premi Invio per uscire"
    exit 1
}

# 2) Ripulisci un eventuale .git rotto/parziale (es. manca objects/, config.lock)
if (Test-Path ".git") {
    $broken = -not (Test-Path ".git\objects")
    if ($broken) {
        Write-Host "  Trovato .git parziale/rotto -- lo rimuovo e ricostruisco" -ForegroundColor Yellow
        # togli eventuali attributi read-only prima di cancellare
        attrib -R -H -S ".git\*.*" /S /D 2>$null
        Remove-Item -Recurse -Force ".git"
    } else {
        Write-Host "  Repo gia' inizializzato -- non tocco .git esistente." -ForegroundColor Green
        Write-Host "  (Se vuoi ripartire da zero, cancella la cartella .git a mano e rilancia.)"
        Read-Host "  Premi Invio per uscire"
        exit 0
    }
}

# 3) .gitignore -- fuori i file enormi e i backup
$gitignore = @"
# Modelli e binari enormi -- non versionare
models/
bin/
*.dll
*.exe

# Backup e file troncati
*.bak
*.back
*.truncated.bak
chat - Copy GOOD.html

# Log e temporanei
*.log
__pycache__/
*.pyc

# Lock
*.lock

# File di test pesanti
Test files/
"@
$gitignore | Set-Content -Encoding UTF8 ".gitignore"
Write-Host "  .gitignore scritto" -ForegroundColor Green

# 4) Init + config
git init -b main | Out-Null
git config user.email "you@example.com"
git config user.name  "Fabio"
git config core.autocrlf false

# 5) Stage di tutto cio' che non e' ignorato
git add -A

# 6) Primo commit
git commit -m "v0.31 -- baseline tracciata + fix sessione 8

- chat.html: risolta la causa radice TDZ (currentSessionId dichiarato
  in cima, prima della init renderSessionList()). Sistemava insieme la
  sidebar history vuota e l'errore /web 'chatHistory before initialization'.
- chat.html: layout a griglia corretto -- nav/main/aside ancorati a
  grid-row:2 con colonna esplicita, cosi' le tre colonne condividono la
  riga 2 e scorrono in modo indipendente (prima main finiva su una riga
  implicita per via dell'ordine nel DOM).
- chat.html: etichetta versione header -> v0.31
- selmo_web.py: bridge ricerca web
- test_chunking.py, selmo-session6-plan.md, selmo-bug-report-s7.md aggiunti" | Out-Null

# 7) Tag della release
git tag -a v0.31 -m "Selmo v0.31"

Write-Host ""
Write-Host "  Repository inizializzato. Primo commit fatto e tag v0.31 creato." -ForegroundColor Green
Write-Host ""
git log --oneline -1
Write-Host ""
Write-Host "  Comandi utili:" -ForegroundColor Yellow
Write-Host "    git log --oneline           -- storia commit"
Write-Host "    git status                  -- cosa e' cambiato"
Write-Host "    git diff                    -- modifiche non committate"
Write-Host "    .\git-save.ps1 'messaggio'  -- salva un nuovo commit al volo"
Write-Host ""
Read-Host "  Premi Invio per uscire"
