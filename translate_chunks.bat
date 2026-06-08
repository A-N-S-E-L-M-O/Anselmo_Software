@echo off
title translate_chunks -- Selmo
cd /d "%~dp0"

:: Finestra CMD dedicata: stdin interattivo, la domanda "thinking model?"
:: compare correttamente anche al doppio click (BUG-05).
:: Eventuali argomenti passati da riga di comando vengono inoltrati con %*
python "%~dp0translate_chunks.py" %*

echo.
echo  Premi un tasto per chiudere...
pause >nul
