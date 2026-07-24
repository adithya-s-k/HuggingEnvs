#!/usr/bin/env python3
"""RL Envs 101 — launch a JupyterLab on Hugging Face Jobs with the tutorial notebooks loaded.

Cross-platform (Windows / macOS / Linux). The only dependency is `huggingface_hub`; this uses its
SDK (`run_job`) rather than the `hf` CLI, so it isn't affected by CLI version/flag differences.

Prereqs (once):
    pip install -U huggingface_hub        # the package (NOT the standalone hf binary)
    hf auth login                          # paste a free token from hf.co/settings/tokens

Run:
    python3 jupyter_launch.py                     # interactive GPU picker (Enter = A100)
    python3 jupyter_launch.py --flavor t4-small   # pick hardware  (list: hf jobs hardware)
    curl -sSL <raw>/tutorials/jupyter_launch.py | python3 -        # one-liner (FLAVOR=t4-small to pick GPU)
    irm  <raw>/tutorials/jupyter_launch.py | python -             # Windows PowerShell

Your notebooks live on a personal HF **storage bucket** mounted as the JupyterLab root, so anything you
edit/create there survives across sessions. Disable with --no-bucket (ephemeral). GPU is pay-as-you-go;
auto-stops at --timeout or `hf jobs cancel`.
"""
import argparse
import os
import sys
import time
import urllib.error
import urllib.request

PORT = 8888
MOUNT = "/notebooks"  # JupyterLab root (bucket-backed when enabled)
DEFAULT_IMAGE = "huggingface/trl"  # TRL image: torch + CUDA + trl preinstalled (same as the experiments)
DEFAULT_REPO = "https://github.com/adithya-s-k/RL_Envs_101.git"
DEFAULT_BUCKET_NAME = "rl-envs-101-notebooks"  # created under your namespace
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
    """Import the huggingface_hub SDK, with clear guidance if it's missing or too old. No auto-install."""
    try:
        from huggingface_hub import HfApi, get_token, login, whoami
    except ImportError:
        sys.exit("❌ huggingface_hub is not installed for this Python.\n"
                 "   Install it (the PACKAGE, not the standalone `hf` binary):\n"
                 f"     {os.path.basename(sys.executable)} -m pip install -U huggingface_hub\n"
                 "   then:  hf auth login")
    import inspect
    if "expose" not in inspect.signature(HfApi.run_job).parameters:
        sys.exit("❌ Your huggingface_hub is too old for HF Jobs. Upgrade:\n"
                 f"     {os.path.basename(sys.executable)} -m pip install -U huggingface_hub")
    return HfApi, get_token, login, whoami


def _open_console():
    """Return a readable console handle (works even under `curl … | python3 -`, where stdin is the script)."""
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


def ensure_bucket(api, whoami, name):
    """Return a 'namespace/name' bucket id, creating the bucket if needed. None on failure (fall back to ephemeral)."""
    try:
        bucket_id = name if "/" in name else f"{whoami()['name']}/{name}"
        api.create_bucket(bucket_id, exist_ok=True)
        return bucket_id
    except Exception as e:
        print(f"⚠️  couldn't set up bucket ({e}); notebooks will be ephemeral this session.")
        return None


def main():
    ap = argparse.ArgumentParser(description="Launch a JupyterLab on HF Jobs with the RL Envs 101 notebooks.")
    ap.add_argument("--flavor", default=os.environ.get("FLAVOR"), help="GPU (list: hf jobs hardware)")
    ap.add_argument("--image", default=os.environ.get("IMAGE", DEFAULT_IMAGE))
    ap.add_argument("--timeout", default=os.environ.get("TIMEOUT", "4h"))
    ap.add_argument("--repo", default=os.environ.get("REPO_URL", DEFAULT_REPO))
    ap.add_argument("--bucket", default=os.environ.get("HF_BUCKET", DEFAULT_BUCKET_NAME),
                    help="HF bucket for your notebooks (default: <you>/rl-envs-101-notebooks)")
    ap.add_argument("--no-bucket", action="store_true", help="don't persist notebooks (ephemeral session)")
    args = ap.parse_args()

    # No flavor given (neither --flavor nor FLAVOR env) -> show the interactive picker.
    if not args.flavor:
        args.flavor = pick_gpu()

    HfApi, get_token, login, whoami = _hub()
    token = os.environ.get("HF_TOKEN") or get_token()
    if not token:
        print("🔑 Need a Hugging Face token (free): https://huggingface.co/settings/tokens")
        login()
        token = get_token()
    if not token:
        sys.exit("❌ No token — run `hf auth login` first.")

    api = HfApi(token=token)
    bucket_id = None if args.no_bucket else ensure_bucket(api, lambda: api.whoami(), args.bucket)

    # Container startup: clone the repo, seed the notebook root (bucket-backed if enabled) without
    # clobbering the user's edits, then serve JupyterLab ROOTED at that folder.
    #   `cd /` first: some images' WORKDIR is /workspace, which we rm below.
    #   `cp -rn`: copy only notebooks that aren't already there, so your saved work is preserved.
    bootstrap = (
        "set -e; cd /; export PATH=/root/.local/bin:$PATH; "
        "command -v git >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq git >/dev/null 2>&1); "
        "pip install -q jupyterlab ipywidgets >/dev/null 2>&1; "
        f"rm -rf /repo; git clone --depth 1 {args.repo} /repo >/dev/null 2>&1; "
        f"mkdir -p {MOUNT}; cp -rn /repo/tutorials/notebooks/. {MOUNT}/ 2>/dev/null || true; "
        f"cd {MOUNT}; "
        "echo '=== JupyterLab starting on :%d ==='; " % PORT
        + f"exec jupyter lab --ip 0.0.0.0 --port {PORT} --no-browser --allow-root --ServerApp.root_dir={MOUNT} "
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
    if bucket_id:  # persist notebooks to your HF bucket, mounted as the JupyterLab root
        from huggingface_hub import Volume
        kwargs["volumes"] = [Volume(type="bucket", source=bucket_id, mount_path=MOUNT, read_only=False)]

    where = f"bucket {bucket_id}" if bucket_id else "ephemeral (no bucket)"
    print(f"🚀 Launching JupyterLab on HF Jobs  (flavor={args.flavor}, image={args.image}, notebooks={where}) ...")
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
    if bucket_id:
        print(f"   💾 notebooks persist on bucket: {bucket_id}")
    print("\n   📋 Track this & all your jobs:  https://huggingface.co/settings/jobs")
    print(f"   logs:  hf jobs logs -f {jid}")
    print(f"   stop:  hf jobs cancel {jid}")
    print("─" * 60)


if __name__ == "__main__":
    main()
