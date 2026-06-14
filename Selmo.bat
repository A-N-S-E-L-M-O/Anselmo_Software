@echo off
setlocal enabledelayedexpansion
title Selmo -- Local AI

cd /d "%~dp0"

:: ---- Load per-model server strings from selmo-models.ini ----
set "INI=%~dp0selmo-models.ini"
set "secN=0"
set "def_srv=--ctx-size 8192 -ngl 99 --parallel 1 --no-warmup --timeout 600 --metrics --reasoning-format deepseek"
set "def_max=unknown" & set "def_note=Unknown/untested: try your settings"
set "def_chunk_ratio=0.25" & set "def_chunk_maxtok=6000"
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
                        if /i "%%A"=="srv"          set "def_srv=%%B"
                        if /i "%%A"=="max"          set "def_max=%%B"
                        if /i "%%A"=="note"         set "def_note=%%B"
                        if /i "%%A"=="chunk_ratio"  set "def_chunk_ratio=%%B"
                        if /i "%%A"=="chunk_maxtok" set "def_chunk_maxtok=%%B"
                    ) else if defined curIdx (
                        if /i "%%A"=="srv"          set "ssrv_!curIdx!=%%B"
                        if /i "%%A"=="max"          set "smax_!curIdx!=%%B"
                        if /i "%%A"=="note"         set "snote_!curIdx!=%%B"
                        if /i "%%A"=="chunk_ratio"  set "schunk_ratio_!curIdx!=%%B"
                        if /i "%%A"=="chunk_maxtok" set "schunk_maxtok_!curIdx!=%%B"
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

:: ---- Resolve this model's values (from selmo-models.ini) ----
set "SRV=!srv_%selected%!"
set "CRATIO=!chunk_ratio_%selected%!"
set "CMAXTOK=!chunk_maxtok_%selected%!"
if "!SRV!"=="" set "SRV=%def_srv%"
if "!CRATIO!"=="" set "CRATIO=%def_chunk_ratio%"
if "!CMAXTOK!"=="" set "CMAXTOK=%def_chunk_maxtok%"

echo.
echo  Native max ctx for this model: !max_%selected%!   (keep --ctx-size at or below this)
echo.
echo  Server args (the exact llama-server command line):
echo    !SRV!
echo.
echo  Press ENTER to keep them, or type/paste a full replacement line.
echo  (--model / --host / --port / --path are added automatically.)
set /p "SRV=  srv> "
echo.
set /p "CRATIO=  Chunk input ratio (fraction of ctx per chunk) [!CRATIO!]: "
set /p "CMAXTOK=  Chunk max output tokens [!CMAXTOK!]: "
echo.
set "_vis=text only"
if defined MMPROJ_FILE set "_vis=on (mmproj auto-detected)"
echo  Launching:  vision=!_vis!  chunk_ratio=!CRATIO!  chunk_maxtok=!CMAXTOK!
echo    !SRV!
echo.

:: Start backend -- single window, everything dies on close
if defined MMPROJ_FILE (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --srv "!SRV!" --mmproj "!MMPROJ_FILE!" --chunk-ratio !CRATIO! --chunk-maxtok !CMAXTOK!
) else (
    python "%~dp0selmo_server.py" --model "!MODELFILE!" --srv "!SRV!" --chunk-ratio !CRATIO! --chunk-maxtok !CMAXTOK!
)

:: If python exits with an error, keep the window open
if errorlevel 1 (
    echo.
    echo  ERROR - press a key to close.
    pause >nul
)
goto :eof

:: ---- Resolve srv / max / note / chunk params for a model from the parsed ini ----
::   %~1 = model file name   %~2 = menu index   (first matching section wins)
:lookup
set "li=%~2"
set "srv_%li%=!def_srv!"
set "max_%li%=!def_max!"
set "note_%li%=!def_note!"
set "chunk_ratio_%li%=!def_chunk_ratio!"
set "chunk_maxtok_%li%=!def_chunk_maxtok!"
set "hit=0"
for /l %%s in (1,1,%secN%) do (
    if "!hit!"=="0" (
        echo %~1| findstr /i /c:"!sname_%%s!" >nul && ( set "srv_%li%=!ssrv_%%s!" & set "max_%li%=!smax_%%s!" & set "note_%li%=!snote_%%s!" & set "chunk_ratio_%li%=!schunk_ratio_%%s!" & set "chunk_maxtok_%li%=!schunk_maxtok_%%s!" & set "hit=1" )
    )
)
goto :eof
