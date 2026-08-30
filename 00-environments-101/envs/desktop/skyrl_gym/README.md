# Desktop · SkyRL Gym

SkyRL Gym `BaseTextEnv` driving an E2B Desktop sandbox. The model produces free text containing **action tags**; the env parses each tag and dispatches to the desktop controller.

## Action tag grammar

```
<screenshot/>
<click x="100" y="200"/>             (button="right" or "middle" optional)
<double_click x="100" y="200"/>
<triple_click x="100" y="200"/>
<move x="100" y="200"/>
<drag sx="100" sy="200" x="400" y="500"/>
<scroll x="500" y="400" direction="down" amount="3" modifier="shift"?/>
<type>text to type</type>
<key>ctrl+s</key>
<wait seconds="1"/>
<run>echo hello</run>
<terminate status="success"/>
```

## Step return

`BaseTextEnvStepOutput(observations=[{role: 'user', content: ...}], reward, done, metadata)`.
Reward: 1.0 if `<terminate status="success"/>` was emitted; 0.0 otherwise.

## Run

```bash
cd 00-environments-101/envs/desktop/skyrl_gym
uv sync
uv run python rollout.py        # Qwen3-VL via HF Router, multimodal per turn
```

The rollout sends the latest screenshot as an image in the user message at the start of each turn so a vision model can ground its tag coordinates.

`E2B_API_KEY` must be set — SkyRL runs the sandbox in-process.
