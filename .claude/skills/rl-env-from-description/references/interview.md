# Interview question bank

Use this when the user's description is too thin to start coding. Don't run the full bank — pick what's missing from their prompt.

## 1. The loop in plain English

Ask: *"In one or two sentences, what is the agent doing each turn?"*

Listen for:
- The **trigger** ("the user asks…", "a board state arrives…")
- The **agent's choice** ("…the agent picks an action…")
- The **feedback** ("…and sees the result of that action")

If you can't draft a 5-step bullet trace from their answer, ask again.

## 2. Action surface

Ask: *"What can the agent do, concretely?"* — accept any of:

- A list of tool names with arguments → **structured tool calls**, the default. Targets: OpenEnv (`@mcp.tool`), ORS (`@tool` on `Environment`), Verifiers (plain functions).
- "It just types a guess word" → **single-tool**, like Wordle.
- "It writes code blocks / XML tags" → **text-action with parsing**. Only do this if the model has no native tool calling. Targets: SkyRL Gym / GEM.
- "It clicks and types on a screen" → **vision / computer-use**, 19-tool action surface modelled on Anthropic's `computer_20251124` schema (broadest superset across Claude / OpenAI Operator / Qwen3-VL).

If you genuinely can't tell, propose structured tool calls — they work with every modern model.

## 3. State across turns

Ask: *"Between two tool calls in the same episode, does anything need to remember the previous call?"*

| Answer | Implication |
|---|---|
| "No, every call is independent" | Stateless — easiest. No session needed. |
| "Yes, but it's just a Python dict / counter" | In-memory state on the env instance. |
| "There's a kernel / browser / process" | External backend with a per-session sandbox. Probably E2B. |

State that survives across episodes is rare and usually a bug — flag it.

## 4. Reward

Ask: *"How do we know the agent did well?"* — the answer pins the reward style:

| Their answer | Reward style |
|---|---|
| "It's right or wrong at the end" | Terminal reward (1.0/0.0). Use `terminate(status)` tool. |
| "Each step has its own score" | Per-tool-call reward in `ToolOutput.reward` (ORS-native). |
| "There's a unit test / regex / LLM judge that runs after" | Post-episode `/verify` (NeMo Gym) or external grader. |
| "I'll figure it out later" | Stub reward as 0.0, mark TODO, **don't block creation on this**. |

## 5. External backends

Ask: *"Does the env need anything outside the Python process?"*

- E2B sandbox? → Need `E2B_API_KEY` in `.env`. Verifiers / SkyRL / GEM run the sandbox in-process; OpenEnv / ORS / NeMo Gym run it server-side.
- Web service? → Probably belongs as a tool that uses `requests` / `httpx`.
- Database? → Treat as a tool too. State lives there, not in the env class.
- Nothing? → Easiest case.

## 6. Termination

Ask: *"When does an episode end?"*

- "After N turns" → fixed turn cap, set in env config.
- "When the model says it's done" → expose a `terminate(status)` tool, watch for `finished=True`.
- "When a condition is met" (e.g. `won == True`) → check inside the tool that mutated state, return `finished=True` from there.
- "Whichever comes first" → both. The rollout caps `MAX_TURNS` and the env signals `finished` early.

## 7. The two-question shortcut

If you only have time for two questions, ask:

1. *"What does the agent do?"* (covers loop + action surface)
2. *"What's the reward signal?"* (covers reward + termination)

Everything else can be defaulted reasonably.
