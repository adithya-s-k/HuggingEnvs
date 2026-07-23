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
DEFAULT_IMAGE = "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel"
DEFAULT_REPO = "https://github.com/adithya-s-k/RL_Envs_101.git"


def _hub():
    try:
        import huggingface_hub  # noqa
    except ImportError:
        print("installing huggingface_hub ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub"], check=True)
    from huggingface_hub import HfApi, get_token, login
    return HfApi, get_token, login


def main():
    ap = argparse.ArgumentParser(description="Launch a JupyterLab on HF Jobs with the RL Envs 101 notebooks.")
    ap.add_argument("--flavor", default=os.environ.get("FLAVOR", "a100-large"), help="GPU (list: hf jobs hardware)")
    ap.add_argument("--image", default=os.environ.get("IMAGE", DEFAULT_IMAGE))
    ap.add_argument("--timeout", default=os.environ.get("TIMEOUT", "4h"))
    ap.add_argument("--repo", default=os.environ.get("REPO_URL", DEFAULT_REPO))
    ap.add_argument("--bucket", default=os.environ.get("HF_BUCKET", ""),
                    help="optional HF bucket 'name' to mount at /workspace/persist (survives restarts)")
    args = ap.parse_args()

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
        "set -e; export PATH=/root/.local/bin:$PATH; "
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
    job = HfApi(token=token).run_job(**kwargs)
    jid = getattr(job, "id", None) or getattr(job, "job_id", "<job-id>")
    lab = f"https://{jid}--{PORT}.hf.jobs/lab"

    # Wait until JupyterLab actually answers (image pull + pip + clone can take a few min).
    print(f"   job {jid}  ·  waiting for JupyterLab to come up ", end="", flush=True)
    ready = False
    for _ in range(90):  # up to ~7.5 min
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
    print("✅ JupyterLab is READY — open it:" if ready else "⏳ Still starting — it should come up shortly at:")
    print(f"     {lab}")
    print("   (log into huggingface.co in the same browser first)")
    print("\n   📋 Track this & all your jobs:  https://huggingface.co/settings/jobs")
    print(f"   logs:  hf jobs logs -f {jid}")
    print(f"   stop:  hf jobs cancel {jid}")
    print("─" * 60)


if __name__ == "__main__":
    main()
