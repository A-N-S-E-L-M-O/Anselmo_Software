@echo off
setlocal enabledelayedexpansion
title Selmo -- Local AI

cd /d "%~dp0"

:: ---- Load per-model defaults from selmo-models.ini ----
set "INI=%~dp0selmo-models.ini"
set "secN=0"
set "def_ngl=99" & set "def_ctx=8192" & set "def_max=unknown" & set "def_cpumoe=" & set "def_note=Unknown/untested: try your settings"
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
                        if /i "%%A"=="note"   set "def_note=%%B"
                        if /i "%%A"=="cpumoe" set "def_cpumoe=%%B"
                    ) else if defined curIdx (
                        if /i "%%A"=="ngl"  set "sngl_!curIdx!=%%B"
                        if /i "%%A"=="ctx"  set "sctx_!curIdx!=%%B"
                        if /i "%%A"=="max"  set "smax_!curIdx!=%%B"
                        if /i "%%A"=="note"   set "snote_!curIdx!=%%B"
                        if /i "%%A"=="cpumoe" set "scpumoe_!curIdx!=%%B"
                    )
                )
            )
        )
    )
)

:: ---- Scan models recursively (subfolders, LM Studio style), exclude mmproj ----
::   each model remembers its own folder, so its mmproj is just the
::   *mmproj*.gguf sitting next to it -- no name matching, nothing to rename.
set count=0
for /r "%~dp0models" %%F in (*.gguf) do (
    echo %%~nxF | findstr /i "mmproj" >nul
    if errorlevel 1 (
        set /a count+=1
        set "model_!count!=%%~nxF"
        set "modelpath_!count!=%%~fF"
        set "modeldir_!count!=%%~dpF"
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

:: mmproj auto-detection: the *mmproj*.gguf in the SAME folder as the model
set "MMPROJ_FILE="
for %%F in ("!modeldir_%selected%!*mmproj*.gguf") do (
    if not defined MMPROJ_FILE if exist "%%~fF" set "MMPROJ_FILE=%%~fF"
)

:: Per-model defaults (resolved from selmo-models.ini; lower -ngl if VRAM is short)
set "NGL=!ngl_%selected%!"
set "CTX=!ctx_%selected%!"
if "!NGL!"=="" set "NGL=%def_ngl%"
if "!CTX!"=="" set "CTX=%def_ctx%"
set "CMOE=!cpumoe_%selected%!"
if "!CMOE!"=="" set "CMOE=%def_cpumoe%"

echo.

:: Defaults are pre-filled; press ENTER to keep or type a new value
set /p "NGL=  GPU layers (-ngl) [!NGL!]: "
set /p "CTX=  Context window (--ctx) [!CTX!]  (native max !max_%selected%!): "
set /p "CMOE=  CPU MoE experts (--n-cpu-moe, blank=off) [!CMOE!]: "
echo.
set "EXTRA="
if not "!CMOE!"=="" if not "!CMOE!"=="0" set "EXTRA=--cpumoe !CMOE!"
echo  Starting: NGL=!NGL!  CTX=!CTX!  CPUMOE=[!CMOE!]
echo.

:: Start backend -- single window, everything dies on close
if defined MMPROJ_FILE (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX% --mmproj "!MMPROJ_FILE!" !EXTRA!
) else (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --ngl %NGL% --ctx %CTX% !EXTRA!
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
set "cpumoe_%li%=!def_cpumoe!"
set "hit=0"
for /l %%s in (1,1,%secN%) do (
    if "!hit!"=="0" (
        echo %~1| findstr /i /c:"!sname_%%s!" >nul && ( set "ngl_%li%=!sngl_%%s!" & set "ctx_%li%=!sctx_%%s!" & set "max_%li%=!smax_%%s!" & set "note_%li%=!snote_%%s!" & set "cpumoe_%li%=!scpumoe_%%s!" & set "hit=1" )
    )
)
goto :eof
