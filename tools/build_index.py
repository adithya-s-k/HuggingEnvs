#!/usr/bin/env python3
"""Regenerate the generated blocks in the READMEs from each project's `project.yaml`.

Keeps the root project table and each project's framework matrix honest, so adding
a project or a framework port means editing one manifest instead of several tables.

Blocks are delimited in the Markdown by:

    <!-- BEGIN:projects -->  ... <!-- END:projects -->     (root README)
    <!-- BEGIN:matrix -->    ... <!-- END:matrix -->       (project README)

    python3 tools/build_index.py            # rewrite the blocks
    python3 tools/build_index.py --check    # fail if anything is stale (for CI)

Requires PyYAML:  pip install pyyaml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("error: PyYAML is required — pip install pyyaml")

REPO_ROOT = Path(__file__).resolve().parents[1]

STATUS_ICON = {
    "stable": "✅ stable",
    "notebook-only": "📓 notebook",
    "wip": "🚧 wip",
}
VERIFIED_ICON = {
    True: "✅",
    False: "—",
    "deployed-only": "⚙️ deployed",
}


def load_projects() -> list[dict]:
    projects = []
    for manifest in sorted(REPO_ROOT.glob("[0-9][0-9]-*/project.yaml")):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        data["_dir"] = manifest.parent
        projects.append(data)
    return sorted(projects, key=lambda p: p.get("order", 99))


def render_projects_table(projects: list[dict]) -> str:
    rows = [
        "| # | Project | What you get | Envs | Frameworks | Deployed | Status |",
        "|---|---|---|:--:|:--:|:--:|---|",
    ]
    for p in projects:
        folder = p["_dir"].name
        num = folder.split("-", 1)[0]
        envs = p.get("envs") or []
        frameworks = {f for e in envs for f in (e.get("frameworks") or {})}
        spaces = {
            spec["space"]
            for e in envs
            for spec in (e.get("frameworks") or {}).values()
            if spec.get("space")
        }
        status = STATUS_ICON.get(p.get("status", ""), p.get("status", ""))
        rows.append(
            f"| **{num}** | **[{p['title']}](./{folder}/)** | {p['tagline']} "
            f"| {len(envs)} | {len(frameworks)} | {len(spaces)} | {status} |"
        )
    return "\n".join(rows)


def render_matrix(project: dict) -> str:
    envs = project.get("envs") or []
    frameworks: list[str] = []
    for env in envs:
        for fw in (env.get("frameworks") or {}):
            if fw not in frameworks:
                frameworks.append(fw)
    if not frameworks:
        return ""

    header = "| Env | Tools | Backend | " + " | ".join(f"`{f}`" for f in frameworks) + " |"
    sep = "|---|---|---|" + "---|" * len(frameworks)
    rows = [header, sep]
    for env in envs:
        cells = []
        for f in frameworks:
            spec = (env.get("frameworks") or {}).get(f)
            cells.append(VERIFIED_ICON.get(spec.get("verified", False), "—") if spec else "—")
        tools = env.get("tools", "—")
        rows.append(
            f"| **{env['name']}** | {tools} | `{env.get('backend', '—')}` | " + " | ".join(cells) + " |"
        )
    return "\n".join(rows)


def splice(path: Path, marker: str, body: str, *, check: bool) -> bool:
    """Replace the delimited block. Returns True if the file is (or would be) changed."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(<!-- BEGIN:{marker} -->\n).*?(\n<!-- END:{marker} -->)", re.S
    )
    if not pattern.search(text):
        print(f"  skip {path.relative_to(REPO_ROOT)} — no {marker} block")
        return False
    updated = pattern.sub(lambda m: m.group(1) + body + m.group(2), text)
    if updated == text:
        return False
    if not check:
        path.write_text(updated, encoding="utf-8")
    print(f"  {'stale' if check else 'wrote'} {path.relative_to(REPO_ROOT)} [{marker}]")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report staleness without writing")
    args = ap.parse_args()

    projects = load_projects()
    print(f"{len(projects)} project(s): " + ", ".join(p["_dir"].name for p in projects))

    changed = splice(REPO_ROOT / "README.md", "projects", render_projects_table(projects), check=args.check)
    for p in projects:
        matrix = render_matrix(p)
        if matrix:
            changed |= splice(p["_dir"] / "README.md", "matrix", matrix, check=args.check)

    if args.check and changed:
        sys.exit("error: generated blocks are out of date — run tools/build_index.py")
    print("✓ up to date" if not changed else "✓ regenerated")


if __name__ == "__main__":
    main()
