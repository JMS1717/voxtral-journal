param(
    [Parameter(Mandatory = $true)]
    [string]$AudioPath,
    [int]$Seconds = 30,
    [string]$Language = "en"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$wslRepo = (wsl.exe wslpath -a "$repoRoot").Trim()

if (Test-Path -LiteralPath $AudioPath) {
    $resolvedAudio = (Resolve-Path -LiteralPath $AudioPath).Path
    $audioForWsl = (wsl.exe wslpath -a ($resolvedAudio -replace "\\", "/")).Trim()
}
else {
    $audioForWsl = $AudioPath
}

wsl.exe bash -lc "cd '$wslRepo' && . .venv/bin/activate && python scripts/smoke_vllm_audio_real.py '$audioForWsl' --seconds $Seconds --language '$Language'"
