# SPDX-License-Identifier: BSD-3-Clause

"""One rollout against the watercolour environment, printed so a human can read it.

Their CONTRIBUTING asks for this and gives the reason: if a person cannot read a
trajectory and tell whether the model did well, neither can a reward function.

    uv run rollout.py https://<you>-watercolour-env.hf.space
    uv run rollout.py http://localhost:8000

Needs `HF_TOKEN` for the pairwise judge, and the env needs its HPSv3 Space up.
Without either, the reward tops out at 0.10 and the breakdown says so.
"""


from __future__ import annotations

import sys
from pathlib import Path

# Two deliberate departures from the layout in CONTRIBUTING.md, both forced by the
# same thing: this folder is called `openenv` and so is the installed package.
#
# 1. There is no `__init__.py` here. With one, `import openenv` resolves to this
#    folder whenever the interpreter's working directory is the environment root,
#    which is what the Dockerfile sets, and `openenv.core` then does not exist.
# 2. The path entry is appended rather than inserted, and points at the folder
#    holding `core/`, so an installed package always wins over a local directory.
_ENV_ROOT = str(Path(__file__).resolve().parents[1])
if _ENV_ROOT not in sys.path:
    sys.path.append(_ENV_ROOT)


_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from client import WatercolourEnv  # noqa: E402

# No default Space to point at: the environment needs paid hardware, so there is
# no instance of it left running. Deploy your own and pass its URL.
DEFAULT = None

# A sketch that uses only the ten allowed brush methods and paints a passable
# flower. Hand-written rather than generated, so this file does not need a model.
SKETCH = """```javascript
async function setup() {
  createCanvas(600, 600, WEBGL);
  brush.scaleBrushes(3);
  angleMode(DEGREES);
  noLoop();
}

function draw() {
  translate(-width / 2, -height / 2);
  background("#f9f4e6");
  brush.noStroke();
  for (let i = 0; i < 5; i++) {
    const a = i * 72;
    brush.fill("#e88c82", 200);
    brush.fillBleed(0.25);
    brush.beginShape(0.6);
    brush.vertex(300, 300);
    brush.vertex(300 + 210 * Math.cos(a), 300 + 210 * Math.sin(a));
    brush.vertex(300 + 160 * Math.cos(a + 18), 300 + 160 * Math.sin(a + 18));
    brush.endShape(true);
  }
  brush.fill("#ffdc8a", 230);
  brush.circle(300, 300, 40, 0.3);
}
```"""


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not base:
        raise SystemExit(
            "pass the URL of your environment Space, e.g.\n"
            "  uv run rollout.py https://<you>-watercolour-env.hf.space"
        )
    print(f"env: {base}\n")
    with WatercolourEnv(base_url=base, message_timeout_s=300.0).sync() as env:
        obs = env.reset(subject="a peach hibiscus", references=4, seed=0)
        o = obs.observation or {}
        print(f"subject: {o.get('prompt')}")
        print(f"system prompt: {len(o.get('system_prompt') or '')} chars, "
              f"lists the allowed brush methods\n")

        result = env.step({"response": SKETCH})
        o = result.observation or {}
        b = o.get("breakdown") or {}
        print(f"reward: {result.reward}")
        print(f"components: {b.get('components')}")
        g = b.get("gate") or {}
        print(f"gate passed: {g.get('passed')}  violations: {g.get('violations')}")
        r = g.get("render") or {}
        print(f"render: paint_fraction {r.get('paint_fraction')}  "
              f"finished {r.get('finished')}  {r.get('elapsed_ms')} ms")
        j = b.get("judge") or {}
        print(f"judge: {j.get('score')} over {len(j.get('comparisons') or [])} references")
        for c in (j.get("comparisons") or [])[:2]:
            print(f"  vs {c.get('reference')}: {c.get('score')}")
            for reason in (c.get("reasons") or [])[:1]:
                print(f"     {reason[:100]}")


if __name__ == "__main__":
    main()
