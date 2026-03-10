@echo off
setlocal

set ROOT=%~dp0
set ENV_FILE=%ROOT%.env
set EXAMPLE_FILE=%ROOT%.env.example

if not exist "%ENV_FILE%" (
  if exist "%EXAMPLE_FILE%" (
    copy "%EXAMPLE_FILE%" "%ENV_FILE%" >nul
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start-docker.ps1"
