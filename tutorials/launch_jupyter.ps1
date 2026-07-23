# RL Envs 101 — spin up a JupyterLab on Hugging Face Jobs with the tutorial notebooks loaded (Windows).
# Pure PowerShell: uses ONLY the `hf` CLI (no Python needed).
#
# Prereqs (once):
#   powershell -ExecutionPolicy ByPass -c "irm https://hf.co/cli/install.ps1 | iex"   # or: pip install -U huggingface_hub
#   hf auth login                                      # paste a free token from hf.co/settings/tokens
#
# Run:   ./launch_jupyter.ps1 [-Flavor t4-small]       Default: a100-large.   List: hf jobs hardware
param(
  [string]$Flavor  = $(if ($env:FLAVOR)  { $env:FLAVOR }  else { "a100-large" }),
  [string]$Timeout = $(if ($env:TIMEOUT) { $env:TIMEOUT } else { "4h" }),
  [string]$Image   = $(if ($env:IMAGE)   { $env:IMAGE }   else { "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel" })
)
$ErrorActionPreference = "Stop"
$Repo = if ($env:REPO_URL) { $env:REPO_URL } else { "https://github.com/adithya-s-k/RL_Envs_101.git" }
$Port = 8888

if (-not (Get-Command hf -ErrorAction SilentlyContinue)) {
  Write-Host "❌ 'hf' CLI not found. Install it first:"
  Write-Host '     powershell -ExecutionPolicy ByPass -c "irm https://hf.co/cli/install.ps1 | iex"'
  Write-Host "   then:  hf auth login"; exit 1
}
$Token = if ($env:HF_TOKEN) { $env:HF_TOKEN } else { (hf auth token 2>$null) }
if (-not $Token) { Write-Host "❌ Not logged in. Run:  hf auth login"; exit 1 }

# Single-line container bootstrap (no newlines — the CLI mangles multi-line commands).
$Boot = "set -e; command -v git >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1); pip install -q jupyterlab ipywidgets >/dev/null 2>&1; rm -rf /workspace; git clone --depth 1 $Repo /workspace >/dev/null 2>&1; cd /workspace/tutorials 2>/dev/null || cd /workspace; echo '=== JupyterLab starting on :$Port ==='; exec jupyter lab --ip 0.0.0.0 --port $Port --no-browser --allow-root --ServerApp.token= --ServerApp.password= --ServerApp.disable_check_xsrf=True --ServerApp.allow_origin=* --ServerApp.trust_xheaders=True"

Write-Host "🚀 Launching JupyterLab on HF Jobs (flavor=$Flavor) ..."
# NOTE: the `--` before the command is REQUIRED so the CLI stops parsing flags and forwards bash -c intact.
$Out = hf jobs run --flavor $Flavor --timeout $Timeout --expose $Port -s "HF_TOKEN=$Token" -d $Image -- bash -c $Boot 2>&1
$Jid = ([regex]::Match([string]$Out, '[0-9a-f]{24}')).Value

Write-Host "────────────────────────────────────────────────────────────"
Write-Host "⏳ Ready in ~1-2 min at:"
Write-Host "     https://$Jid--$Port.hf.jobs/lab"
Write-Host "   (log into huggingface.co in the same browser first)"
Write-Host "   logs:  hf jobs logs -f $Jid"
Write-Host "   stop:  hf jobs cancel $Jid"
Write-Host "────────────────────────────────────────────────────────────"
