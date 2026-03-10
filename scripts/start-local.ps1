$ErrorActionPreference = "Stop"

function Write-Status([string]$message) {
  Write-Host "[FGBM] $message"
}

function Fail-And-Exit([string]$message) {
  Write-Host "[FGBM] ERROR: $message" -ForegroundColor Red
  Read-Host "Press Enter to exit"
  exit 1
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $root "..\.env"
$exampleFile = Join-Path $root "..\.env.example"
$venvDir = Join-Path $root "..\.venv"
 $frontendDir = Join-Path $root "..\frontend\dashboard"

if (-not (Test-Path $envFile)) {
  if (Test-Path $exampleFile) {
    Copy-Item $exampleFile $envFile
  } else {
    "" | Set-Content $envFile
  }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Fail-And-Exit "Python is not installed. Install Python 3.11+ and try again."
}

if (-not (Test-Path $venvDir)) {
  Write-Status "Creating virtual environment..."
  python -m venv $venvDir
}

$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$pipExe = Join-Path $venvDir "Scripts\pip.exe"

Write-Status "Installing dependencies..."
& $pipExe install -r (Join-Path $root "..\requirements.txt") | Out-Null

Write-Status "Starting API..."
Start-Process $pythonExe -ArgumentList "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"

Start-Sleep -Seconds 2
Start-Process (Join-Path $frontendDir "index.html")
