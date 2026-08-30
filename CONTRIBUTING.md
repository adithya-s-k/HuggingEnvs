# Contributing

The most useful contributions here, roughly in order:

1. **A new environment** — a task nobody has modelled yet.
2. **A new framework port** of an environment that already exists.
3. **A reproduction that disagrees with ours.** If you ran a recipe and got a different curve, that's
   a bug report we want.
4. **Fixes to rollouts that broke.** Frameworks move fast; things rot.

## Repository shape

```
HuggingEnvs/
├── NN-<project>/       a self-contained project
│   ├── README.md       the project page
│   ├── project.yaml    manifest — drives the generated README tables
│   ├── envs/<env>/     core/ + one folder per framework
│   ├── train/          configs + launch scripts
│   ├── notebooks/
│   └── results/
├── content/            articles/ and slides/
├── tools/              deploy.py, build_index.py, jupyter_launch.py
└── .claude/skills/     the five env-authoring agent skills
```

Those folder names mean the same thing in every project. Keep it that way.

## Adding an environment

The paved path is the agent skills — they do the scaffolding and the rollout smoke test:

```bash
npx skills add adithya-s-k/HuggingEnvs
# then, in your agent: "make me an env where the agent plays connect-four"
```

By hand, inside the project you're adding to:

1. Put the domain logic in `envs/<env>/core/` — the game, the controller, the task list. Anything a
   framework port would otherwise copy belongs here. **If two framework folders contain the same
   file, it belongs in `core/`.**
2. Add one folder per framework beside it. Each ships a `README.md`, a `pyproject.toml`, and a
   runnable `rollout.py`.
3. Framework code imports from `core/`:
   ```python
   _ENV_ROOT = str(Path(__file__).resolve().parents[1])
   if _ENV_ROOT not in sys.path:
       sys.path.insert(0, _ENV_ROOT)
   from core.game import WordleGame  # noqa: E402
   ```
4. Record it in `project.yaml`, then run `python3 tools/build_index.py` to refresh the tables.

## Before you open a PR

```bash
python3 tools/build_index.py --check    # generated tables are current
uv run python rollout.py                # your env actually runs
```

**Read one trajectory by hand.** Did the model see what you expected? Did the tool returns make
sense? Did the reward fire? If a human can't read the trajectory and tell whether the model did
well, neither can a reward function — and no amount of training will surface that.

## Articles and slides

Sources live in `content/`, never as a nested git clone. Deployment goes over the Hub HTTP endpoint:

```bash
python3 tools/deploy.py content/slides/<deck> HuggingEnvs/<space>
```

Each item's `space.md` is its Space card — the frontmatter there decides how it deploys.

## What doesn't belong in git

Build output (`node_modules/`, `dist/`, `.astro/`), slide exports (`export/` — PPTX and PDF go to the
Hub), virtualenvs, and anything over a few MB. Large artifacts belong on
[HuggingEnvs](https://huggingface.co/HuggingEnvs), linked from the project README.

## License

Contributions are under [Apache 2.0](./LICENSE).
