# Desktop · NeMo Gym

Desktop computer-use environment exposed as a NeMo Gym Resources Server. Each session owns an E2B Desktop sandbox; tools are plain `app.post("/<tool>")` endpoints + cookie-based session id, plus the standard `/seed_session` and `/verify`.

The 19-tool action surface mirrors Anthropic's `computer_20251124` schema (same as `desktop_env/openenv/` and `desktop_env/ors/`). Coordinates are `[x, y]` arrays in pixel space.

## Endpoints

| Path | Body |
|---|---|
| `POST /seed_session` | `{}` — sets the session cookie |
| `POST /reset` | `{"app": "firefox", "resolution": [1024, 768]}` |
| `POST /screenshot` | `{}` — returns `{"output": "...", "image_b64": "..."}` |
| `POST /left_click` | `{"coordinate": [x, y], "text": "shift"?}` |
| `POST /right_click` `/middle_click` `/double_click` `/triple_click` | same shape |
| `POST /mouse_move` | `{"coordinate": [x, y]}` |
| `POST /left_click_drag` | `{"start_coordinate": [...], "coordinate": [...], "text"?}` |
| `POST /scroll` | `{"coordinate": [...], "scroll_direction": "down", "scroll_amount": 3}` |
| `POST /type` | `{"text": "..."}` |
| `POST /key` `/hold_key` | `{"keys": "ctrl+s"}` (+ `"duration": 0.5` for hold) |
| `POST /wait` | `{"duration": 1.0}` |
| `POST /terminate` | `{"status": "success"}` |
| `POST /run_command` | `{"command": "..."}` |
| `POST /verify` | NeMo Gym verify — reward 1.0 if the agent ever called `terminate(status="success")` |

## Run

```bash
cd envs/desktop_env/nemo_gym
uv sync                                  # Python 3.12+
uv run python server.py                  # serves on :11000
uv run python rollout.py                 # Qwen3-VL via HF Router
```

> ⚠️ NeMo Gym's `run_webserver()` initializes Ray, which fails on shared cluster nodes (`gcs_server` can't bind). On those machines deploy via Docker / HF Space.
