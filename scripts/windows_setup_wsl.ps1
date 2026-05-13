$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "WSL is not installed. Run this from an elevated PowerShell:"
    Write-Host "wsl --install -d Ubuntu"
    exit 1
}

$wslRepo = (wsl.exe wslpath -a "$repoRoot").Trim()
wsl.exe bash -lc "cd '$wslRepo' && bash scripts/wsl_install_deps_ubuntu.sh"
wsl.exe bash -lc "cd '$wslRepo' && make setup"

