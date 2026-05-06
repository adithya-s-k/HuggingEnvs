"""
Deterministic tests for the Desktop OpenEnv environment.

Tests the deployed HF Space or a local server via the MCP client.
All tests use the 'terminal' preset (no install step) for speed,
and verify deterministic outputs from shell commands.

Usage:
    # Test against HF Space
    python test_openenv.py

    # Test against local server
    python test_openenv.py --url http://localhost:8000

    # Verbose output
    python test_openenv.py -v
"""

import argparse
import base64
import sys
import time

# Load .env for E2B_API_KEY (needed by the server, not the client)
import os
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

from openenv.core.mcp_client import MCPToolClient


HF_SPACE_URL = "https://adithyask-desktop-openenv.hf.space"

# ── Test results tracking ──

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name, detail=""):
        self.passed += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))

    def fail(self, name, reason):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  FAIL  {name}  -- {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        print(f"{'='*60}")
        return self.failed == 0


# ── Individual tests ──

def test_health(base_url, results):
    """Server responds to health check."""
    import requests
    try:
        r = requests.get(f"{base_url}/health", timeout=10)
        if r.status_code == 200:
            results.ok("health_check", f"status={r.status_code}")
        else:
            results.fail("health_check", f"status={r.status_code}")
    except Exception as e:
        results.fail("health_check", str(e))


def test_reset_terminal(env, results):
    """Reset with 'terminal' preset succeeds and returns expected metadata."""
    try:
        obs = env.reset(app="terminal")
        # obs is a StepResult; obs.observation may be Observation, dict, or nested
        raw = obs.observation
        meta = {}
        if hasattr(raw, "metadata"):
            meta = raw.metadata or {}
        elif isinstance(raw, dict):
            meta = raw.get("metadata", raw)
        # Some versions nest it as obs.observation.observation
        if not meta and hasattr(raw, "observation"):
            inner = raw.observation
            if hasattr(inner, "metadata"):
                meta = inner.metadata or {}
            elif isinstance(inner, dict):
                meta = inner.get("metadata", inner)
        # Try __dict__ as last resort
        if not meta and hasattr(raw, "__dict__"):
            for v in raw.__dict__.values():
                if isinstance(v, dict) and "sandbox_id" in v:
                    meta = v
                    break

        # Verify reset succeeded — observation should not be done
        done = getattr(raw, "done", None)
        if done is False:
            results.ok("reset_not_done", "done=False")
        else:
            results.fail("reset_not_done", f"expected done=False, got {done}")

        # If metadata is available, check it (may be empty over WebSocket)
        if meta:
            sandbox_id = meta.get("sandbox_id")
            status = meta.get("status")
            if status == "ready":
                results.ok("reset_status", f"status={status}")
            if sandbox_id:
                results.ok("reset_sandbox_id", f"id={sandbox_id[:20]}")
        else:
            # Metadata not serialized over WebSocket — verify via a tool call
            result = env.call_tool("get_screen_size")
            if "1920" in str(result):
                results.ok("reset_verified", "sandbox alive (screen_size works)")
            else:
                results.fail("reset_verified", f"sandbox not responding: {result}")

    except Exception as e:
        results.fail("reset_terminal", str(e))


def test_list_tools(env, results):
    """All expected tools are registered."""
    expected_tools = {
        "screenshot", "click", "double_click", "right_click",
        "type_text", "press_key", "scroll", "drag",
        "run_command", "get_cursor_position", "get_screen_size",
    }
    try:
        tools = env.list_tools()
        tool_names = {t.name for t in tools}

        missing = expected_tools - tool_names
        if not missing:
            results.ok("list_tools", f"{len(tool_names)} tools found")
        else:
            results.fail("list_tools", f"missing: {missing}")

        # Each tool should have a description
        for t in tools:
            if not t.description:
                results.fail(f"tool_desc_{t.name}", "no description")
                return
        results.ok("tool_descriptions", "all tools have descriptions")

    except Exception as e:
        results.fail("list_tools", str(e))


def test_run_command_echo(env, results):
    """run_command with 'echo' produces deterministic output."""
    try:
        result = env.call_tool("run_command", command="echo hello_desktop_env")
        if "hello_desktop_env" in str(result):
            results.ok("run_command_echo", f"output contains expected string")
        else:
            results.fail("run_command_echo", f"unexpected output: {str(result)[:100]}")
    except Exception as e:
        results.fail("run_command_echo", str(e))


def test_run_command_math(env, results):
    """run_command with arithmetic produces correct result."""
    try:
        result = env.call_tool("run_command", command="python3 -c \"print(6 * 7)\"")
        if "42" in str(result):
            results.ok("run_command_math", "6*7=42 confirmed")
        else:
            results.fail("run_command_math", f"expected '42', got: {str(result)[:100]}")
    except Exception as e:
        results.fail("run_command_math", str(e))


def test_run_command_env(env, results):
    """run_command can read environment variables."""
    try:
        result = env.call_tool("run_command", command="echo $HOME")
        output = str(result).strip()
        if output and "/" in output:
            results.ok("run_command_env", f"HOME={output[:50]}")
        else:
            results.fail("run_command_env", f"unexpected HOME: {output[:100]}")
    except Exception as e:
        results.fail("run_command_env", str(e))


def test_run_command_file_write_read(env, results):
    """Write a file and read it back — deterministic round-trip."""
    try:
        env.call_tool("run_command", command="echo 'openenv_test_12345' > /tmp/test_file.txt")
        result = env.call_tool("run_command", command="cat /tmp/test_file.txt")
        if "openenv_test_12345" in str(result):
            results.ok("file_write_read", "round-trip verified")
        else:
            results.fail("file_write_read", f"readback mismatch: {str(result)[:100]}")
    except Exception as e:
        results.fail("file_write_read", str(e))


def test_screenshot(env, results):
    """Screenshot returns valid base64 PNG data."""
    try:
        result = env.call_tool("screenshot")
        result_str = str(result)

        # Should be base64 encoded
        if len(result_str) < 100:
            results.fail("screenshot_size", f"too small: {len(result_str)} chars")
            return
        results.ok("screenshot_size", f"{len(result_str)} chars")

        # Should be valid base64 that decodes to PNG
        try:
            raw = base64.b64decode(result_str)
            # PNG magic bytes
            if raw[:4] == b'\x89PNG':
                results.ok("screenshot_png", "valid PNG header")
            else:
                results.fail("screenshot_png", f"not PNG, starts with {raw[:4]}")
        except Exception as e:
            results.fail("screenshot_png", f"base64 decode failed: {e}")

    except Exception as e:
        results.fail("screenshot", str(e))


def test_get_screen_size(env, results):
    """get_screen_size returns valid dimensions."""
    try:
        result = env.call_tool("get_screen_size")
        result_str = str(result)
        if "1920" in result_str and "1080" in result_str:
            results.ok("screen_size", result_str.strip())
        elif "x" in result_str.lower() or "size" in result_str.lower():
            results.ok("screen_size", f"got dimensions: {result_str.strip()}")
        else:
            results.fail("screen_size", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("screen_size", str(e))


def test_get_cursor_position(env, results):
    """get_cursor_position returns valid coordinates."""
    try:
        result = env.call_tool("get_cursor_position")
        result_str = str(result)
        # Should contain numbers
        import re
        numbers = re.findall(r'\d+', result_str)
        if len(numbers) >= 2:
            results.ok("cursor_position", result_str.strip())
        else:
            results.fail("cursor_position", f"no coordinates found: {result_str[:100]}")
    except Exception as e:
        results.fail("cursor_position", str(e))


def test_click(env, results):
    """Click at coordinates succeeds."""
    try:
        result = env.call_tool("click", x=100, y=100)
        result_str = str(result).lower()
        if "click" in result_str or "100" in result_str:
            results.ok("click", result_str.strip()[:80])
        else:
            results.fail("click", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("click", str(e))


def test_double_click(env, results):
    """Double click at coordinates succeeds."""
    try:
        result = env.call_tool("double_click", x=200, y=200)
        result_str = str(result).lower()
        if "click" in result_str or "200" in result_str:
            results.ok("double_click", result_str.strip()[:80])
        else:
            results.fail("double_click", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("double_click", str(e))


def test_right_click(env, results):
    """Right click at coordinates succeeds."""
    try:
        result = env.call_tool("right_click", x=300, y=300)
        result_str = str(result).lower()
        if "click" in result_str or "300" in result_str:
            results.ok("right_click", result_str.strip()[:80])
        else:
            results.fail("right_click", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("right_click", str(e))


def test_type_text(env, results):
    """Type text succeeds."""
    try:
        result = env.call_tool("type_text", text="hello")
        result_str = str(result).lower()
        if "hello" in result_str or "type" in result_str:
            results.ok("type_text", result_str.strip()[:80])
        else:
            results.fail("type_text", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("type_text", str(e))


def test_press_key(env, results):
    """Press key succeeds."""
    try:
        result = env.call_tool("press_key", key="escape")
        result_str = str(result).lower()
        if "escape" in result_str or "press" in result_str:
            results.ok("press_key", result_str.strip()[:80])
        else:
            results.fail("press_key", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("press_key", str(e))


def test_press_key_combo(env, results):
    """Press key combo (ctrl+a) succeeds."""
    try:
        result = env.call_tool("press_key", key="ctrl+a")
        result_str = str(result).lower()
        if "ctrl" in result_str or "press" in result_str:
            results.ok("press_key_combo", result_str.strip()[:80])
        else:
            results.fail("press_key_combo", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("press_key_combo", str(e))


def test_scroll(env, results):
    """Scroll succeeds."""
    try:
        result = env.call_tool("scroll", direction="down", amount=3)
        result_str = str(result).lower()
        if "scroll" in result_str or "down" in result_str:
            results.ok("scroll", result_str.strip()[:80])
        else:
            results.fail("scroll", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("scroll", str(e))


def test_drag(env, results):
    """Drag succeeds."""
    try:
        result = env.call_tool("drag", start_x=100, start_y=100, end_x=300, end_y=300)
        result_str = str(result).lower()
        if "drag" in result_str or "300" in result_str:
            results.ok("drag", result_str.strip()[:80])
        else:
            results.fail("drag", f"unexpected: {result_str[:100]}")
    except Exception as e:
        results.fail("drag", str(e))


def test_deterministic_sequence(env, results):
    """Run a deterministic sequence: write file, read file, verify content matches."""
    try:
        # Write a specific file with known content
        env.call_tool("run_command", command="echo -n 'line1\nline2\nline3' > /tmp/seq_test.txt")

        # Count lines
        result = env.call_tool("run_command", command="wc -l < /tmp/seq_test.txt")
        line_count = str(result).strip()
        if "2" in line_count or "3" in line_count:
            results.ok("seq_line_count", f"wc -l = {line_count}")
        else:
            results.fail("seq_line_count", f"expected 2-3, got: {line_count}")

        # Compute md5
        result = env.call_tool("run_command", command="md5sum /tmp/seq_test.txt | cut -d' ' -f1")
        md5 = str(result).strip()
        if len(md5) == 32:
            results.ok("seq_md5", f"md5={md5}")
        else:
            results.fail("seq_md5", f"invalid md5: {md5}")

        # Verify content
        result = env.call_tool("run_command", command="head -1 /tmp/seq_test.txt")
        first_line = str(result).strip()
        if "line1" in first_line:
            results.ok("seq_content", "first line matches")
        else:
            results.fail("seq_content", f"expected 'line1', got: {first_line}")

    except Exception as e:
        results.fail("deterministic_sequence", str(e))


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Test Desktop OpenEnv environment")
    parser.add_argument("--url", default=HF_SPACE_URL,
                        help=f"Server URL (default: {HF_SPACE_URL})")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    print(f"Testing Desktop OpenEnv at: {args.url}")
    print("=" * 60)

    results = TestResult()

    # Connect
    try:
        env = MCPToolClient(base_url=args.url).sync()
    except Exception as e:
        print(f"\nFATAL: Cannot connect to {args.url}: {e}")
        sys.exit(1)

    try:
        # 1. Health check
        print("\n[1/7] Health check")
        test_health(args.url, results)

        # 2. Reset
        print("\n[2/7] Reset (terminal)")
        test_reset_terminal(env, results)

        # 3. Tool discovery
        print("\n[3/7] Tool discovery")
        test_list_tools(env, results)

        # 4. Shell commands (deterministic)
        print("\n[4/7] Shell commands")
        test_run_command_echo(env, results)
        test_run_command_math(env, results)
        test_run_command_env(env, results)
        test_run_command_file_write_read(env, results)

        # 5. Screenshot & screen info
        print("\n[5/7] Screenshot & screen info")
        test_screenshot(env, results)
        test_get_screen_size(env, results)
        test_get_cursor_position(env, results)

        # 6. Input actions
        print("\n[6/7] Input actions")
        test_click(env, results)
        test_double_click(env, results)
        test_right_click(env, results)
        test_type_text(env, results)
        test_press_key(env, results)
        test_press_key_combo(env, results)
        test_scroll(env, results)
        test_drag(env, results)

        # 7. Deterministic sequence
        print("\n[7/7] Deterministic sequence")
        test_deterministic_sequence(env, results)

    finally:
        env.close()

    ok = results.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
