# build.ps1 — erzeugt FontManager.exe (einmalig ausführen: .\build.ps1)
#
# Voraussetzung: Python 3.11+ (py-Launcher), Internetzugang für pip.
# Ergebnis:      .\dist\FontManager.exe  (Single-File, fordert UAC an)
#
# Falls die Skriptausführung blockiert ist, einmalig in PowerShell:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/3 Virtuelle Umgebung anlegen =="
if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

Write-Host "== 2/3 Abhaengigkeiten installieren =="
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "== 3/3 exe bauen (PyInstaller) =="
& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --uac-admin `
    --icon FontManager.ico `
    --add-data "FontManager.ico;." `
    --collect-all qfluentwidgets `
    --name FontManager `
    font_manager.py

Write-Host ""
Write-Host "Fertig: $PSScriptRoot\dist\FontManager.exe"
Write-Host "(--uac-admin: die exe fordert beim Start automatisch"
Write-Host " Administratorrechte per UAC-Dialog an.)"
