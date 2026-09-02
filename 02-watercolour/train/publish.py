# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface-hub"]
# ///
"""Turn a local pool and a finished run into the four Hub artifacts.

The chain from `pool_photos.py` to `watercolour_grpo.py` produces files on disk and
a repo full of PNGs. This is the last step, and it existed only as ad-hoc commands
until someone tried to follow the recipe end to end and found it missing.

    uv run publish.py pool   --pool ../envs/watercolour/core/reference_pool --org YOURORG
    uv run publish.py rollouts --run YOURACCOUNT/watercolour-grpo-myrun --tag hps-only --org YOURORG

`pool` reads the manifest the rating step wrote and ships the `love` and `okay`
tiers with their sketches and the photograph provenance for each. `rollouts` pulls
the `film/` directory a training run pushed and turns it into a dataset with the
reward, the sketch and the per-step group metrics.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import shutil

from huggingface_hub import HfApi, snapshot_download

METHODS = [
    "scaleBrushes", "noStroke", "fill", "noFill", "fillBleed",
    "fillTexture", "beginShape", "vertex", "endShape", "circle",
]
FILM = re.compile(r"^c(\d{4})_g(\d{2})_r([\d.]+)(_none)?\.png$")


def publish_pool(args) -> None:
    """Ship the rated pool as an imagefolder dataset."""
    pool = pathlib.Path(args.pool)
    manifest = json.loads((pool / "manifest_v2.json").read_text())
    photos = {}
    if args.photos:
        photos = {x["file"]: x for x in json.loads(pathlib.Path(args.photos).read_text())}

    out = pathlib.Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "sources").mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in manifest:
        if entry.get("grada") not in ("love", "okay"):
            continue
        png = pool / entry["fichero"]
        js = pool / "sources" / f"{png.stem}.js"
        if not png.exists():
            continue
        shutil.copy(png, out / "images" / png.name)
        if js.exists():
            shutil.copy(js, out / "sources" / js.name)
        photo = photos.get(entry.get("foto"))
        rows.append({
            "file_name": f"images/{png.name}",
            "source_file": f"sources/{js.name}" if js.exists() else None,
            "tier": entry["grada"],
            "subject": entry.get("subject"),
            "generator_model": entry.get("modelo"),
            "refinement_round": entry.get("ronda"),
            "hpsv3_mu": entry.get("mu"),
            "paint_coverage": entry.get("pigmento"),
            "gate_errors": entry.get("errores"),
            "reference_photo": entry.get("foto") if photo else None,
            "reference_photo_licence": photo["licence"] if photo else None,
            "reference_photo_attribution": photo["attribution"] if photo else None,
            "reference_photo_url": photo["observation_url"] if photo else None,
        })
    with (out / "metadata.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if photos:
        usadas = sorted({r["reference_photo"] for r in rows if r["reference_photo"]})
        (out / "photo_attribution.json").write_text(
            json.dumps([photos[f] for f in usadas], indent=1, ensure_ascii=False)
        )

    print(f"{len(rows)} references, tiers: {dict(collections.Counter(r['tier'] for r in rows))}")
    _upload(out, f"{args.org}/watercolour-reference-pool", "dataset", args.dry_run,
            "Add the watercolour reference pool")


def publish_rollouts(args) -> None:
    """Turn a run's `film/` directory into a dataset."""
    src = pathlib.Path(snapshot_download(args.run, repo_type="model",
                                        allow_patterns=["film/c*"])) / "film"
    log = pathlib.Path(args.log).read_text(errors="ignore") if args.log else ""
    step_reward = [float(x) for x in re.findall(r"'reward': '([\d.eE+-]+)'", log)]
    # per-step group means of each reward term, from the trainer's desglose lines
    group_terms = re.findall(
        r"desglose: judge ([\d.]+)\u00b1[\d.]+\[[\d.,]+\]\s+length ([\d.]+)\u00b1[\d.]+"
        r"\[[\d.,]+\]\s+paint_fraction ([\d.]+)\u00b1[\d.]+\[[\d.,]+\]\s+quality ([\d.]+)",
        log,
    )

    out = pathlib.Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "sources").mkdir(parents=True, exist_ok=True)
    rows = []
    for png in sorted(src.glob("*.png")):
        m = FILM.match(png.name)
        if not m or m.group(4):  # `_none` marks a rollout nothing could score
            continue
        if args.max_step is not None and int(m.group(1)) > args.max_step:
            continue
        js = src / f"{png.stem}.js"
        if not js.exists():
            continue
        code = js.read_text(errors="ignore")
        shutil.copy(png, out / "images" / png.name)
        shutil.copy(js, out / "sources" / js.name)
        used = {k: code.count(f"brush.{k}(") for k in METHODS}
        step = int(m.group(1))
        rows.append({
            "file_name": f"images/{png.name}",
            "source_file": f"sources/{js.name}",
            "run": args.tag,
            "judge_weight": args.judge_weight,
            "hpsv3_weight": args.hpsv3_weight,
            "step": step,
            "position_in_group": int(m.group(2)),
            "reward": float(m.group(3)),
            "code": code,
            "code_chars": len(code),
            "n_shapes": used["beginShape"],
            "n_vertices": used["vertex"],
            "n_circles": used["circle"],
            "n_fill_calls": used["fill"],
            "brush_methods_used": sorted(k for k, v in used.items() if v),
            "step_group_reward": step_reward[step] if step < len(step_reward) else None,
            "group_judge_mean": float(group_terms[step][0]) if step < len(group_terms) else None,
            "group_length_mean": float(group_terms[step][1]) if step < len(group_terms) else None,
            "group_paint_mean": float(group_terms[step][2]) if step < len(group_terms) else None,
            "group_quality_mean": float(group_terms[step][3]) if step < len(group_terms) else None,
        })
    with (out / "metadata.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    steps = collections.Counter(r["step"] for r in rows)
    incompletos = {k: v for k, v in sorted(steps.items()) if v != 8}
    print(f"{len(rows)} rollouts over {len(steps)} steps")
    if incompletos:
        print(f"  groups with fewer than 8: {incompletos}")
        print("  those are rollouts whose render failed or whose scorer did not answer")
    _upload(out, f"{args.org}/watercolour-rollouts-{args.tag}", "dataset", args.dry_run,
            f"Add every rollout from the {args.tag} run")


def _upload(folder, repo_id, repo_type, dry_run, message) -> None:
    if dry_run:
        print(f"dry run, would upload {folder} to {repo_id}")
        return
    api = HfApi()
    api.create_repo(repo_id, repo_type=repo_type, exist_ok=True, private=False)
    api.upload_folder(repo_id=repo_id, repo_type=repo_type,
                      folder_path=str(folder), commit_message=message)
    print(f"uploaded to {repo_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="what", required=True)

    p = sub.add_parser("pool")
    p.add_argument("--pool", required=True, help="directory the rating step wrote")
    p.add_argument("--photos", help="manifest.json from pool_photos.py, for provenance")
    p.add_argument("--out", default="/tmp/pool-dataset")
    p.set_defaults(fn=publish_pool)

    p = sub.add_parser("rollouts")
    p.add_argument("--run", required=True, help="the model repo a run pushed to")
    p.add_argument("--tag", required=True, help="hps-only, judge-led, hps-led")
    p.add_argument("--log", help="the job log, for the per-step group reward")
    p.add_argument("--max-step", type=int, default=None,
                   help="drop rollouts past this step (a run cancelled after its last checkpoint)")
    p.add_argument("--judge-weight", type=float, default=0.0)
    p.add_argument("--hpsv3-weight", type=float, default=0.9)
    p.add_argument("--out", default="/tmp/rollouts-dataset")
    p.set_defaults(fn=publish_rollouts)

    for s in sub.choices.values():
        s.add_argument("--org", required=True)
        s.add_argument("--dry-run", action="store_true")

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
