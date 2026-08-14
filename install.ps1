# RunRepo Automated Installer for Windows (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    RunRepo Automated Installation     " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Check and install uv if missing
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[*] 'uv' is not installed. Installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

# 2. Locate RunRepo directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "[*] Installing RunRepo globally via uv tool..." -ForegroundColor Green
uv tool install -e . --force

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " [✓] RunRepo successfully installed!   " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Try running:"
Write-Host "  runrepo doctor"
Write-Host "  runrepo setup https://github.com/owner/project"
Write-Host ""
