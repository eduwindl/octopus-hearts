$ErrorActionPreference = "Stop"

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

if (-not (Get-EnvValue $envFile "TOKEN_ENCRYPTION_KEY")) {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $key = [Convert]::ToBase64String($bytes).Trim()
  Set-EnvValue $envFile "TOKEN_ENCRYPTION_KEY" $key
}

if (-not (Get-EnvValue $envFile "API_USERNAME")) {
  $user = Read-Host "Create dashboard username"
  Set-EnvValue $envFile "API_USERNAME" $user
}

if (-not (Get-EnvValue $envFile "API_PASSWORD")) {
  $pass = Read-Host "Create dashboard password"
  Set-EnvValue $envFile "API_PASSWORD" $pass
}

Copy-Item $envFile $dockerEnv -Force

Push-Location $dockerDir
try {
  docker compose up --build -d
} finally {
  Pop-Location
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:8080"
