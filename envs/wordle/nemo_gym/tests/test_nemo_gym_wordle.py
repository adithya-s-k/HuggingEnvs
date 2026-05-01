"""
Tests for Wordle NeMo Gym environment.

Tests are split into:
1. Dataset tests — no server needed
2. Server tests — require running NeMo Gym server (set NEMO_GYM_URL)

Usage:
    # Dataset only:
    PYTHONPATH=. pytest environments/wordle/nemo_gym/tests/ -v -k "dataset"

    # With server:
    NEMO_GYM_URL=http://localhost:11000 pytest environments/wordle/nemo_gym/tests/ -v
"""

import os
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

NEMO_GYM_URL = os.getenv("NEMO_GYM_URL", "")
requires_server = pytest.mark.skipif(
    not NEMO_GYM_URL,
    reason="NEMO_GYM_URL not set — start server to run these tests"
)


class TestDataset:
    """Test dataset building (no server needed)."""

    def test_build_dataset(self):
        from environments.wordle.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "metadata" in ds.column_names
        assert "answer" in ds.column_names

    def test_dataset_has_correct_format(self):
        from environments.wordle.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=2, max_tasks=2)
        assert len(ds) == 4
        row = ds[0]
        assert isinstance(row["prompt"], list)
        assert row["prompt"][0]["role"] == "system"

    def test_dataset_metadata_is_valid_nemo_gym_json(self):
        from environments.wordle.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=1)
        meta = json.loads(ds[0]["metadata"])
        assert "responses_create_params" in meta
        assert "ground_truth" in meta
        assert "tools" in meta["responses_create_params"]
        tool_names = [t["name"] for t in meta["responses_create_params"]["tools"]]
        assert "guess" in tool_names
        assert "get_history" in tool_names


@requires_server
class TestNemoGymServer:
    """Test the NeMo Gym server (requires running server)."""

    def test_openapi_routes(self):
        import requests
        resp = requests.get(f"{NEMO_GYM_URL}/openapi.json")
        assert resp.status_code == 200
        paths = list(resp.json()["paths"].keys())
        assert "/seed_session" in paths
        assert "/verify" in paths
        assert "/guess" in paths
        assert "/get_history" in paths

    def test_seed_session(self):
        import requests
        session = requests.Session()
        resp = session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        assert resp.status_code == 200

    def test_guess(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(
            f"{NEMO_GYM_URL}/guess",
            json={"word": "crane"}
        )
        assert resp.status_code == 200
        output = resp.json()["output"]
        assert "🟩" in output or "🟨" in output or "⬛" in output

    def test_get_history(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        session.post(f"{NEMO_GYM_URL}/guess", json={"word": "crane"})
        resp = session.post(f"{NEMO_GYM_URL}/get_history", json={})
        assert resp.status_code == 200
        assert "crane" in resp.json()["output"]

    def test_verify_correct(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(f"{NEMO_GYM_URL}/verify", json={
            "responses_create_params": {"input": []},
            "response": {
                "id": "t", "object": "response", "created_at": 0, "model": "t",
                "output": [{"type": "function_call_output", "call_id": "c1",
                            "output": "🟩🟩🟩🟩🟩 — Correct! The word was 'apple'. Solved in 1 guesses."}],
                "tool_choice": "auto", "tools": [], "parallel_tool_calls": False,
            },
            "ground_truth": [],
        })
        assert resp.status_code == 200
        assert resp.json()["reward"] == 1.0
