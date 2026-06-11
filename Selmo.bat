@echo off
setlocal enabledelayedexpansion
title Selmo -- IA Locale

cd /d "%~dp0"

:: Scansione modelli (escludi mmproj)
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

:: Menu selezione
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

set "MODELFILE=!modelpath_%selected%!"
set "MODELNAME=!model_%selected%!"
if "!MODELFILE!"=="" (
    echo  Scelta non valida.
    pause
    exit /b 1
)

:: Auto-detection mmproj (visione multimodale)
set "MMPROJ_FILE="
for %%F in ("models\*mmproj*.gguf") do (
    if not defined MMPROJ_FILE (
        set "mp_name=%%~nxF"
        set "mp_path=%%~fF"
        set "mp_key=!mp_name:mmproj-=!"
        set "mp_key=!mp_key:~0,10!"
        echo !MODELNAME! | findstr /i /c:"!mp_key!" >nul
        if not errorlevel 1 (
            set "MMPROJ_FILE=!mp_path!"
        )
    )
)

:: No forcing: offload all layers to GPU; ctx 0 = let the model decide (training ctx)
set NGL=99
set CTX=0

:: Avvio backend -- unica finestra, tutto muore alla chiusura
if defined MMPROJ_FILE (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX% --mmproj "!MMPROJ_FILE!"
) else (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX%
)

:: Se python esce con errore, tieni la finestra aperta
if errorlevel 1 (
    echo.
    echo  ERRORE - premi un tasto per chiudere.
    pause >nul
)
