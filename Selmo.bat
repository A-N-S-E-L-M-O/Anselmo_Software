@echo off
setlocal enabledelayedexpansion
title Selmo -- Local AI

cd /d "%~dp0"

:: Scan models (exclude mmproj)
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
    echo  ERROR: no .gguf file found in models\
    echo  Download a model and copy it into the models\ folder
    pause
    exit /b 1
)

:: Selection menu
if %count%==1 (
    set "selected=1"
    echo  Only one model found: !model_1!
    echo.
) else (
    echo  Available models:
    echo.
    for /l %%i in (1,1,%count%) do (
        echo    [%%i] !model_%%i!
    )
    echo.
    set /p "selected=  Choose the model [1-%count%]: "
)

set "MODELFILE=!modelpath_%selected%!"
set "MODELNAME=!model_%selected%!"
if "!MODELFILE!"=="" (
    echo  Invalid choice.
    pause
    exit /b 1
)

:: mmproj auto-detection (multimodal vision)
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

:: Runtime parameters -- defaults are pre-filled; press ENTER to keep or type a new value
set NGL=99
set /p "NGL=  GPU layers (-ngl) [!NGL!]: "
set CTX=8192
set /p "CTX=  Context window (--ctx) [!CTX!]: "
echo.
echo  Starting: NGL=!NGL!  CTX=!CTX!
echo.

:: Start backend -- single window, everything dies on close
if defined MMPROJ_FILE (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX% --mmproj "!MMPROJ_FILE!"
) else (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX%
)

:: If python exits with an error, keep the window open
if errorlevel 1 (
    echo.
    echo  ERROR - press a key to close.
    pause >nul
)
