# Gera dist\Xiaomi1C\Xiaomi1C.exe (pasta portátil) com PyInstaller.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Push-Location frontend; npm run build; Pop-Location
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name Xiaomi1C `
  --add-data "frontend\dist;frontend" `
  --collect-submodules xiaomi1c --collect-submodules uvicorn `
  --hidden-import keyring.backends.Windows `
  packaging\launcher.py
Write-Host "Executável em dist\Xiaomi1C\Xiaomi1C.exe"
