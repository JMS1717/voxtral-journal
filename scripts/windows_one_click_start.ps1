param(
    [ValidateSet("safe", "balanced", "high-context")]
    [string]$Profile = "safe"
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line
    if ($script:OneClickLog) {
        Add-Content -LiteralPath $script:OneClickLog -Value $line
    }
}

function Add-LogBlock {
    param(
        [string]$Title,
        [string[]]$Lines
    )
    Write-Status $Title
    foreach ($line in $Lines) {
        Write-Host $line
        if ($script:OneClickLog) {
            Add-Content -LiteralPath $script:OneClickLog -Value $line
        }
    }
}

function Invoke-NativeCapture {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldEap
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

function Write-CapturedOutput {
    param(
        [object[]]$Lines,
        [switch]$Log
    )

    foreach ($line in @($Lines)) {
        if ($null -ne $line -and "$line" -ne "") {
            Write-Host "$line"
            if ($Log -and $script:OneClickLog) {
                Add-Content -LiteralPath $script:OneClickLog -Value "$line"
            }
        }
    }
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Wait-HttpOk {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds,
        [int]$StatusEverySeconds = 25
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $nextStatus = Get-Date

    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url) {
            Write-Status "$Name is ready: $Url"
            return $true
        }

        if ((Get-Date) -ge $nextStatus) {
            $remaining = [Math]::Max(0, [int]($deadline - (Get-Date)).TotalSeconds)
            Write-Status "Waiting for $Name at $Url. Timeout in ${remaining}s."
            $nextStatus = (Get-Date).AddSeconds($StatusEverySeconds)
        }

        Start-Sleep -Seconds 5
    }

    return $false
}

function Get-WslTail {
    param(
        [string]$WslRepo,
        [string]$LogPath,
        [int]$Lines = 120
    )

    $command = "cd '$WslRepo' && if [ -f '$LogPath' ]; then tail -n $Lines '$LogPath'; else echo '$LogPath does not exist'; fi"
    $result = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("bash", "-lc", $command)
    return $result.Output
}

function Invoke-WslNoFail {
    param([string[]]$Arguments)
    $result = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments $Arguments
    Write-CapturedOutput -Lines $result.Output -Log
    $global:LASTEXITCODE = 0
}

function ConvertTo-WindowsPathFromWsl {
    param([string]$WslPath)
    $result = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("wslpath", "-w", "$WslPath")
    if ($result.ExitCode -ne 0) {
        Write-CapturedOutput -Lines $result.Output
        throw "Failed to convert WSL path to Windows path: $WslPath"
    }
    return ($result.Output | Select-Object -First 1).ToString().Trim()
}

function Get-VllmProfileConfig {
    param([string]$ProfileName)

    switch ($ProfileName) {
        "safe" {
            return [pscustomobject]@{
                Name = "safe"
                MaxModelLen = 8192
                GpuMemoryUtilization = "0.90"
                MaxNumSeqs = "1"
                EnforceEager = "true"
                ExtraArgs = ""
                Summary = "safe 8192 profile with enforce eager and 0.90 GPU memory utilization"
            }
        }
        "balanced" {
            return [pscustomobject]@{
                Name = "balanced"
                MaxModelLen = 8192
                GpuMemoryUtilization = "0.90"
                MaxNumSeqs = "1"
                EnforceEager = "false"
                ExtraArgs = ""
                Summary = "balanced 8192 profile"
            }
        }
        "high-context" {
            return [pscustomobject]@{
                Name = "high-context"
                MaxModelLen = 16384
                GpuMemoryUtilization = "0.90"
                MaxNumSeqs = "1"
                EnforceEager = "false"
                ExtraArgs = ""
                Summary = "high-context 16384 profile with 0.90 GPU memory utilization"
            }
        }
        default {
            throw "Unknown profile: $ProfileName"
        }
    }
}

function Get-VllmMemoryFailureMessage {
    param([object[]]$Lines)

    $joined = ($Lines | ForEach-Object { "$_" }) -join "`n"
    if ($joined -match "No available memory for the cache blocks|Available KV cache memory") {
        return "Your GPU does not have enough free VRAM for this profile. Close GPU apps or use the safe 8192 profile."
    }

    return $null
}

