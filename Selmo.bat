@echo off
setlocal enabledelayedexpansion
title Selmo -- Local AI

cd /d "%~dp0"

:: ---- Load per-model defaults from selmo-models.ini ----
set "INI=%~dp0selmo-models.ini"
set "secN=0"
set "def_ngl=99" & set "def_ctx=8192" & set "def_max=unknown" & set "def_note=Unknown/untested: try your settings"
set "curIdx="
if exist "%INI%" (
    for /f "usebackq eol=; tokens=* delims=" %%L in ("%INI%") do (
        set "ln=%%L"
        if defined ln (
            if "!ln:~0,1!"=="[" (
                set "sname=!ln:~1!"
                set "sname=!sname:]=!"
                if /i "!sname!"=="default" ( set "curIdx=0" ) else ( set /a secN+=1 & set "curIdx=!secN!" & set "sname_!secN!=!sname!" )
            ) else (
                for /f "tokens=1* delims==" %%A in ("!ln!") do (
                    if "!curIdx!"=="0" (
                        if /i "%%A"=="ngl"  set "def_ngl=%%B"
                        if /i "%%A"=="ctx"  set "def_ctx=%%B"
                        if /i "%%A"=="max"  set "def_max=%%B"
                        if /i "%%A"=="note" set "def_note=%%B"
                    ) else if defined curIdx (
                        if /i "%%A"=="ngl"  set "sngl_!curIdx!=%%B"
                        if /i "%%A"=="ctx"  set "sctx_!curIdx!=%%B"
                        if /i "%%A"=="max"  set "smax_!curIdx!=%%B"
                        if /i "%%A"=="note" set "snote_!curIdx!=%%B"
                    )
                )
            )
        )
    )
)

:: ---- Scan models (exclude mmproj), resolve each one from the ini ----
set count=0
for %%F in ("models\*.gguf") do (
    echo %%~nxF | findstr /i "mmproj" >nul
    if errorlevel 1 (
        set /a count+=1
        set "model_!count!=%%~nxF"
        set "modelpath_!count!=%%~fF"
        call :lookup "%%~nxF" !count!
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
        set "row=!model_%%i!                                           "
        echo    [%%i] !row:~0,42!  --  !note_%%i!
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

:: Per-model defaults (resolved from selmo-models.ini; lower -ngl if VRAM is short)
set "NGL=!ngl_%selected%!"
set "CTX=!ctx_%selected%!"
if "!NGL!"=="" set "NGL=%def_ngl%"
if "!CTX!"=="" set "CTX=%def_ctx%"

echo.

:: Defaults are pre-filled; press ENTER to keep or type a new value
set /p "NGL=  GPU layers (-ngl) [!NGL!]: "
set /p "CTX=  Context window (--ctx) [!CTX!]  (native max !max_%selected%!): "
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
goto :eof

:: ---- Resolve ngl / ctx / note for a model from the parsed ini ----
::   %~1 = model file name   %~2 = menu index   (first matching section wins)
:lookup
set "li=%~2"
set "ngl_%li%=!def_ngl!"
set "ctx_%li%=!def_ctx!"
set "max_%li%=!def_max!"
set "note_%li%=!def_note!"
set "hit=0"
for /l %%s in (1,1,%secN%) do (
    if "!hit!"=="0" (
        echo %~1| findstr /i /c:"!sname_%%s!" >nul && ( set "ngl_%li%=!sngl_%%s!" & set "ctx_%li%=!sctx_%%s!" & set "max_%li%=!smax_%%s!" & set "note_%li%=!snote_%%s!" & set "hit=1" )
    )
)
goto :eof
