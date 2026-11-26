# Build dist\WFMarketTracker.exe
# Usage: .\build.ps1 [-Venv <path to venv>]
# The venv must live on a short path (Windows MAX_PATH); default: .venv next to this script.
param([string]$Venv = "$PSScriptRoot\.venv")

# Native tools write progress to stderr; rely on exit codes instead of "Stop".
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv $Venv
    & $py -m pip install -q -r requirements-dev.txt
}
& $py -m pytest -q -p no:warnings
if ($LASTEXITCODE -ne 0) { throw "tests failed" }
& $py -m PyInstaller --noconfirm --clean wfmt.spec
if ($LASTEXITCODE -ne 0) { throw "build failed" }
Write-Host "Built: $PSScriptRoot\dist\WFMarketTracker.exe"
