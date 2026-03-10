$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Join-Path $root ".."
$distDir = Join-Path $projectRoot "dist"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is required to build the EXE." -ForegroundColor Red
  exit 1
}

Push-Location $projectRoot
try {
  python -m pip install --user -r requirements.txt
  python -m pip install --user pyinstaller

  python -m PyInstaller --noconfirm --onefile --name fgbm desktop_app.py

  if (-not (Test-Path $distDir)) { New-Item -ItemType Directory -Force -Path $distDir | Out-Null }
  Copy-Item .env.example (Join-Path $distDir ".env.example") -Force
  Copy-Item README.md (Join-Path $distDir "README.md") -Force
} finally {
  Pop-Location
}

Write-Host "Build complete. EXE located at dist\\fgbm.exe" -ForegroundColor Green

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
  $candidate = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
  if (Test-Path $candidate) {
    $iscc = $candidate
  }
}

if ($iscc) {
  Push-Location $root
  try {
    & $iscc setup.iss
    Write-Host "Installer created: installer\\FGBM-Setup.exe" -ForegroundColor Green
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Inno Setup not found. To create a wizard installer, install Inno Setup and rerun build.ps1." -ForegroundColor Yellow
}
