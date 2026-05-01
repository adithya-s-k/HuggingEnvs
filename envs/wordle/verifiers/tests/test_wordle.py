"""
Tests for Wordle environment + adapter.

The key test: the EXISTING VerifiersEnvironment adapter (built for Jupyter Agent)
works with a completely different environment (Wordle) with ZERO adapter changes.
Just swap the toolkit_cls.
"""

import sys
from pathlib import Path
import pytest

# Ensure imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestWordleGame:
    """Test core game logic."""

    def test_correct_guess(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        result = game.guess("apple")
        assert "Correct" in result
        assert game.won is True
        assert game.reward >= 1.0

    def test_feedback_green(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        result = game.guess("apple")
        assert "🟩🟩🟩🟩🟩" in result

    def test_feedback_yellow(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        result = game.guess("plead")
        # p is in apple but wrong position → 🟨
        # l is in apple but wrong position → 🟨
        # e is in apple but wrong position → 🟨
        # a is in apple but wrong position → 🟨
        assert "🟨" in result

    def test_feedback_grey(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        result = game.guess("world")
        assert "⬛" in result

    def test_max_guesses(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple", max_guesses=2)
        game.guess("beach")
        result = game.guess("chair")
        assert "Game over" in result
        assert game.done is True
        assert game.won is False

    def test_invalid_length(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        result = game.guess("hi")
        assert "Invalid" in result

    def test_history(self):
        from environments.wordle.game import WordleGame
        game = WordleGame(answer="apple")
        game.guess("beach")
        game.guess("crane")
        history = game.get_history()
        assert "Guess 1:" in history
        assert "Guess 2:" in history
        assert "beach" in history

    def test_reward_scales_with_efficiency(self):
        from environments.wordle.game import WordleGame
        game1 = WordleGame(answer="apple")
        game1.guess("apple")  # 1 guess
        game2 = WordleGame(answer="apple")
        game2.guess("beach")
        game2.guess("crane")
        game2.guess("apple")  # 3 guesses
        assert game1.reward > game2.reward  # Faster = higher reward


class TestWordleToolkit:
    """Test the toolkit (what the adapter discovers)."""

    def test_toolkit_has_correct_tools(self):
        import inspect
        from environments.wordle.verifiers.env import WordleToolkit
        tk = WordleToolkit()
        methods = [n for n, _ in inspect.getmembers(tk, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "cleanup", "set_answer")]
        assert sorted(methods) == ["get_history", "guess"]

    def test_toolkit_guess(self):
        from environments.wordle.verifiers.env import WordleToolkit
        tk = WordleToolkit()
        tk.set_answer("apple")
        result = tk.guess("apple")
        assert "Correct" in result
        assert tk.step_count == 1

    def test_toolkit_reset(self):
        from environments.wordle.verifiers.env import WordleToolkit
        tk = WordleToolkit()
        tk.set_answer("apple")
        tk.guess("beach")
        tk.reset()
        assert tk.step_count == 0


class TestAdapterWithWordle:
    """THE KEY TEST: existing adapter works with Wordle, zero changes."""

    def test_adapter_discovers_wordle_tools(self):
        """InProcessEnvironment should find guess() and get_history()."""
        import inspect
        from environments.adapters.inprocess_adapter import InProcessEnvironment

        env = InProcessEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
            prompt_template="Play Wordle! {task}",
        )
        methods = [n for n, _ in inspect.getmembers(env, predicate=inspect.ismethod)
                   if not n.startswith("_") and n not in ("reset", "close")]
        assert "guess" in methods
        assert "get_history" in methods
        # Should NOT have jupyter tools
        assert "add_and_execute_code_cell" not in methods
        env.close()

    def test_adapter_tool_signatures(self):
        """Tools should have proper typed signatures for TRL/vLLM."""
        import inspect
        from environments.adapters.inprocess_adapter import InProcessEnvironment

        env = InProcessEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        sig = inspect.signature(env.guess)
        assert "word" in sig.parameters
        env.close()

    def test_adapter_play_game(self):
        """Full game through the adapter."""
        from environments.adapters.inprocess_adapter import InProcessEnvironment

        env = InProcessEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        obs = env.reset(task="Guess the word", answer="apple")

        # Set the answer on the toolkit
        env._toolkit.set_answer("apple")

        result = env.guess(word="beach")
        assert "remaining" in result.lower() or "⬛" in result or "🟨" in result
        assert env.step_count == 1

        result = env.guess(word="apple")
        assert "Correct" in result
        env.close()

    def test_verifiers_adapter_alias(self):
        """VerifiersEnvironment with Wordle toolkit — proving it's generic."""
        from environments.adapters.verifiers_adapter import VerifiersEnvironment

        env = VerifiersEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        env.reset(task="Guess the word")
        env._toolkit.set_answer("grape")
        result = env.guess(word="grape")
        assert "Correct" in result
        env.close()

    def test_skyrl_adapter_alias(self):
        """SkyRLEnvironment with Wordle toolkit — same adapter, different name."""
        from environments.adapters.skyrl_gym_adapter import SkyRLEnvironment

        env = SkyRLEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        env.reset(task="Guess the word")
        env._toolkit.set_answer("house")
        result = env.guess(word="house")
        assert "Correct" in result
        env.close()

    def test_gem_adapter_alias(self):
        """GEMEnvironment with Wordle toolkit — same adapter, different name."""
        from environments.adapters.gem_adapter import GEMEnvironment

        env = GEMEnvironment(
            toolkit_cls="environments.wordle.verifiers.env.WordleToolkit",
        )
        env.reset(task="Guess the word")
        env._toolkit.set_answer("tiger")
        result = env.guess(word="tiger")
        assert "Correct" in result
        env.close()

    def test_dataset(self):
        from environments.wordle.verifiers.dataset import build_dataset
        ds = build_dataset(num_repeats=1, max_tasks=5)
        assert len(ds) == 5
        assert "answer" in ds.column_names
        assert "prompt" in ds.column_names
