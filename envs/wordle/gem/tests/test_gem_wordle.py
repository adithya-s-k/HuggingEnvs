"""
Tests for Wordle GEM environment.

Tests the native GEM Env subclass (reset/step/close/spawn)
and the adapter integration (GEMEnvironment with WordleToolkit).

Run: PYTHONPATH=. python -m pytest environments/wordle/gem/tests/ -v
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestWordleGemEnv:
    """Test the native GEM Env subclass."""

    def test_reset_returns_instruction(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        obs, info = env.reset()
        assert "Wordle" in obs
        assert "5-letter" in obs
        assert info["answer"] == "apple"

    def test_step_correct_guess(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        obs, reward, terminated, truncated, info = env.step("<guess>apple</guess>")
        assert terminated is True
        assert reward >= 1.0
        assert info["won"] is True
        assert "Correct" in obs

    def test_step_wrong_guess(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        obs, reward, terminated, truncated, info = env.step("<guess>crane</guess>")
        assert terminated is False
        assert reward == 0.0
        assert "remaining" in obs.lower()

    def test_step_parses_raw_word(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        obs, reward, terminated, truncated, info = env.step("I'll try crane")
        assert terminated is False
        assert "🟨" in obs or "⬛" in obs or "🟩" in obs

    def test_multi_turn_game(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        env.step("<guess>crane</guess>")
        env.step("<guess>beach</guess>")
        obs, reward, terminated, truncated, info = env.step("<guess>apple</guess>")
        assert terminated is True
        assert reward >= 1.0
        assert info["step_count"] == 3

    def test_max_turns_truncated(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple", max_turns=2)
        env.reset()
        env.step("<guess>crane</guess>")
        obs, reward, terminated, truncated, info = env.step("<guess>beach</guess>")
        # Game ends on 6th wrong guess (done=True), or truncated at max_turns
        assert terminated or truncated

    def test_no_parse_increments_error(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        obs, reward, terminated, truncated, info = env.step("hmm I am so lost")
        assert info["error_count"] == 1
        assert "Could not parse" in obs

    def test_spawn(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple", max_turns=4)
        env.reset()
        child = env.spawn(same_state=True)
        assert child._answer == "apple"
        assert child._max_turns == 4

    def test_spawn_fresh(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        child = env.spawn(same_state=False)
        assert child._answer == ""

    def test_close(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv(answer="apple")
        env.reset()
        env.close()
        assert env._game is None

    def test_random_answer_from_tasks(self):
        from environments.wordle.gem.env import WordleGemEnv
        env = WordleGemEnv()
        obs, info = env.reset()
        assert len(info["answer"]) == 5

    def test_task_index(self):
        from environments.wordle.gem.env import WordleGemEnv
        from environments.wordle.game import TASKS
        env = WordleGemEnv(task_index=0)
        obs, info = env.reset()
        assert info["answer"] == TASKS[0]["answer"]


class TestGEMAdapter:
    """Test the GEMEnvironment adapter with WordleToolkit."""

    def test_adapter_discovers_tools(self):
        import inspect
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        methods = [n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert "guess" in methods
        assert "get_history" in methods
        env.close()

    def test_adapter_play_game(self):
        from environments.adapters.gem_adapter import GEMEnvironment
        env = GEMEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        env.reset(task="Guess the word")
        env._toolkit.set_answer("tiger")
        result = env.guess(word="tiger")
        assert "Correct" in result
        env.close()


class TestDataset:
    def test_build(self):
        from environments.wordle.gem.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "answer" in ds.column_names
