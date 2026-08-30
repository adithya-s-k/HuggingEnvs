# Desktop · GEM

GEM (Gymnasium-style) env wrapping an E2B Desktop sandbox. Same tag grammar as the SkyRL variant — only the framework wrapping differs:

- `reset()` returns `(observation, info)`.
- `step(action)` returns the **5-tuple** `(observation, reward, terminated, truncated, info)`.
- `spawn()` for parallel rollouts (per the GEM convention).

## Tags

Same grammar as `desktop_env/skyrl_gym/`:

```
<screenshot/>
<click x="100" y="200"/>
<type>hello</type>
<key>enter</key>
<scroll x="500" y="400" direction="down" amount="3"/>
<terminate status="success"/>
```

## Run

```bash
cd 00-environments-101/envs/desktop/gem
uv sync
uv run python rollout.py        # Qwen3-VL via HF Router
```

`E2B_API_KEY` is required (sandbox runs in-process). Reward = 1.0 only when the model emits `<terminate status="success"/>`.
