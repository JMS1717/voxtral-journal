$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Invoke-WslNoFail {
    param([string[]]$Arguments)
    & wsl.exe @Arguments 2>&1 | ForEach-Object {
        if ($_) {
            Write-Host $_
        }
    }
    $global:LASTEXITCODE = 0
}

try {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
    $wslRuntime = (& wsl.exe bash -lc "printf '%s' `"`$HOME/apps/voxtral-journal-windows`"" 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host $wslRuntime
        throw "Failed to resolve WSL runtime path."
    }
    $wslRuntime = ($wslRuntime | Select-Object -First 1).Trim()

    Write-Status "Stopping Voxtral journal stack."
    Write-Status "Windows source path: $repoRoot"
    Write-Status "WSL runtime path: $wslRuntime"

    Invoke-WslNoFail -Arguments @("pkill", "-f", "vllm serve")
    Invoke-WslNoFail -Arguments @("pkill", "-f", "mistralai/Voxtral-Mini-3B-2507")
    Invoke-WslNoFail -Arguments @("pkill", "-f", "python -m app.main")
    Invoke-WslNoFail -Arguments @("pkill", "-f", "$wslRuntime/scripts/run_vllm_logged.sh")
    Invoke-WslNoFail -Arguments @("pkill", "-f", "$wslRuntime/scripts/run_ui_logged.sh")

    Write-Status "Remaining matching processes, if any:"
    & wsl.exe bash -lc "pgrep -af 'vllm|Voxtral|mistralai|app.main|run_vllm_logged|run_ui_logged' || true"

    Write-Status "Stop command finished. Logs and data were not deleted."
    exit 0
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)"
    exit 1
}
