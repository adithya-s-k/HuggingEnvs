#!/usr/bin/env python3
"""RL Envs 101 — launch a JupyterLab on Hugging Face Jobs with the tutorial notebooks loaded.

Cross-platform (Windows / macOS / Linux). Alternative to launch.sh / .ps1 for people who
already have Python — same result, uses the huggingface_hub SDK (`run_job`) instead of the `hf` CLI.

Prereqs (once):  pip install -U huggingface_hub   &&   hf auth login
Run:             python launch.py                    # default A100 (80 GB)
                 python launch.py --flavor t4-small  # pick hardware  (list: hf jobs hardware)
       one-line:  curl -sSL <raw>/tutorials/launch.py | python3 -     (FLAVOR=t4-small to pick GPU)

Opens a JupyterLab URL in ~1-2 min. GPU is pay-as-you-go; auto-stops at --timeout or `hf jobs cancel`.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 8888
DEFAULT_IMAGE = "huggingface/trl"  # TRL image: torch + CUDA + trl preinstalled (same as the experiments)
DEFAULT_REPO = "https://github.com/adithya-s-k/RL_Envs_101.git"
TERMINAL_STAGES = {"CANCELED", "CANCELLED", "ERROR", "FAILED", "COMPLETED", "DELETED"}

# Curated GPU menu (name, description). Full list: `hf jobs hardware`.
GPU_MENU = [
    ("t4-small",   "1x T4  16GB  · $0.40/hr · cheapest, slow"),
    ("l4x1",       "1x L4  24GB  · $0.80/hr · good budget pick"),
    ("a10g-large", "1x A10G 24GB · $1.50/hr"),
    ("l40sx1",     "1x L40S 48GB · $1.80/hr · roomy VRAM"),
    ("a100-large", "1x A100 80GB · $2.50/hr · recommended for these tutorials"),
    ("h200",       "1x H200 141GB · $5.00/hr · fastest"),
]
DEFAULT_FLAVOR = "a100-large"


def _hub():
    try:
        import huggingface_hub  # noqa
    except ImportError:
        print("installing huggingface_hub ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub"], check=True)
    from huggingface_hub import HfApi, get_token, login
    return HfApi, get_token, login


def _open_console():
    """Return a readable console handle (works even under `curl … | python -`, where stdin is the script)."""
    try:
        return open("CON") if os.name == "nt" else open("/dev/tty")
    except OSError:
        return None


def pick_gpu():
    """Interactive GPU picker. Falls back to the default if no console is available."""
    con = _open_console()
    if con is None:
        return DEFAULT_FLAVOR
    default_i = next(i for i, (n, _) in enumerate(GPU_MENU) if n == DEFAULT_FLAVOR)
    print(f"Select a GPU  (Enter = {DEFAULT_FLAVOR}, the default):")
    for i, (name, desc) in enumerate(GPU_MENU):
        star = "*" if i == default_i else " "
        print(f"  {star}{i + 1}) {name:<12} {desc}")
    print(f"  {len(GPU_MENU) + 1}) other      (type any flavor name — see: hf jobs hardware)")
    try:
        print("> ", end="", flush=True)
        choice = con.readline().strip()
    except (EOFError, OSError):
        choice = ""
    if not choice:
        return DEFAULT_FLAVOR
    if choice.isdigit():
        n = int(choice)
        if n == len(GPU_MENU) + 1:
            print("flavor name > ", end="", flush=True)
            return con.readline().strip() or DEFAULT_FLAVOR
        if 1 <= n <= len(GPU_MENU):
            return GPU_MENU[n - 1][0]
    return choice  # user typed a flavor name directly


def main():
    ap = argparse.ArgumentParser(description="Launch a JupyterLab on HF Jobs with the RL Envs 101 notebooks.")
    ap.add_argument("--flavor", default=os.environ.get("FLAVOR"), help="GPU (list: hf jobs hardware)")
    ap.add_argument("--image", default=os.environ.get("IMAGE", DEFAULT_IMAGE))
    ap.add_argument("--timeout", default=os.environ.get("TIMEOUT", "4h"))
    ap.add_argument("--repo", default=os.environ.get("REPO_URL", DEFAULT_REPO))
    ap.add_argument("--bucket", default=os.environ.get("HF_BUCKET", ""),
                    help="optional HF bucket 'name' to mount at /workspace/persist (survives restarts)")
    args = ap.parse_args()

    # No flavor given (neither --flavor nor FLAVOR env) -> show the interactive picker.
    if not args.flavor:
        args.flavor = pick_gpu()

    HfApi, get_token, login = _hub()
    token = os.environ.get("HF_TOKEN") or get_token()
    if not token:
        print("🔑 Need a Hugging Face token (free): https://huggingface.co/settings/tokens")
        login()
        token = get_token()
    if not token:
        sys.exit("❌ No token — run `hf auth login` first.")

    # Container startup: ensure git, install JupyterLab, clone the repo, serve on :8888 through the proxy.
    bootstrap = (
        "set -e; cd /; export PATH=/root/.local/bin:$PATH; "  # cd / first: some images' WORKDIR is /workspace, which we rm below
        "command -v git >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1); "
        "pip install -q jupyterlab ipywidgets >/dev/null 2>&1; "
        f"rm -rf /workspace; git clone --depth 1 {args.repo} /workspace >/dev/null 2>&1; "
        "cd /workspace/tutorials 2>/dev/null || cd /workspace; "
        "echo '=== JupyterLab starting on :%d ==='; " % PORT
        + f"exec jupyter lab --ip 0.0.0.0 --port {PORT} --no-browser --allow-root "
        "--ServerApp.token='' --ServerApp.password='' "
        "--ServerApp.disable_check_xsrf=True --ServerApp.allow_origin='*' --ServerApp.trust_xheaders=True"
    )

    kwargs = dict(
        image=args.image,
        command=["bash", "-lc", bootstrap],
        secrets={"HF_TOKEN": token},
        flavor=args.flavor,
        timeout=args.timeout,
        expose=[PORT],
    )
    if args.bucket:  # optional: persist your work to an HF bucket mounted at /workspace/persist
        from huggingface_hub import Volume
        kwargs["volumes"] = [Volume(type="bucket", source=args.bucket, mount_path="/workspace/persist", read_only=False)]

    print(f"🚀 Launching JupyterLab on HF Jobs  (flavor={args.flavor}, image={args.image}) ...")
    api = HfApi(token=token)
    job = api.run_job(**kwargs)
    jid = getattr(job, "id", None) or getattr(job, "job_id", "<job-id>")
    lab = f"https://{jid}--{PORT}.hf.jobs/lab"

    # Wait until JupyterLab answers (image pull + clone can take a few min), while also watching the
    # job's status so a cancel / error from the dashboard is reflected here immediately.
    print(f"   job {jid}  ·  waiting for JupyterLab to come up ", end="", flush=True)
    ready, stopped = False, None
    for _ in range(90):  # up to ~7.5 min
        try:
            stage = api.inspect_job(job_id=jid).status.stage
        except Exception:
            stage = None
        if stage in TERMINAL_STAGES:
            stopped = stage
            break
        try:
            req = urllib.request.Request(lab, headers={"Authorization": f"Bearer {token}"})
            if urllib.request.urlopen(req, timeout=10).status == 200:
                ready = True
                break
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print()

    print("─" * 60)
    if stopped:
        print(f"❌ Job is no longer running (status: {stopped}).")
        print("   📋 dashboard:  https://huggingface.co/settings/jobs")
        print(f"   logs:         hf jobs logs {jid}")
        print("─" * 60)
        sys.exit(1)
    print("✅ JupyterLab is READY — open it:" if ready else "⏳ Still starting — it should come up shortly at:")
    print(f"     {lab}")
    print("   (log into huggingface.co in the same browser first)")
    print("\n   📋 Track this & all your jobs:  https://huggingface.co/settings/jobs")
    print(f"   logs:  hf jobs logs -f {jid}")
    print(f"   stop:  hf jobs cancel {jid}")
    print("─" * 60)


if __name__ == "__main__":
    main()
