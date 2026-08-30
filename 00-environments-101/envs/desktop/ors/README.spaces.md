---
title: Desktop ORS
emoji: 🖱️
colorFrom: pink
colorTo: indigo
sdk: docker
app_port: 7860
tags:
  - ors
  - openreward
  - computer-use
  - desktop
  - e2b
short_description: Cloud Linux desktop with computer-use tools, exposed via ORS
---

# Desktop ORS Environment Server

A cloud Linux desktop exposed as an [Open Reward Standard (ORS)](https://openrewardstandard.io) environment, built with the official [`openreward`](https://github.com/openrewardstandard/python-sdk) Python SDK. Each session creates a fresh [E2B Desktop](https://e2b.dev) sandbox.

The action surface mirrors **Anthropic's `computer_20251124`** schema so a model's native computer-use tool calls drive the env with minimal adaptation.

## Tools (19)

`screenshot`, `cursor_position`, `get_screen_size`, `left_click`, `right_click`, `middle_click`, `double_click`, `triple_click`, `mouse_move`, `left_click_drag`, `left_mouse_down`, `left_mouse_up`, `scroll`, `type`, `key`, `hold_key`, `wait`, `terminate`, `run_command`.

`screenshot` returns an `ImageBlock` (the model sees pixels, not text). Click/scroll tools accept `coordinate=[x, y]` and an optional `text` modifier (`"shift"`, `"ctrl+shift"`, …).

## Reward

`terminate(status="success")` → `reward=1.0, finished=True`.
`terminate(status="failure")` → `reward=0.0, finished=True`.
All other tools → `reward=0.0, finished=False`.

Part of the [exp_rl](https://github.com/adithya-s-k/exp_rl) project — demonstrating RL environment frameworks with TRL.
