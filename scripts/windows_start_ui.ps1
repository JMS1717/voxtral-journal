$ErrorActionPreference = "Stop"

$wslRepo = (& wsl.exe bash -lc "printf '%s' `"`$HOME/apps/voxtral-journal-windows`"" 2>&1)
if ($LASTEXITCODE -ne 0) {
    $wslRepo | ForEach-Object { Write-Host $_ }
    throw "Failed to resolve WSL runtime path."
}
$wslRepo = ($wslRepo | Select-Object -First 1).Trim()

& wsl.exe test -d "$wslRepo"
if ($LASTEXITCODE -ne 0) {
    throw "Missing WSL runtime copy at $wslRepo. Run .\start_voxtral_webui.cmd first so it can sync and bootstrap the runtime."
}

wsl.exe bash -lc "cd '$wslRepo' && make start-ui"
