"""Inference helpers for Qwen/Qwen3-1.7B.

Supports:
- offline inference via `transformers`
- online inference against an OpenAI-compatible vLLM server
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = "Qwen/Qwen3-1.7B"
DEFAULT_SYSTEM_PROMPT = (
    "You are a precise coding and data analysis assistant. "
    "Think through the task carefully and return a direct answer."
)


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def build_messages(prompt: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


@dataclass
class OnlineQwenInference:
    model: str = DEFAULT_MODEL
    base_url: str = "http://localhost:8000"
    api_key: str = "EMPTY"
    timeout: float = 120.0

    def __post_init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            base_url=_normalize_base_url(self.base_url),
            api_key=self.api_key,
            timeout=self.timeout,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: float = 0.95,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=build_messages(prompt, system_prompt),
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content or ""

    def list_models(self) -> list[str]:
        response = self._client.models.list()
        return [model.id for model in response.data]


class OfflineQwenInference:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        device_map: str = "auto",
        torch_dtype: str = "auto",
        trust_remote_code: bool = True,
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = model
        dtype: Any
        if torch_dtype == "auto":
            dtype = "auto"
        else:
            dtype = getattr(torch, torch_dtype)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model,
            trust_remote_code=trust_remote_code,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model,
            torch_dtype=dtype,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 256,
        temperature: float = 0.2,
        top_p: float = 0.95,
    ) -> str:
        import torch

        messages = build_messages(prompt, system_prompt)
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}

        do_sample = temperature > 0
        generation_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample,
            "top_p": top_p,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if do_sample:
            generation_kwargs["temperature"] = temperature

        with torch.inference_mode():
            output = self.model.generate(**inputs, **generation_kwargs)

        prompt_length = inputs["input_ids"].shape[1]
        new_tokens = output[0][prompt_length:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Qwen inference in offline or online mode")
    parser.add_argument("--mode", choices=["offline", "online"], required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--system-prompt", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--torch-dtype", default="auto")
    args = parser.parse_args()

    if args.mode == "online":
        engine = OnlineQwenInference(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
        )
    else:
        engine = OfflineQwenInference(
            model=args.model,
            device_map=args.device_map,
            torch_dtype=args.torch_dtype,
        )

    output = engine.generate(
        prompt=args.prompt,
        system_prompt=args.system_prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
    )
    print(output)


if __name__ == "__main__":
    main()
