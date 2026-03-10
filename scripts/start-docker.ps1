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
$dockerDir = Join-Path $root "..\docker"
$dockerEnv = Join-Path $dockerDir ".env"

if (-not (Test-Path $envFile)) {
  if (Test-Path $exampleFile) {
    Copy-Item $exampleFile $envFile
  } else {
    "" | Set-Content $envFile
  }
}

function Set-EnvValue([string]$path, [string]$key, [string]$value) {
  $lines = Get-Content $path
  $pattern = "^$([regex]::Escape($key))="
  if ($lines | Where-Object { $_ -match $pattern }) {
    $lines = $lines | ForEach-Object {
      if ($_ -match $pattern) { "$key=$value" } else { $_ }
    }
  } else {
    $lines += "$key=$value"
  }
  $lines | Set-Content $path
}

function Get-EnvValue([string]$path, [string]$key) {
  $line = Get-Content $path | Where-Object { $_ -match "^$([regex]::Escape($key))=" } | Select-Object -First 1
  if ($null -eq $line) { return $null }
  return $line.Split("=",2)[1]
}

if (-not (Get-EnvValue $envFile "DATABASE_URL")) {
  Set-EnvValue $envFile "DATABASE_URL" "sqlite:///./data/fgbm.db"
}

if (-not (Get-EnvValue $envFile "BACKUPS_ROOT")) {
  Set-EnvValue $envFile "BACKUPS_ROOT" "./backups"
}

if (-not (Get-EnvValue $envFile "RETENTION_COUNT")) {
  Set-EnvValue $envFile "RETENTION_COUNT" "3"
}

if (-not (Get-EnvValue $envFile "SCHEDULER_TIMEZONE")) {
  Set-EnvValue $envFile "SCHEDULER_TIMEZONE" "America/Santo_Domingo"
}

if (-not (Get-EnvValue $envFile "AUTH_ENABLED")) {
  Set-EnvValue $envFile "AUTH_ENABLED" "true"
}

if (-not (Get-EnvValue $envFile "FORTIGATE_VERIFY_SSL")) {
  Set-EnvValue $envFile "FORTIGATE_VERIFY_SSL" "false"
}

if (-not (Get-EnvValue $envFile "FORTIGATE_RESTORE_ENDPOINT")) {
  Set-EnvValue $envFile "FORTIGATE_RESTORE_ENDPOINT" "/api/v2/monitor/system/config/restore"
}

if (-not (Get-EnvValue $envFile "TOKEN_ENCRYPTION_KEY")) {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $key = [Convert]::ToBase64String($bytes).Trim()
  Set-EnvValue $envFile "TOKEN_ENCRYPTION_KEY" $key
}

if (-not (Get-EnvValue $envFile "ADMIN_USERNAME")) {
  $user = Read-Host "Create admin username"
  Set-EnvValue $envFile "ADMIN_USERNAME" $user
}

if (-not (Get-EnvValue $envFile "ADMIN_PASSWORD")) {
  $pass = Read-Host "Create admin password"
  Set-EnvValue $envFile "ADMIN_PASSWORD" $pass
}

Copy-Item $envFile $dockerEnv -Force

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail-And-Exit "Docker is not installed. Install Docker Desktop and try again."
}

try {
  docker version | Out-Null
} catch {
  Fail-And-Exit "Docker Desktop is not running. Start Docker Desktop and try again."
}

try {
  docker compose version | Out-Null
} catch {
  Fail-And-Exit "Docker Compose is unavailable. Update Docker Desktop and try again."
}

Push-Location $dockerDir
try {
  Write-Status "Starting containers..."
  docker compose up --build -d
} finally {
  Pop-Location
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:8080"
