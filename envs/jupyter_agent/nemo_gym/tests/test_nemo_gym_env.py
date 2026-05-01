"""Tests for the Jupyter Agent NeMo Gym environment.

Tests are split into:
1. Dataset tests — no server or nemo_gym needed
2. Server tests — require running NeMo Gym Resources Server (set NEMO_GYM_URL)
3. Adapter tests — require running server

Usage:
    # Dataset only (no server):
    PYTHONPATH=. pytest tests/ -v -k "dataset"

    # With HF Space:
    NEMO_GYM_URL=https://AdithyaSK-jupyter-agent-nemo-gym.hf.space pytest tests/ -v

    # With local server:
    NEMO_GYM_URL=http://localhost:11000 pytest tests/ -v
"""

import os
import json
import pytest

NEMO_GYM_URL = os.getenv(
    "NEMO_GYM_URL",
    "https://AdithyaSK-jupyter-agent-nemo-gym.hf.space",
)
requires_server = pytest.mark.skipif(
    not NEMO_GYM_URL,
    reason="NEMO_GYM_URL not set — start server to run these tests"
)


class TestDataset:
    """Test dataset building (no server needed)."""

    def test_build_dataset(self):
        from environments.jupyter_agent.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "prompt" in ds.column_names
        assert "metadata" in ds.column_names
        assert "expected_output" in ds.column_names

    def test_dataset_has_correct_format(self):
        from environments.jupyter_agent.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=2, max_tasks=2)
        assert len(ds) == 4  # 2 tasks * 2 repeats
        row = ds[0]
        assert isinstance(row["prompt"], list)
        assert row["prompt"][0]["role"] == "system"

    def test_dataset_metadata_is_valid_nemo_gym_json(self):
        from environments.jupyter_agent.nemo_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=1)
        meta = json.loads(ds[0]["metadata"])
        assert "responses_create_params" in meta
        assert "ground_truth" in meta
        assert "tools" in meta["responses_create_params"]
        assert len(meta["responses_create_params"]["tools"]) == 4
        tool_names = [t["name"] for t in meta["responses_create_params"]["tools"]]
        assert "add_and_execute_code_cell" in tool_names
        assert "execute_shell_command" in tool_names

    def test_tasks_list(self):
        from environments.jupyter_agent.nemo_gym.tasks import TASKS
        assert len(TASKS) == 46
        for task in TASKS:
            assert "task" in task
            assert "expected_output" in task


