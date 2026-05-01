"""Deploy Qwen3-4B as a persistent vLLM endpoint on Modal.

5-minute idle cooldown. OpenAI-compatible API.

Usage:
    modal deploy modal_vllm_server.py

Then use the URL from Modal dashboard or `modal app list`:
    python test_multiturn_app.py --api-url https://<your-modal-url>
"""

import modal
import os
import subprocess
import time

MODEL_NAME = "Qwen/Qwen3-4B"
APP_NAME = "jupyter-agent-vllm"
VLLM_PORT = 8000
GPU_CONFIG = "A100-80GB:1"
MAX_MODEL_LEN = 8192
SCALEDOWN_WINDOW = 300  # 5 min

cuda_version = "12.8.1"
tag = f"{cuda_version}-devel-ubuntu24.04"

VLLM_IMAGE = (
    modal.Image.from_registry(f"nvidia/cuda:{tag}", add_python="3.12")
    .apt_install("git", "curl")
    .run_commands("pip install uv")
    .run_commands("uv pip install --system vllm torch hf_transfer sentencepiece")
    .run_commands(
        "pip install --no-deps "
        "'transformers @ git+https://github.com/huggingface/transformers.git@main' "
        "'huggingface_hub @ git+https://github.com/huggingface/huggingface_hub.git@main'"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/data/hf_cache"})
)

app = modal.App(APP_NAME, image=VLLM_IMAGE, secrets=[modal.Secret.from_name("jupyter-agent-secrets")])
data_volume = modal.Volume.from_name("jupyter-agent-grpo-data", create_if_missing=True)


@app.cls(
    gpu=GPU_CONFIG,
    timeout=60 * 60 * 2,
    scaledown_window=SCALEDOWN_WINDOW,
    max_containers=1,
    volumes={"/data": data_volume},
)
class VLLMServer:

    @modal.enter()
    def start_server(self):
        import torch
        import shutil
        import sys

        print("=" * 60)
        print(f"Starting vLLM: {MODEL_NAME}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print("=" * 60)

        os.environ["HF_HOME"] = "/data/hf_cache"

        # Pre-download
        cache_dir = f"/data/hf_cache/hub/models--{MODEL_NAME.replace('/', '--')}"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        subprocess.run(
            [sys.executable, "-c",
             f"from huggingface_hub import snapshot_download; "
             f"snapshot_download('{MODEL_NAME}', ignore_patterns=['*.gguf', '*.bin'])"],
            check=True,
        )
        data_volume.commit()

        cmd = [
            "vllm", "serve", MODEL_NAME,
            "--host", "0.0.0.0",
            "--port", str(VLLM_PORT),
            "--max-model-len", str(MAX_MODEL_LEN),
            "--generation-config", "vllm",
            "--enable-auto-tool-choice",
            "--tool-call-parser", "hermes",
            "--enforce-eager",
        ]
        print(f"Command: {' '.join(cmd)}")
        self.vllm_proc = subprocess.Popen(cmd)
        self._wait_ready()
        print("=" * 60)
        print("vLLM Ready")
        print("=" * 60)

    def _wait_ready(self, timeout=600):
        import requests
        start = time.time()
        while time.time() - start < timeout:
            if self.vllm_proc.poll() is not None:
                raise RuntimeError(f"vLLM exited with code {self.vllm_proc.returncode}")
            try:
                r = requests.get(f"http://localhost:{VLLM_PORT}/health", timeout=5)
                if r.status_code == 200:
                    print(f"Ready after {time.time()-start:.0f}s")
                    return
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(f"Not ready after {timeout}s")

    @modal.web_server(port=VLLM_PORT, startup_timeout=600)
    def serve(self):
        pass

    @modal.exit()
    def shutdown(self):
        if hasattr(self, "vllm_proc"):
            self.vllm_proc.terminate()
            self.vllm_proc.wait(timeout=10)


@app.local_entrypoint()
def main():
    print(f"Model: {MODEL_NAME}")
    print(f"GPU: {GPU_CONFIG}")
    print(f"Cooldown: {SCALEDOWN_WINDOW}s")
    print()
    print("To deploy:  modal deploy modal_vllm_server.py")
    print("To check:   modal app list")
