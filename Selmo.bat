@echo off
setlocal enabledelayedexpansion
title Selmo -- IA Locale

cd /d "%~dp0"

echo.
echo  +------------------------------------------+
echo  ^|  Selmo  --  IA locale, GDPR by design   ^|
echo  ^|  I tuoi dati restano sul tuo computer.  ^|
echo  +------------------------------------------+
echo.

:: ── Scansione modelli (escludi mmproj) ──────────────────────────
set count=0
for %%F in ("models\*.gguf") do (
    echo %%~nxF | findstr /i "mmproj" >nul
    if errorlevel 1 (
        set /a count+=1
        set "model_!count!=%%~nxF"
        set "modelpath_!count!=%%~fF"
    )
)

if %count%==0 (
    echo  ERRORE: nessun file .gguf trovato in models\
    echo  Scarica un modello e copialo nella cartella models\
    pause
    exit /b 1
)

:: ── Menu selezione ───────────────────────────────────────────────
if %count%==1 (
    set "selected=1"
    echo  Un solo modello trovato: !model_1!
    echo.
) else (
    echo  Modelli disponibili:
    echo.
    for /l %%i in (1,1,%count%) do (
        echo    [%%i] !model_%%i!
    )
    echo.
    set /p "selected=  Scegli il modello [1-%count%]: "
)

:: Validazione scelta
set "MODELFILE=!modelpath_%selected%!"
set "MODELNAME=!model_%selected%!"
if "!MODELFILE!"=="" (
    echo  Scelta non valida.
    pause
    exit /b 1
)

:: ── Auto-detection mmproj (visione multimodale) ─────────────────
:: Abbina automaticamente il mmproj al modello scelto, in base al nome.
:: Niente domanda: il primo mmproj il cui nome combacia col modello vince.
:: Convenzione: il mmproj si chiama "mmproj-<nome-base-modello>-<formato>.gguf",
:: quindi togliendo "mmproj-" i primi caratteri coincidono col nome del modello.
set "MMPROJ_FILE="
set "MMPROJ_NAME="
for %%F in ("models\*mmproj*.gguf") do (
    if not defined MMPROJ_FILE (
        set "mp_name=%%~nxF"
        set "mp_path=%%~fF"
        set "mp_key=!mp_name:mmproj-=!"
        set "mp_key=!mp_key:~0,10!"
        echo !MODELNAME! | findstr /i /c:"!mp_key!" >nul
        if not errorlevel 1 (
            set "MMPROJ_FILE=!mp_path!"
            set "MMPROJ_NAME=!mp_name!"
        )
    )
)
if defined MMPROJ_FILE (
    echo  Visione  : mmproj abbinato in automatico -- !MMPROJ_NAME!
) else (
    echo  Visione  : nessun mmproj compatibile con il modello -- solo testo
)

:: ── Calcolo -ngl adattivo ────────────────────────────────────────
:: set /a e' limitato a 32-bit: per file > 2GB serve PowerShell
for /f "usebackq" %%S in (`powershell -NoProfile -Command "[int]((Get-Item '!MODELFILE!').Length / 1MB)"`) do set "fsize_mb=%%S"

:: Logica adattiva:
::   < 6000 MB  -> modelli ~9B   : tutto su GPU, ctx 4096 (limite architetturale)
::   6000-9000  -> modelli ~13B  : tutto su GPU, ctx 16384 (KV cache ok)
::   9000-13000 -> modelli 12-24B: layer parziali, ctx 8192 (KV cache sforerebbe a 16384)
::   > 13000    -> modelli >30B  : layer ridotti, ctx 8192
set NGL=45
set CTX=8192
if !fsize_mb! LSS 6000 (
    set NGL=99
    set CTX=4096
)
if !fsize_mb! LSS 9000 if !fsize_mb! GEQ 6000 (
    set NGL=99
    set CTX=16384
)
if !fsize_mb! GTR 13000 (
    set NGL=30
    set CTX=8192
)

:: Nota (s9): nessun prompt "thinking" qui. Con il chunking la finestra resta
:: piccola e veloce (GPU piena, ctx 8192). Lo spazio per il ragionamento dei
:: modelli reasoning si riserva nel client con chunk_pipeline.py --thinking-buffer,
:: non allargando la ctx del server (contesti grandi = piu' lenti e peggiori).

echo.
echo  Modello  : !MODELNAME!
echo  Dim.     : %fsize_mb% MB
echo  -ngl     : %NGL%   ctx: %CTX%
if defined MMPROJ_FILE echo  Visione  : attiva
echo  Rete     : http://0.0.0.0:8080  (locale + WiFi)
echo.

:: ── GPU monitor + web bridge + whisper (opzionali) ─────────────
python --version >nul 2>&1
if errorlevel 1 goto skip_python
echo  Avvio servizi Python...
start "SelmoGPU"     /min python "%~dp0selmo_gpu_monitor.py" 2>nul
start "SelmoWeb"     /min python "%~dp0selmo_web.py" 2>nul
start "SelmoWhisper" /min python "%~dp0selmo_whisper.py" 2>nul
start "SelmoTTS"     /min python "%~dp0selmo_tts.py" --voice im_nicola 2>nul
timeout /t 2 /nobreak >nul
:skip_python

:: ── Apertura interfaccia ─────────────────────────────────────────
echo  Apertura interfaccia chat...
start "" "http://127.0.0.1:8080/chat.html"

echo  Premi CTRL+C per fermare il server.
echo.

:: ── Avvio server ─────────────────────────────────────────────────
if defined MMPROJ_FILE (
    "%~dp0bin\llama-server.exe" ^
        --model "!MODELFILE!" ^
        --mmproj "!MMPROJ_FILE!" ^
        --image-min-tokens 1120 --image-max-tokens 1120 ^
        --batch-size 2048 --ubatch-size 2048 ^
        --host 0.0.0.0 ^
        --port 8080 ^
        --ctx-size %CTX% ^
        -ngl %NGL% ^
        --parallel 1 ^
        --no-warmup ^
        --timeout 0 ^
        --metrics ^
        --path "." ^
        --temp 0.75 ^
        --top-p 0.9 ^
        --reasoning-format deepseek
) else (
    "%~dp0bin\llama-server.exe" ^
        --model "!MODELFILE!" ^
        --host 0.0.0.0 ^
        --port 8080 ^
        --ctx-size %CTX% ^
        -ngl %NGL% ^
        --parallel 1 ^
        --no-warmup ^
        --timeout 0 ^
        --metrics ^
        --path "." ^
        --temp 0.75 ^
        --top-p 0.9 ^
        --reasoning-format deepseek
)

:: -- Pausa diagnostica: tiene la finestra aperta se il