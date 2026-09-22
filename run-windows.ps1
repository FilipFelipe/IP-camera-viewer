$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Error ".venv not found. Create it first with: py -m venv .venv"
    exit 1
}

. ".\.venv\Scripts\Activate.ps1"
python main.py
