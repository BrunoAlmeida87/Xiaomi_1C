# Prepara o ambiente de desenvolvimento no Windows (PowerShell).
# Requisitos: Python 3.11+ (python.org) e Node.js 20+ (nodejs.org).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[desktop,dev]"

Push-Location frontend
npm install
npm run build
Pop-Location

Write-Host "Pronto. Execute: .\packaging\run_windows.ps1"
