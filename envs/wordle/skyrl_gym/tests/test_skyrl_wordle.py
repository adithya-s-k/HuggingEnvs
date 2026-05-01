"""
Tests for Wordle SkyRL Gym environment.

Tests the native SkyRL BaseTextEnv subclass (init/step/close)
and the adapter integration (SkyRLEnvironment with WordleToolkit).

Run: PYTHONPATH=. python -m pytest environments/wordle/skyrl_gym/tests/ -v
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestWordleSkyRLEnv:
    """Test the native SkyRL BaseTextEnv subclass."""

    def test_init_creates_game(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        prompt = [{"role": "user", "content": "Guess the word"}]
        obs, info = env.init(prompt)
        assert obs == prompt
        assert info["max_turns"] == 6
        assert info["answer"] == "apple"

    def test_step_correct_guess(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        result = env.step("<guess>apple</guess>")
        assert result.done is True
        assert result.reward >= 1.0
        assert result.metadata["won"] is True
        assert "Correct" in result.observations[0]["content"]

    def test_step_wrong_guess(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        result = env.step("<guess>crane</guess>")
        assert result.done is False
        assert result.reward == 0.0
        assert "remaining" in result.observations[0]["content"].lower()

    def test_step_parses_raw_word(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        result = env.step("I think the word is crane")
        assert result.done is False
        assert "🟨" in result.observations[0]["content"] or "⬛" in result.observations[0]["content"]

    def test_step_parses_guess_prefix(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        result = env.step("guess: crane")
        assert result.done is False

    def test_multi_turn_game(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        env.step("<guess>crane</guess>")
        env.step("<guess>beach</guess>")
        result = env.step("<guess>apple</guess>")
        assert result.done is True
        assert result.reward >= 1.0
        assert result.metadata["turns"] == 3

    def test_max_turns(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple", max_turns=2)
        env.init([{"role": "user", "content": "Guess"}])
        env.step("<guess>crane</guess>")
        result = env.step("<guess>beach</guess>")
        assert result.done is True
        assert result.metadata["won"] is False

    def test_no_parse_increments_error(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        result = env.step("I am so lost, no idea")
        assert env.error_count == 1
        assert "Could not parse" in result.observations[0]["content"]

    def test_close(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv(answer="apple")
        env.init([{"role": "user", "content": "Guess"}])
        env.close()
        assert env._game is None

    def test_random_answer_when_not_provided(self):
        from environments.wordle.skyrl_gym.env import WordleSkyRLEnv
        env = WordleSkyRLEnv()
        _, info = env.init([{"role": "user", "content": "Guess"}])
        assert len(info["answer"]) == 5


class TestSkyRLAdapter:
    """Test the SkyRLEnvironment adapter with WordleToolkit."""

    def test_adapter_discovers_tools(self):
        import inspect
        from environments.adapters.skyrl_gym_adapter import SkyRLEnvironment
        env = SkyRLEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        methods = [n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert "guess" in methods
        assert "get_history" in methods
        env.close()

    def test_adapter_play_game(self):
        from environments.adapters.skyrl_gym_adapter import SkyRLEnvironment
        env = SkyRLEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        env.reset(task="Guess the word")
        env._toolkit.set_answer("crane")
        result = env.guess(word="crane")
        assert "Correct" in result
        env.close()


class TestDataset:
    def test_build(self):
        from environments.wordle.skyrl_gym.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=3)
        assert len(ds) == 3
        assert "answer" in ds.column_names
