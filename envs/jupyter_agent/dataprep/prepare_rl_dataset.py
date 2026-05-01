"""
End-to-end RL dataset preparation from jupyter-agent-dataset.

1. Load both splits (thinking + non_thinking), filter, shuffle, sample
2. Download needed Kaggle datasets to --output-dir
3. Upload raw Kaggle data to HF as {hub-name}-data
4. Format RL dataset with: prompt, answer, reference trace, sizes, metadata
5. Upload formatted dataset to HF as {hub-name}

Usage:
    # Test with 10
    python experiments/prepare_rl_dataset.py --target 10 --output-dir /fsx/$USER/data/kaggle-data-10 --hub-name AdithyaSK/jupyter-agent-rl-test

    # Full 10K
    python experiments/prepare_rl_dataset.py --target 10000 --output-dir /fsx/$USER/data/kaggle-data-10000 --hub-name AdithyaSK/jupyter-agent-rl-v0 --upload
"""

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from datasets import Dataset, concatenate_datasets, load_dataset
from huggingface_hub import HfApi

SEED = 42

SYSTEM_PROMPT = """You are an intelligent data science assistant with access to a stateful Jupyter notebook environment. You can execute Python code, run shell commands, edit cells, and inspect notebook state using the available tools.

You have access to the following files in /home/user/input/:
- {files}

Pre-installed packages: {packages}

Answer the following question based on the provided files.
When you have the final answer, use the final_answer tool to submit it.

Question: {question}"""

# Tool name mapping: original dataset → our environment
TOOL_RENAME = {
    "add_and_execute_jupyter_code_cell": "add_and_execute_code_cell",
}


# -- Kaggle download -------------------------------------------------------

def download_one(name: str, output_dir: Path, timeout: int = 180) -> tuple:
    dest = output_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    existing = [f for f in dest.rglob("*") if f.is_file() and f.stat().st_size > 0]
    if existing:
        files = [{"name": str(f.relative_to(dest)), "size": f.stat().st_size} for f in existing]
        return name, {"status": "cached", "files": files}
    try:
        r = subprocess.run(
            ["kaggle", "datasets", "download", "-d", name, "-p", str(dest), "--unzip"],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            return name, {"status": "error", "error": (r.stderr or r.stdout)[:200]}
        files = [{"name": str(f.relative_to(dest)), "size": f.stat().st_size}
                 for f in dest.rglob("*") if f.is_file()]
        return name, {"status": "success", "files": files} if files else (name, {"status": "empty"})
    except subprocess.TimeoutExpired:
        return name, {"status": "timeout"}
    except Exception as e:
        return name, {"status": "error", "error": str(e)[:200]}


def download_needed(names: set, output_dir: Path, manifest: dict, workers: int = 20):
    to_dl = [n for n in names if manifest.get(n, {}).get("status") not in ("success", "cached")]
    cached = len(names) - len(to_dl)
    print(f"  Need {len(names)} datasets, {cached} cached, {len(to_dl)} to download ({workers} workers)")
    if not to_dl:
        return manifest
    t0 = time.time()
    done = ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(download_one, n, output_dir): n for n in to_dl}
        for fut in as_completed(futs):
            name, result = fut.result()
            manifest[name] = result
            done += 1
            s = result["status"]
            if s in ("success", "cached"):
                ok += 1
                sz = sum(f["size"] for f in result.get("files", [])) / 1e6
                print(f"  [{done}/{len(to_dl)}] ✓ {name} ({sz:.1f}MB)")
            else:
                fail += 1
                print(f"  [{done}/{len(to_dl)}] ✗ {name} ({s})")
    print(f"  Done: {ok}✓ {fail}✗ in {time.time()-t0:.0f}s")
    return manifest


# -- Tool trace transformation ----------------------------------------------

