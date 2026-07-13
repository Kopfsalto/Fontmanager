@echo off
rem ============================================================
rem  build.bat - startet build.ps1 per Doppelklick
rem  - umgeht die PowerShell-ExecutionPolicy (nur fuer diesen Aufruf)
rem  - haelt das Fenster am Ende offen, damit Meldungen lesbar sind
rem ============================================================
setlocal
cd /d "%~dp0"

echo === FontManager Build wird gestartet ===
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"

echo.
if errorlevel 1 (
    echo *** BUILD FEHLGESCHLAGEN - Meldungen oben pruefen ***
) else (
    echo === Fertig: dist\FontManager.exe ===
)
echo.
pause
