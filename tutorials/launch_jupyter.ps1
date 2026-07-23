# RL Envs 101 — thin wrapper around the cross-platform launcher (launch_jupyter.py), for Windows.
# Prereqs (once):  pip install -U huggingface_hub ;  hf auth login
# Run:             ./launch_jupyter.ps1 [-flavor a100-large]   (list: hf jobs hardware)
if (-not (Get-Command hf -ErrorAction SilentlyContinue)) { pip install -q -U huggingface_hub }
python "$PSScriptRoot/launch_jupyter.py" @args
