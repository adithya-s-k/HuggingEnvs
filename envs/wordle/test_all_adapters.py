"""
Test ALL adapters with the Wordle environment.

This is the proof that adapters are environment-agnostic:
- Same adapters that work with Jupyter Agent
- Now work with Wordle
- Zero adapter code changes

Run: PYTHONPATH=. python -m pytest environments/wordle/test_all_adapters.py -v
"""

import sys
from pathlib import Path
import inspect
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WORDLE_TOOLKIT = "environments.wordle.verifiers.env.WordleToolkit"


class TestInProcessAdapters:
    """All 3 in-process adapters (Verifiers, SkyRL, GEM) with Wordle."""

    @pytest.fixture(params=[
        "environments.adapters.verifiers_adapter.VerifiersEnvironment",
        "environments.adapters.skyrl_gym_adapter.SkyRLEnvironment",
        "environments.adapters.gem_adapter.GEMEnvironment",
        "environments.adapters.inprocess_adapter.InProcessEnvironment",
    ])
    def adapter(self, request):
        module_path, class_name = request.param.rsplit(".", 1)
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        env = cls(toolkit_cls=WORDLE_TOOLKIT)
        yield env
        env.close()

    def test_discovers_wordle_tools(self, adapter):
        """Should find guess() and get_history(), NOT jupyter tools."""
        methods = [n for n, _ in inspect.getmembers(adapter, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert "guess" in methods
        assert "get_history" in methods
        assert "add_and_execute_code_cell" not in methods

    def test_tool_has_typed_signature(self, adapter):
        """guess(word: str) -> str — proper types for TRL/vLLM."""
        sig = inspect.signature(adapter.guess)
        assert "word" in sig.parameters

    def test_play_and_win(self, adapter):
        """Full game: reset, set answer, guess correctly."""
        adapter.reset(task="Guess the word")
        adapter._toolkit.set_answer("crane")
        result = adapter.guess(word="crane")
        assert "Correct" in result

    def test_multi_turn(self, adapter):
        """Multiple guesses before winning."""
        adapter.reset(task="Guess the word")
        adapter._toolkit.set_answer("apple")
        r1 = adapter.guess(word="crane")
        assert "remaining" in r1.lower() or "⬛" in r1
        r2 = adapter.guess(word="apple")
        assert "Correct" in r2
        assert adapter.step_count == 2

    def test_get_history(self, adapter):
        """History tool works."""
        adapter.reset(task="Guess the word")
        adapter._toolkit.set_answer("beach")
        adapter.guess(word="crane")
        history = adapter.get_history()
        assert "crane" in history
        assert "Guess 1" in history


class TestDataset:
    def test_build(self):
        from environments.wordle.verifiers.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "answer" in ds.column_names
        assert len(ds[0]["answer"]) == 5
