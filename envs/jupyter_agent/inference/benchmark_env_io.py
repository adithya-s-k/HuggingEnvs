"""Benchmark I/O throughput of the Jupyter Agent OpenEnv server.

Tests:
1. Single-client latency (reset, tool calls, state query)
2. Sequential multi-turn episode
3. Concurrent client throughput (simulates parallel rollouts)
"""

import statistics
import time
import concurrent.futures

ENV_URL = "https://AdithyaSK-jupyter-agent-openenv.hf.space"


def get_client():
    from jupyter_agent_env import JupyterAgentEnv
    client = JupyterAgentEnv(base_url=ENV_URL).sync()
    client.__enter__()
    return client


def extract_text(result):
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", str(result))
        res = result.get("result", "")
        if isinstance(res, dict):
            content = res.get("content", [])
            if isinstance(content, list) and content:
                return content[0].get("text", str(res))
            return res.get("data", str(res))
        return str(res)
    return str(result)


def benchmark_single_client():
    """Measure individual operation latencies."""
    print("=" * 60)
    print("SINGLE CLIENT LATENCY TEST")
    print("=" * 60)

    client = get_client()

    # --- Reset latency ---
    reset_times = []
    for i in range(3):
        t0 = time.time()
        client.reset()
        elapsed = time.time() - t0
        reset_times.append(elapsed)
        print(f"  Reset {i+1}: {elapsed:.2f}s")

    print(f"  Reset avg: {statistics.mean(reset_times):.2f}s, "
          f"min: {min(reset_times):.2f}s, max: {max(reset_times):.2f}s\n")

    # --- Simple code execution ---
    client.reset()
    code_times = []
    test_codes = [
        "print(2 + 2)",
        "import numpy as np; print(np.mean([1,2,3,4,5]))",
        "x = sum(range(1000)); print(x)",
        "import pandas as pd; df = pd.DataFrame({'a': [1,2,3]}); print(df.shape)",
        "print('hello world')",
    ]
    for i, code in enumerate(test_codes):
        t0 = time.time()
        result = client.call_tool("add_and_execute_code_cell", code=code)
        elapsed = time.time() - t0
        text = extract_text(result)
        code_times.append(elapsed)
        print(f"  Code exec {i+1}: {elapsed:.2f}s → {text[:50].strip()}")

    print(f"  Code exec avg: {statistics.mean(code_times):.2f}s, "
          f"min: {min(code_times):.2f}s, max: {max(code_times):.2f}s\n")

    # --- Shell command ---
    shell_times = []
    shell_cmds = ["echo hello", "python --version", "pip list | head -5"]
    for i, cmd in enumerate(shell_cmds):
        t0 = time.time()
        result = client.call_tool("execute_shell_command", command=cmd)
        elapsed = time.time() - t0
        text = extract_text(result)
        shell_times.append(elapsed)
        print(f"  Shell {i+1}: {elapsed:.2f}s → {text[:50].strip()}")

    print(f"  Shell avg: {statistics.mean(shell_times):.2f}s\n")

    # --- Get state ---
    state_times = []
    for i in range(3):
        t0 = time.time()
        result = client.call_tool("get_notebook_state")
        elapsed = time.time() - t0
        state_times.append(elapsed)
        print(f"  Get state {i+1}: {elapsed:.2f}s")

    print(f"  Get state avg: {statistics.mean(state_times):.2f}s\n")

    client.__exit__(None, None, None)
    return {
        "reset_avg": statistics.mean(reset_times),
        "code_exec_avg": statistics.mean(code_times),
        "shell_avg": statistics.mean(shell_times),
        "state_avg": statistics.mean(state_times),
    }


def benchmark_full_episode():
    """Measure a complete multi-turn episode (like training)."""
    print("=" * 60)
    print("FULL EPISODE TEST (reset → 3 tool calls → done)")
    print("=" * 60)

    client = get_client()
    episode_times = []

    for ep in range(3):
        t0 = time.time()
        client.reset()
        t_reset = time.time() - t0

        t1 = time.time()
        r1 = client.call_tool("add_and_execute_code_cell", code="primes = [p for p in range(2, 50) if all(p%i!=0 for i in range(2,p))]; print(sum(primes))")
        t_call1 = time.time() - t1

        t2 = time.time()
        r2 = client.call_tool("add_and_execute_code_cell", code="print('done')")
        t_call2 = time.time() - t2

        total = time.time() - t0
        episode_times.append(total)
        print(f"  Episode {ep+1}: reset={t_reset:.2f}s, call1={t_call1:.2f}s, call2={t_call2:.2f}s, total={total:.2f}s")

    print(f"  Episode avg: {statistics.mean(episode_times):.2f}s\n")
    client.__exit__(None, None, None)
    return statistics.mean(episode_times)


def benchmark_concurrent(num_clients=4):
    """Measure throughput with concurrent clients (simulates parallel rollouts)."""
    print("=" * 60)
    print(f"CONCURRENT TEST ({num_clients} parallel clients)")
    print("=" * 60)

    def run_episode(client_id):
        """Single episode: reset + 2 tool calls."""
        client = get_client()
        t0 = time.time()
        client.reset()
        client.call_tool("add_and_execute_code_cell", code=f"print({client_id} * 100)")
        client.call_tool("add_and_execute_code_cell", code="print('done')")
        elapsed = time.time() - t0
        client.__exit__(None, None, None)
        return elapsed

    # Warm up
    print("  Warming up...")
    run_episode(0)

    # Run concurrent episodes
    t_start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
        futures = [executor.submit(run_episode, i) for i in range(num_clients)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    wall_time = time.time() - t_start

    for i, t in enumerate(sorted(results)):
        print(f"  Client {i+1}: {t:.2f}s")

    print(f"\n  Wall time ({num_clients} episodes): {wall_time:.2f}s")
    print(f"  Throughput: {num_clients / wall_time:.2f} episodes/s")
    print(f"  Avg per episode: {statistics.mean(results):.2f}s")
    print(f"  Max per episode: {max(results):.2f}s")
    return wall_time, num_clients / wall_time


def main():
    print(f"Benchmarking: {ENV_URL}\n")

    single = benchmark_single_client()
    ep_avg = benchmark_full_episode()

    # Test increasing concurrency
    for n in [2, 4, 8, 16]:
        try:
            benchmark_concurrent(n)
        except Exception as e:
            print(f"  FAILED at {n} concurrent: {e}")
            break
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Reset latency:     {single['reset_avg']:.2f}s")
    print(f"  Code exec latency: {single['code_exec_avg']:.2f}s")
    print(f"  Shell cmd latency: {single['shell_avg']:.2f}s")
    print(f"  State query:       {single['state_avg']:.2f}s")
    print(f"  Full episode:      {ep_avg:.2f}s")
    print()
    print("  Estimated per-rollout overhead during training:")
    print(f"    1 tool call episode:  ~{single['reset_avg'] + single['code_exec_avg']:.1f}s")
    print(f"    3 tool call episode:  ~{single['reset_avg'] + 3*single['code_exec_avg']:.1f}s")
    print(f"    With 8 rollouts (seq): ~{8 * (single['reset_avg'] + single['code_exec_avg']):.1f}s")


if __name__ == "__main__":
    main()
