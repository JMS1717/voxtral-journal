$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$wslRepo = (wsl.exe wslpath -a "$repoRoot").Trim()
$audioPath = "/path/to/journal.m4a"

wsl.exe bash -lc "cd '$wslRepo' && . .venv/bin/activate && python scripts/smoke_vllm_audio_real.py '$audioPath' --seconds 30 --language en"
