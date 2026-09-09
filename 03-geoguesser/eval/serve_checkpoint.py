# /// script
# requires-python = ">=3.11"
# dependencies = [
#   # Pinned: this is the version whose resolved config is verified against this
#   # model. Qwen3.5 is hybrid attention/mamba and its vLLM support is
#   # version-sensitive. See README.md.
#   "vllm==0.25.1",
#   "gradio",
#   "huggingface-hub",
# ]
# ///

"""
Serve Qwen3.5-4B plus LoRA checkpoints on a GPU Job and print a public URL.

Hugging Face Jobs expose no port, so the URL comes from a Gradio tunnel opened
from inside the container. The eval then runs from wherever you like against
that URL, which is what makes iterating on the eval cheap: no 8-minute job
startup and no staging code onto a bucket to change one line.

The tunnel URL is reachable by anyone who has it, for as long as this job runs.
It serves a base model and adapters, so nothing private is behind it -- but it
is not access-controlled, so treat the URL as a secret and keep the job's
timeout tight.

Serve arguments are held verbatim from a hand-verified configuration; see
README.md for what each one does and which two are load-bearing.

Usage:

    hf jobs uv run --flavor a100-large --timeout 3h \\
      --secrets HF_TOKEN --image huggingface/trl \\
      -v hf://buckets/AdithyaSK/geoguesser-runs:/outputs \\
      -e ADAPTERS="ckpt50=/outputs/<run>/checkpoint-50" \\
      eval/serve_checkpoint.py

Then read the URL out of the job logs:

    hf jobs logs <job-id> | grep ENDPOINT

Runtime LoRA updating is enabled, so a checkpoint that appears after the server
is already up does not need a new endpoint:

    curl $URL/../v1/load_lora_adapter -H 'Content-Type: application/json' \
      -d '{"lora_name":"ckpt450","lora_path":"/outputs/<run>/checkpoint-450"}'

That endpoint is only exposed because VLLM_ALLOW_RUNTIME_LORA_UPDATING is set,
and it accepts a filesystem path -- which works here because the run bucket is
mounted at /outputs inside the job.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("serve")

MODEL = os.getenv("MODEL", "Qwen/Qwen3.5-4B")
PORT = int(os.getenv("PORT", "8190"))
ADAPTERS = os.getenv("ADAPTERS", "")
SERVER_TIMEOUT_S = int(os.getenv("SERVER_TIMEOUT_S", "1800"))
# How long to hold the tunnel open once the server is up. The job's own
# --timeout is the hard stop; this keeps the process from lingering if the
# job timeout is generous.
HOLD_S = int(os.getenv("HOLD_S", "10800"))

SERVE_ARGS = [
    "--host",
    "127.0.0.1",
    "--port",
    str(PORT),
    "--tensor-parallel-size",
    "1",
    "--max-model-len",
    "32768",
    "--gpu-memory-utilization",
    os.getenv("GPU_MEM", "0.92"),
    "--trust-remote-code",
    "--enable-auto-tool-choice",
    "--tool-call-parser",
    "qwen3_xml",
    "--reasoning-parser",
    "qwen3",
    "--default-chat-template-kwargs",
    '{"enable_thinking": false}',
    "--enable-lora",
    "--max-lora-rank",
    "16",
    # Adapters are 12.6 MB each, so keeping several resident is free. A vLLM
    # boot costs ~8 minutes against ~6 for a checkpoint's pass@4, so batching
    # checkpoints per endpoint is the single biggest saving available.
    "--max-loras",
    os.getenv("MAX_LORAS", "8"),
    "--mm-processor-cache-type",
    "shm",
]

# vLLM's kernel_warmup calls deep_gemm_warmup on Hopper (sm90); with a stale
# deep_gemm importable the probe raises and the server dies at startup. Inert
# on A100 (sm80), which is why the same launch passes there and fails on H200.
SERVE_ENV = {
    "VLLM_USE_DEEP_GEMM": "0",
    "VLLM_DEEP_GEMM_WARMUP": "skip",
    # Lets a caller POST /v1/load_lora_adapter to attach a checkpoint to the
    # running server, so a later checkpoint costs seconds instead of another
    # ~8 minute boot.
    "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "1",
}


def parse_adapters(spec: str) -> list[tuple[str, str]]:
    """
    Split the `ADAPTERS` spec into `(name, path)` pairs.

    Args:
        spec (`str`):
            Comma-separated `name=/path` entries.

    Returns:
        `list` of `tuple`: One `(name, path)` per adapter that exists on disk.
    """
    pairs = []
    for entry in filter(None, (part.strip() for part in spec.split(","))):
        if "=" not in entry:
            logger.warning("ignoring malformed adapter spec %r", entry)
            continue
        name, path = entry.split("=", 1)
        if not pathlib.Path(path).is_dir():
            logger.warning("adapter %s not found at %s -- skipping", name, path)
            continue
        pairs.append((name.strip(), path.strip()))
    return pairs


def wait_until_ready(server: subprocess.Popen, timeout_s: int) -> list[str]:
    """
    Block until the server answers, then return the model ids it registered.

    Args:
        server (`subprocess.Popen`):
            The server process, watched so a startup crash fails fast.
        timeout_s (`int`):
            How long to wait.

    Returns:
        `list` of `str`: Model ids served, base plus adapters.

    Raises:
        RuntimeError: If the server exits, or never becomes ready.
    """
    deadline = time.monotonic() + timeout_s
    url = f"http://127.0.0.1:{PORT}/v1/models"
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"vllm exited during startup (code {server.returncode})")
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return [row["id"] for row in json.load(response)["data"]]
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
            time.sleep(5)
    raise RuntimeError(f"server not ready within {timeout_s}s")


def open_tunnel(port: int) -> str:
    """
    Expose a local port through Gradio's tunnel and return the public URL.

    Args:
        port (`int`):
            Local port to expose.

    Returns:
        `str`: The public base URL, without a trailing slash.
    """
    from gradio import networking

    return networking.setup_tunnel(
        local_host="127.0.0.1",
        local_port=port,
        share_token=secrets.token_urlsafe(32),
        share_server_address=None,
        share_server_tls_certificate=None,
    ).rstrip("/")


def _assert_adapter_shapes(base: str, adapters: list[tuple[str, str]]) -> None:
    """
    Refuse an adapter whose own config names a different base model.

    Args:
        base (`str`):
            The base model id being served.
        adapters (`list[tuple[str, str]]`):
            `(name, path)` pairs as passed to vLLM.

    Raises:
        RuntimeError: If an adapter declares a different `base_model_name_or_path`.
    """
    for name, path in adapters:
        config = pathlib.Path(path) / "adapter_config.json"
        if not config.exists():
            logger.warning("%s: no adapter_config.json at %s, cannot verify", name, path)
            continue
        declared = json.loads(config.read_text()).get("base_model_name_or_path")
        if declared and declared != base:
            raise RuntimeError(
                f"adapter {name!r} was trained on {declared!r} but the server is "
                f"serving {base!r}. Serving it anyway produces plausible nonsense."
            )
        logger.info("%s: base %s, verified", name, declared or "unknown")


def main() -> None:
    """Serve, expose, announce, and hold the tunnel open."""
    adapters = parse_adapters(ADAPTERS)
    command = ["vllm", "serve", MODEL, *SERVE_ARGS]
    if adapters:
        command.append("--lora-modules")
        command += [f"{name}={path}" for name, path in adapters]
    logger.info("serving: %s", " ".join(command))

    server = subprocess.Popen(
        command, env={**os.environ, **SERVE_ENV}, stdout=sys.stdout, stderr=sys.stderr
    )
    try:
        served = wait_until_ready(server, SERVER_TIMEOUT_S)

        # The check the docs claimed existed and did not. vLLM accepts a 2B
        # adapter on a 4B base, logs `Loaded new LoRA adapter` and answers
        # anyway, which is how four of run 2's checkpoint scores turned out to
        # be nonsense that looked ordinary. Refuse rather than serve.
        missing = [name for name, _ in adapters if name not in served]
        if MODEL not in served:
            raise RuntimeError(
                f"the server does not list the requested base {MODEL!r}; "
                f"it serves {served}"
            )
        if missing:
            raise RuntimeError(
                f"adapter(s) {missing} were requested but are not served; "
                f"the server lists {served}. An adapter trained on a different "
                "base is the usual cause, and vLLM will not always say so."
            )
        _assert_adapter_shapes(MODEL, adapters)

        public = open_tunnel(PORT)
        # Announced on one greppable line each, so the caller can pull them out
        # of the job log without parsing vLLM's own output.
        logger.info("ENDPOINT %s/v1", public)
        for name in served:
            logger.info("ENDPOINT_MODEL %s", name)
        logger.info("ENDPOINT_READY %d model(s), holding for %d s", len(served), HOLD_S)

        deadline = time.monotonic() + HOLD_S
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"vllm exited (code {server.returncode})")
            time.sleep(30)
        logger.info("hold elapsed, shutting down")
    finally:
        server.terminate()
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
