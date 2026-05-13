$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
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

    $stopCommand = @'
set -euo pipefail

patterns=(
  "[v]llm serve"
  "[m]istralai/Voxtral-Mini-3B-2507"
  "[r]un_vllm_logged"
  "[p]ython -m app.main"
  "[r]un_ui_logged"
)

print_matches() {
  local found=0
  for pattern in "${patterns[@]}"; do
    if pgrep -af "${pattern}" >/tmp/voxtral_stop_matches.txt 2>/dev/null; then
      found=1
      cat /tmp/voxtral_stop_matches.txt
    fi
  done
  if [[ "${found}" -eq 1 ]]; then
    return 0
  fi
  return 1
}

for pattern in "${patterns[@]}"; do
  pkill -TERM -f "${pattern}" 2>/dev/null || true
done

for _ in $(seq 1 10); do
  if ! print_matches >/dev/null; then
    echo "No matching vLLM or Gradio processes remain."
    exit 0
  fi
  sleep 1
done

echo "Processes still alive after TERM; sending KILL."
for pattern in "${patterns[@]}"; do
  pkill -KILL -f "${pattern}" 2>/dev/null || true
done

for _ in $(seq 1 10); do
  if ! print_matches >/dev/null; then
    echo "No matching vLLM or Gradio processes remain after KILL."
    exit 0
  fi
  sleep 1
done

echo "WARNING: Matching processes remain after stop attempt:"
print_matches || true
exit 1
'@

    $encodedStopCommand = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($stopCommand))
    $wslStopLauncher = "printf '%s' '$encodedStopCommand' | base64 -d > /tmp/voxtral_stop_stack.sh && bash /tmp/voxtral_stop_stack.sh"
    $stopOutput = & wsl.exe @("bash", "-lc", $wslStopLauncher) 2>&1
    $stopOutput | ForEach-Object {
        if ($_) {
            Write-Host $_
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Stop command could not kill all matching processes."
    }

    Write-Status "Stop command finished. Logs and data were not deleted."
    exit 0
}
catch {
    Write-Status "ERROR: $($_.Exception.Message)"
    exit 1
}