@requires_server
class TestNemoGymServer:
    """Test the NeMo Gym Resources Server (requires running server)."""

    def test_openapi_routes(self):
        import requests
        resp = requests.get(f"{NEMO_GYM_URL}/openapi.json")
        assert resp.status_code == 200
        paths = list(resp.json()["paths"].keys())
        assert "/seed_session" in paths
        assert "/verify" in paths
        assert "/add_and_execute_code_cell" in paths
        assert "/execute_shell_command" in paths
        assert "/get_notebook_state" in paths

    def test_seed_session(self):
        import requests
        session = requests.Session()
        resp = session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_execute_code(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(
            f"{NEMO_GYM_URL}/add_and_execute_code_cell",
            json={"code": "print(2**20)"}
        )
        assert resp.status_code == 200
        assert "1048576" in resp.json()["output"]

    def test_state_persists_across_cells(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        session.post(
            f"{NEMO_GYM_URL}/add_and_execute_code_cell",
            json={"code": "my_var = 123"}
        )
        resp = session.post(
            f"{NEMO_GYM_URL}/add_and_execute_code_cell",
            json={"code": "print(my_var + 1)"}
        )
        assert "124" in resp.json()["output"]

    def test_shell_command(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(
            f"{NEMO_GYM_URL}/execute_shell_command",
            json={"command": "echo hello_nemo"}
        )
        assert resp.status_code == 200
        assert "hello_nemo" in resp.json()["output"]

    def test_edit_cell(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        session.post(
            f"{NEMO_GYM_URL}/add_and_execute_code_cell",
            json={"code": "print('first')"}
        )
        resp = session.post(
            f"{NEMO_GYM_URL}/edit_and_execute_current_cell",
            json={"code": "print('second')"}
        )
        assert "second" in resp.json()["output"]

    def test_notebook_state(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        session.post(
            f"{NEMO_GYM_URL}/add_and_execute_code_cell",
            json={"code": "x = 42"}
        )
        resp = session.post(
            f"{NEMO_GYM_URL}/get_notebook_state",
            json={"include_images": False}
        )
        assert resp.status_code == 200
        assert "42" in resp.json()["output"]

    def test_verify_correct_answer(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(f"{NEMO_GYM_URL}/verify", json={
            "responses_create_params": {"input": []},
            "response": {
                "id": "t", "object": "response", "created_at": 0, "model": "t",
                "output": [{"type": "function_call_output", "call_id": "c1", "output": "3628800"}],
                "tool_choice": "auto", "tools": [], "parallel_tool_calls": False,
            },
            "ground_truth": [{"expected_output": "3628800"}],
        })
        assert resp.status_code == 200
        assert resp.json()["reward"] == 1.0

    def test_verify_wrong_answer(self):
        import requests
        session = requests.Session()
        session.post(f"{NEMO_GYM_URL}/seed_session", json={})
        resp = session.post(f"{NEMO_GYM_URL}/verify", json={
            "responses_create_params": {"input": []},
            "response": {
                "id": "t", "object": "response", "created_at": 0, "model": "t",
                "output": [{"type": "function_call_output", "call_id": "c1", "output": "wrong"}],
                "tool_choice": "auto", "tools": [], "parallel_tool_calls": False,
            },
            "ground_truth": [{"expected_output": "3628800"}],
        })
        assert resp.status_code == 200
        assert resp.json()["reward"] == 0.0


@requires_server
class TestNemoGymAdapter:
    """Test the TRL adapter against a running server."""

    def test_adapter_init_and_tools(self):
        import inspect
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        methods = [
            n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
            if not n.startswith("_") and n not in ("reset", "close", "verify")
        ]
        assert sorted(methods) == [
            "add_and_execute_code_cell",
            "edit_and_execute_current_cell",
            "execute_shell_command",
            "get_notebook_state",
        ]
        # Check signatures have proper types (not **kwargs)
        sig = inspect.signature(env.add_and_execute_code_cell)
        assert "code" in sig.parameters
        assert sig.parameters["code"].annotation is str
        env.close()

    def test_adapter_reset(self):
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        obs = env.reset(task="Print 42")
        assert obs is not None
        assert "Print 42" in obs
        assert env.reward == 0.0
        assert env.step_count == 0
        env.close()

    def test_adapter_tool_call(self):
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        env.reset(task="test", task_spec={"ground_truth": [{"expected_output": "42"}]})
        result = env.add_and_execute_code_cell(code="print(42)")
        assert "42" in result
        assert env.step_count == 1
        assert env.last_output == result
        env.close()

    def test_adapter_verify_reward(self):
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        env.reset(
            task="Calculate factorial of 10",
            task_spec={"ground_truth": [{"expected_output": "3628800"}]},
        )
        env.add_and_execute_code_cell(code="import math; print(math.factorial(10))")
        env.verify()
        assert env.reward == 1.0
        env.close()

    def test_adapter_multi_turn(self):
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        env.reset(
            task="Install sympy and count primes 900-1000",
            task_spec={"ground_truth": [{"expected_output": "14"}]},
        )
        env.execute_shell_command(command="pip install sympy -q")
        result = env.add_and_execute_code_cell(
            code="from sympy import isprime; print(sum(1 for n in range(900,1001) if isprime(n)))"
        )
        assert "14" in result
        assert env.step_count == 2
        env.verify()
        assert env.reward == 1.0
        env.close()

    def test_adapter_as_environment_factory(self):
        """Simulate TRL: environment_factory(**environment_config)"""
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        config = {"resources_url": NEMO_GYM_URL}
        env = NemoGymEnvironment(**config)
        obs = env.reset(
            task="Sum 1 to 100",
            task_spec={"ground_truth": [{"expected_output": "5050"}]},
        )
        assert obs is not None
        result = env.add_and_execute_code_cell(code="print(sum(range(1,101)))")
        assert "5050" in result
        env.verify()
        assert env.reward == 1.0
        env.close()

    def test_adapter_wrong_answer_zero_reward(self):
        from environments.adapters.nemo_gym_adapter import NemoGymEnvironment
        env = NemoGymEnvironment(resources_url=NEMO_GYM_URL)
        env.reset(
            task="Print 42",
            task_spec={"ground_truth": [{"expected_output": "42"}]},
        )
        env.add_and_execute_code_cell(code="print('wrong')")
        env.verify()
        assert env.reward == 0.0
        env.close()
