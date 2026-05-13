$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Test-PowerShellSyntax {
    param([string]$Path)
    $tokens = $null
    $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors.Count -gt 0) {
        $errors | ForEach-Object { Write-Host "${Path}: $($_.Message)" }
        throw "PowerShell syntax check failed for $Path"
    }
}

try {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

    Write-Status "Validating launcher scripts without starting vLLM or Gradio."
    Write-Status "Repo root: $repoRoot"

    $requiredFiles = @(
        "scripts\windows_sync_to_wsl_runtime.ps1",
        "scripts\wsl_bootstrap_runtime.sh",
        "scripts\windows_one_click_start.ps1",
        "scripts\windows_stop_stack.ps1",
        "scripts\windows_start_vllm.ps1",
        "scripts\windows_start_ui.ps1",
        "scripts\run_vllm_logged.sh",
        "scripts\run_ui_logged.sh",
        "start_voxtral_webui.cmd",
        "start_voxtral_webui_safe.cmd",
        "start_voxtral_webui_balanced.cmd",
        "start_voxtral_webui_high_context.cmd",
        "stop_voxtral_webui.cmd",
        "requirements.txt",
        "README.md",
        "AGENTS.md"
    )

    foreach ($relativePath in $requiredFiles) {
        $fullPath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path -LiteralPath $fullPath)) {
            throw "Missing required file: $relativePath"
        }
        Write-Status "Found $relativePath"
    }

    $powerShellScripts = @(
        "scripts\windows_sync_to_wsl_runtime.ps1",
        "scripts\windows_one_click_start.ps1",
        "scripts\windows_stop_stack.ps1",
        "scripts\windows_start_vllm.ps1",
        "scripts\windows_start_ui.ps1",
        "scripts\windows_validate_launchers.ps1"
    )
    foreach ($relativePath in $powerShellScripts) {
        Test-PowerShellSyntax -Path (Join-Path $repoRoot $relativePath)
        Write-Status "PowerShell syntax OK: $relativePath"
    }

    $bashScripts = Get-ChildItem -LiteralPath (Join-Path $repoRoot "scripts") -Filter "*.sh" |
        Sort-Object Name |
        ForEach-Object { Join-Path "scripts" $_.Name }
    foreach ($relativePath in $bashScripts) {
        $wslPath = (& wsl.exe wslpath -a ((Join-Path $repoRoot $relativePath) -replace "\\", "/") 2>&1)
        if ($LASTEXITCODE -ne 0) {
            Write-Host $wslPath
            throw "wslpath failed for $relativePath"
        }
        $wslPath = ($wslPath | Select-Object -First 1).Trim()
        & wsl.exe bash -n "$wslPath"
        if ($LASTEXITCODE -ne 0) {
            throw "bash -n failed for $relativePath"
        }
        Write-Status "bash syntax OK: $relativePath"
    }

    $appsCommand = "mkdir -p `"`$HOME/apps`" && printf '%s' `"`$HOME/apps`""
    $appsPath = (& wsl.exe bash -lc $appsCommand 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host $appsPath
        throw "WSL could not resolve or create ~/apps"
    }
    $appsPath = ($appsPath | Select-Object -Last 1).Trim()
    Write-Status "WSL ~/apps path OK: $appsPath"

    Write-Status "Launcher validation complete."
    exit 0
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)"
    exit 1
}
