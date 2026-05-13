$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function ConvertTo-WslSingleQuoted {
    param([string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

try {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

    Write-Status "Syncing Voxtral Journal Windows repo to WSL-native runtime copy."
    Write-Status "Windows source path: $repoRoot"

    $repoRootForWslPath = $repoRoot -replace "\\", "/"
    $wslSource = (& wsl.exe wslpath -a "$repoRootForWslPath" 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host $wslSource
        throw "wslpath failed for $repoRoot"
    }
    $wslSource = ($wslSource | Select-Object -First 1).Trim()
    $wslRuntime = (& wsl.exe bash -lc "printf '%s' `"`$HOME/apps/voxtral-journal-windows`"" 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host $wslRuntime
        throw "Failed to resolve WSL runtime path."
    }
    $wslRuntime = ($wslRuntime | Select-Object -First 1).Trim()

    Write-Status "WSL source path: $wslSource"
    Write-Status "WSL runtime path: $wslRuntime"

    & wsl.exe bash -lc "command -v rsync >/dev/null 2>&1" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "rsync is not installed in WSL. Install it with:"
        Write-Host "  sudo apt update && sudo apt install -y rsync"
        exit 1
    }

    $quotedSource = ConvertTo-WslSingleQuoted (($wslSource.TrimEnd("/")) + "/")
    $quotedRuntime = ConvertTo-WslSingleQuoted $wslRuntime
    $syncCommand = @"
set -euo pipefail
mkdir -p $quotedRuntime
rsync -a --human-readable --info=stats2,progress2 \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.pytest_cache' \
  --exclude='__pycache__' \
  --exclude='data/logs/*' \
  --exclude='data/smoke/*' \
  --exclude='*.log' \
  $quotedSource $quotedRuntime/
"@

    Write-Status "Running rsync into WSL-native runtime copy."
    $syncOutput = & wsl.exe bash -lc $syncCommand 2>&1
    $syncOutput | ForEach-Object {
        if ($_) {
            Write-Host $_
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "rsync failed."
    }

    Write-Status "Sync complete."
    Write-Host "Windows source path: $repoRoot"
    Write-Host "WSL runtime path: $wslRuntime"
    exit 0
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)"
    exit 1
}