function Test-VllmExtraArgs {
    param([string]$ExtraArgs)

    if ($ExtraArgs -match "(^|\s)--(gpu-memory-utilization|max-model-len|max-num-seqs|enforce-eager)(\s|=|$)") {
        throw "VLLM_EXTRA_ARGS contains a core vLLM flag. Use the dedicated VLLM_* profile fields instead."
    }
}

function ConvertTo-WslSingleQuoted {
    param([string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

try {
    $profileConfig = Get-VllmProfileConfig -ProfileName $Profile
    Test-VllmExtraArgs -ExtraArgs $profileConfig.ExtraArgs
    $scriptDir = Split-Path -Parent $PSCommandPath
    $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

    Write-Host "Voxtral Journal Windows one-click start"
    Write-Host "Profile: $($profileConfig.Name) ($($profileConfig.Summary))"
    Write-Host "Windows source path: $repoRoot"

    Write-Host "Checking WSL installation."
    $wslList = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("-l", "-v")
    if ($wslList.ExitCode -ne 0) {
        Write-CapturedOutput -Lines $wslList.Output
        throw "WSL is not available. Install or repair WSL2 Ubuntu, then rerun this launcher."
    }
    Write-CapturedOutput -Lines $wslList.Output

    $syncScript = Join-Path $scriptDir "windows_sync_to_wsl_runtime.ps1"
    Write-Host "Syncing source repo to WSL-native runtime copy."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $syncScript
    if ($LASTEXITCODE -ne 0) {
        throw "WSL runtime sync failed."
    }

    $wslRepoResult = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("bash", "-lc", "printf '%s' `"`$HOME/apps/voxtral-journal-windows`"")
    if ($wslRepoResult.ExitCode -ne 0) {
        Write-CapturedOutput -Lines $wslRepoResult.Output
        throw "Failed to resolve WSL runtime path."
    }
    $wslRepo = ($wslRepoResult.Output | Select-Object -First 1).ToString().Trim()

    $runtimeLogDir = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("bash", "-lc", "mkdir -p '$wslRepo/data/logs' && printf '%s' '$wslRepo/data/logs'")
    if ($runtimeLogDir.ExitCode -ne 0) {
        Write-CapturedOutput -Lines $runtimeLogDir.Output
        throw "Failed to create runtime log directory."
    }

    $script:OneClickLog = ConvertTo-WindowsPathFromWsl "$wslRepo/data/logs/one_click_start.log"
    Set-Content -LiteralPath $script:OneClickLog -Value $null

    Write-Status "Windows source path: $repoRoot"
    Write-Status "WSL runtime path: $wslRepo"
    Write-Status "Runtime logs: $wslRepo/data/logs"

    Write-Status "Ensuring WSL runtime is bootstrapped. This is fast after the first run."
    $bootstrapCommand = "cd '$wslRepo' && bash scripts/wsl_bootstrap_runtime.sh"
    $bootstrapResult = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("bash", "-lc", $bootstrapCommand)
    Write-CapturedOutput -Lines $bootstrapResult.Output -Log
    if ($bootstrapResult.ExitCode -ne 0) {
        throw "Runtime bootstrap failed."
    }

    Write-Status "Checking GPU visibility in WSL."
    $gpu = Invoke-NativeCapture -FilePath "wsl.exe" -Arguments @("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader")
    if ($gpu.ExitCode -eq 0) {
        Add-LogBlock "GPU check:" $gpu.Output
    }
    else {
        Add-LogBlock "GPU check returned a non-zero exit. Continuing, but vLLM may fail:" $gpu.Output
    }

    Write-Status "Stopping stale vLLM and Gradio processes."
    $stopScript = Join-Path $scriptDir "windows_stop_stack.ps1"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopScript
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop stale vLLM or Gradio processes."
    }

    Write-Status "Starting vLLM from WSL runtime copy with profile $($profileConfig.Name)."
    Write-Status "Effective VLLM_MAX_MODEL_LEN=$($profileConfig.MaxModelLen)"
    Write-Status "Effective VLLM_GPU_MEMORY_UTILIZATION=$($profileConfig.GpuMemoryUtilization)"
    Write-Status "Effective VLLM_MAX_NUM_SEQS=$($profileConfig.MaxNumSeqs)"
    Write-Status "Effective VLLM_ENFORCE_EAGER=$($profileConfig.EnforceEager)"
    Write-Status "Effective VLLM_EXTRA_ARGS=$($profileConfig.ExtraArgs)"
    Write-Status "Final vLLM command line: vllm serve mistralai/Voxtral-Mini-3B-2507 --host 0.0.0.0 --port 8000 --tokenizer_mode mistral --config_format mistral --load_format mistral --max-model-len $($profileConfig.MaxModelLen) --gpu-memory-utilization $($profileConfig.GpuMemoryUtilization) --max-num-seqs $($profileConfig.MaxNumSeqs)$(@{true=' --enforce-eager'; false=''}[$profileConfig.EnforceEager])"
    $vllmProcess = Start-Process -FilePath "wsl.exe" `
        -ArgumentList @(
            "env",
            "VLLM_MAX_MODEL_LEN=$($profileConfig.MaxModelLen)",
            "VLLM_GPU_MEMORY_UTILIZATION=$($profileConfig.GpuMemoryUtilization)",
            "VLLM_MAX_NUM_SEQS=$($profileConfig.MaxNumSeqs)",
            "VLLM_ENFORCE_EAGER=$($profileConfig.EnforceEager)",
            "VLLM_EXTRA_ARGS=$($profileConfig.ExtraArgs)",
            "bash",
            "$wslRepo/scripts/run_vllm_logged.sh"
        ) `
        -WindowStyle Hidden `
        -PassThru
    Write-Status "vLLM launcher process started. Windows PID: $($vllmProcess.Id)"

    if (-not (Wait-HttpOk -Name "vLLM" -Url "http://localhost:8000/v1/models" -TimeoutSeconds 180 -StatusEverySeconds 25)) {
        $tail = Get-WslTail -WslRepo $wslRepo -LogPath "data/logs/vllm.log" -Lines 120
        Add-LogBlock "vLLM failed to become ready. Tail of runtime data/logs/vllm.log:" $tail
        $memoryFailureMessage = Get-VllmMemoryFailureMessage -Lines $tail
        if ($memoryFailureMessage) {
            Write-Status $memoryFailureMessage
        }
        throw "vLLM did not become ready. Check CUDA/GPU availability, Hugging Face model access, and $wslRepo/data/logs/vllm.log."
    }

    Write-Status "Starting Gradio UI from WSL runtime copy."
    $uiProcess = Start-Process -FilePath "wsl.exe" `
        -ArgumentList @("bash", "$wslRepo/scripts/run_ui_logged.sh") `
        -WindowStyle Hidden `
        -PassThru
    Write-Status "Gradio launcher process started. Windows PID: $($uiProcess.Id)"

    if (-not (Wait-HttpOk -Name "Gradio UI" -Url "http://localhost:7860" -TimeoutSeconds 240 -StatusEverySeconds 20)) {
        $tail = Get-WslTail -WslRepo $wslRepo -LogPath "data/logs/gradio.log" -Lines 120
        Add-LogBlock "Gradio failed to become ready. Tail of runtime data/logs/gradio.log:" $tail
        throw "Gradio did not become ready. Check the runtime venv, app startup errors, and $wslRepo/data/logs/gradio.log."
    }

    Write-Status "Opening browser to http://localhost:7860"
    Start-Process "http://localhost:7860"

    Write-Host ""
    Write-Host "UI: http://localhost:7860"
    Write-Host "vLLM: http://localhost:8000/v1/models"
    Write-Host "Windows source path: $repoRoot"
    Write-Host "WSL runtime path: $wslRepo"
    Write-Host "Runtime logs:"
    Write-Host "  $wslRepo/data/logs/vllm.log"
    Write-Host "  $wslRepo/data/logs/vllm_launcher.log"
    Write-Host "  $wslRepo/data/logs/gradio.log"
    Write-Host "  $wslRepo/data/logs/one_click_start.log"
    exit 0
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "Fix the issue above, then rerun:"
    Write-Host "  .\start_voxtral_webui.cmd"
    exit 1
}
