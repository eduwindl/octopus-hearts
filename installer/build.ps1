$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Join-Path $root ".."
$distDir = Join-Path $projectRoot "dist"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is required to build the portable EXE." -ForegroundColor Red
  exit 1
}

Push-Location $projectRoot
try {
  python -m pip install --user -r requirements.txt
  python -m pip install --user pyinstaller

  $addData = "frontend\dashboard;frontend\dashboard"
  python -m PyInstaller --noconfirm --onefile --name fgbm --add-data $addData launcher.py

  if (-not (Test-Path $distDir)) { New-Item -ItemType Directory -Force -Path $distDir | Out-Null }
  Copy-Item .env.example (Join-Path $distDir ".env.example") -Force
  Copy-Item README.md (Join-Path $distDir "README.md") -Force
} finally {
  Pop-Location
}

Write-Host "Build complete. EXE located at dist\\fgbm.exe" -ForegroundColor Green