def transform_messages(messages: list) -> list:
    """Transform original dataset messages to our tool naming convention.

    Original: add_and_execute_jupyter_code_cell → add_and_execute_code_cell
    Keeps: final_answer as-is
    Adds: role labels for system/user/assistant/tool
    """
    transformed = []
    for msg in messages:
        new_msg = {"role": msg["role"], "content": msg.get("content", "")}

        # Transform tool_calls
        if msg.get("tool_calls"):
            new_tool_calls = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                new_name = TOOL_RENAME.get(name, name)
                new_tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": new_name,
                        "arguments": fn.get("arguments", "{}"),
                    }
                })
            new_msg["tool_calls"] = new_tool_calls

        # Keep tool_call_id for tool responses
        if msg.get("tool_call_id"):
            new_msg["tool_call_id"] = msg["tool_call_id"]

        transformed.append(new_msg)
    return transformed


# -- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=10)
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--hub-name", type=str, default=None, help="HF hub name (e.g. AdithyaSK/jupyter-agent-rl-v0)")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--workers", type=int, default=20)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    target = args.target
    oversample = min(target * 3, 100_000)

    # ======================================================================
    # Step 1: Load, filter, shuffle, sample
    # ======================================================================
    t0 = time.time()
    print(f"=" * 60)
    print(f"Step 1: Load + filter + sample {oversample} candidates for {target} target")

    # Load only needed columns first (skip original_notebook for speed)
    ds_t = load_dataset("jupyter-agent/jupyter-agent-dataset", split="thinking",
                        columns=["messages", "question", "answer", "files_used",
                                 "kaggle_dataset_name", "edu_score", "packages_used"])
    ds_n = load_dataset("jupyter-agent/jupyter-agent-dataset", split="non_thinking",
                        columns=["messages", "question", "answer", "files_used",
                                 "kaggle_dataset_name", "edu_score", "packages_used"])
    print(f"  Loaded: thinking={len(ds_t)}, non_thinking={len(ds_n)} ({time.time()-t0:.1f}s)")

    ds_t = ds_t.add_column("source_split", ["thinking"] * len(ds_t))
    ds_n = ds_n.add_column("source_split", ["non_thinking"] * len(ds_n))
    ds_all = concatenate_datasets([ds_t, ds_n])

    # Filter: single file only
    ds_single = ds_all.filter(lambda b: [len(f) == 1 for f in b["files_used"]], batched=True)
    print(f"  Single-file: {len(ds_all)} → {len(ds_single)}")

    ds_cand = ds_single.shuffle(seed=SEED).select(range(min(oversample, len(ds_single))))
    print(f"  Candidates: {len(ds_cand)} ({time.time()-t0:.1f}s)")

    # ======================================================================
    # Step 2: Download needed Kaggle datasets
    # ======================================================================
    print(f"\n{'=' * 60}")
    print(f"Step 2: Download Kaggle datasets")
    needed = set(ds_cand["kaggle_dataset_name"])
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = download_needed(needed, output_dir, manifest, workers=args.workers)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # ======================================================================
    # Step 3: Filter to available, trim to target
    # ======================================================================
    print(f"\n{'=' * 60}")
    print(f"Step 3: Filter to available + trim to {target}")
    available = {n for n, v in manifest.items() if v.get("status") in ("success", "cached")}
    ds_avail = ds_cand.filter(lambda b: [k in available for k in b["kaggle_dataset_name"]], batched=True)
    print(f"  Available: {len(ds_avail)} / {len(ds_cand)}")
    ds_final = ds_avail.select(range(min(target, len(ds_avail))))
    print(f"  Final: {len(ds_final)} rows")

    # ======================================================================
    # Step 4: Format for TRL
    # ======================================================================
    print(f"\n{'=' * 60}")
    print(f"Step 4: Format dataset")

    # Size lookup from manifest
    size_lookup = {}
    for name, info in manifest.items():
        if info.get("status") in ("success", "cached"):
            size_lookup[name] = sum(f["size"] for f in info.get("files", []))

    rows = []
    for i in range(len(ds_final)):
        row = ds_final[i]
        kaggle_name = row["kaggle_dataset_name"]
        files = [f.split("/")[-1] for f in row["files_used"]]
        packages = row.get("packages_used", []) or []
        packages_str = ", ".join(packages[:15]) if packages else "pandas, numpy, matplotlib, seaborn, scikit-learn"

        # Transform the reference messages (tool name mapping)
        ref_messages = transform_messages(row["messages"])

        rows.append({
            "prompt": [
                {"role": "system", "content": SYSTEM_PROMPT.format(
                    files=", ".join(files),
                    packages=packages_str,
                    question=row["question"],
                )},
                {"role": "user", "content": row["question"]},
            ],
            "answer": row["answer"],
            "question": row["question"],
            "kaggle_dataset_name": kaggle_name,
            "files": files,
            "packages_used": packages,
            "edu_score": row["edu_score"],
            "source_split": row["source_split"],
            "dataset_size_bytes": size_lookup.get(kaggle_name, 0),
            "reference_messages": ref_messages,  # full trace with our tool names
            "task_index": i,
        })

    formatted = Dataset.from_list(rows)

    # Stats
    split_dist = Counter(r["source_split"] for r in rows)
    sizes = [r["dataset_size_bytes"] for r in rows]
    print(f"  Rows: {len(formatted)}")
    print(f"  Columns: {formatted.column_names}")
    print(f"  Splits: {dict(split_dist)}")
    print(f"  Unique Kaggle datasets: {len(set(r['kaggle_dataset_name'] for r in rows))}")
    print(f"  Sizes: <1MB={sum(1 for s in sizes if s < 1e6)}, "
          f"1-10MB={sum(1 for s in sizes if 1e6 <= s < 10e6)}, "
          f"10-100MB={sum(1 for s in sizes if 10e6 <= s < 100e6)}, "
          f">100MB={sum(1 for s in sizes if s >= 100e6)}")

    # Verify a sample row
    print(f"\n  Sample row:")
    sample = rows[0]
    print(f"    question: {sample['question'][:80]}")
    print(f"    answer: {sample['answer'][:80]}")
    print(f"    files: {sample['files']}")
    print(f"    dataset_size: {sample['dataset_size_bytes']/1e6:.1f}MB")
    print(f"    reference_messages: {len(sample['reference_messages'])} messages")
    ref_tools = [tc["function"]["name"]
                 for m in sample["reference_messages"]
                 for tc in (m.get("tool_calls") or [])]
    print(f"    reference tool calls: {ref_tools}")

    # ======================================================================
    # Step 5: Save locally
    # ======================================================================
    print(f"\n{'=' * 60}")
    print(f"Step 5: Save")
    local_path = output_dir / f"dataset-{target}"
    formatted.save_to_disk(str(local_path))
    print(f"  Local: {local_path}")

    # ======================================================================
    # Step 6: Upload to HF
    # ======================================================================
    if args.upload and args.hub_name:
        print(f"\n{'=' * 60}")
        print(f"Step 6: Upload to HuggingFace")

        # 6a: Upload formatted RL dataset
        print(f"  Uploading RL dataset → {args.hub_name}")
        formatted.push_to_hub(args.hub_name, private=False)
        print(f"  ✓ https://huggingface.co/datasets/{args.hub_name}")

        # 6b: Upload raw Kaggle data
        data_hub = f"{args.hub_name}-data"
        print(f"  Uploading raw Kaggle data → {data_hub}")
        api = HfApi()
        api.create_repo(data_hub, repo_type="dataset", exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(manifest_path),
            path_in_repo="manifest.json",
            repo_id=data_hub, repo_type="dataset",
        )

        # Upload each dataset folder (skip >500MB)
        used_datasets = set(r["kaggle_dataset_name"] for r in rows)
        total_to_upload = len(used_datasets)
        for idx, name in enumerate(sorted(used_datasets)):
            local = output_dir / name
            if not local.exists():
                continue
            files_list = [f for f in local.rglob("*") if f.is_file()]
            total_size = sum(f.stat().st_size for f in files_list)
            if total_size > 500_000_000:
                print(f"  [{idx+1}/{total_to_upload}] SKIP {name} ({total_size/1e6:.0f}MB > 500MB)")
                continue
            try:
                api.upload_folder(
                    folder_path=str(local), path_in_repo=f"data/{name}",
                    repo_id=data_hub, repo_type="dataset",
                    commit_message=f"Add {name}",
                )
                print(f"  [{idx+1}/{total_to_upload}] ✓ {name} ({total_size/1e6:.1f}MB)")
            except Exception as e:
                print(f"  [{idx+1}/{total_to_upload}] ✗ {name} ({e})")

        print(f"  ✓ https://huggingface.co/datasets/{data_hub}")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
