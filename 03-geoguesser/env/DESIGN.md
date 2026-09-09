# Design

The agent is dropped at an unknown street-level location, looks around, walks along the road, pins candidate coordinates on a map to check itself, and commits to a final guess. Reward is distance-based.

This is an independent project, unaffiliated with GeoGuessr AB. Imagery is openly licensed: CC BY-SA 4.0, Mapillary contributors.

## One environment, several backends

The task, reward curve, response parser, map renderer and pin loop are identical no matter where the imagery comes from. Only the imagery source changes, and with it which tools exist. So there is one environment and a `PanoramaBackend` protocol behind it.

| backend | `look` | `move` | licence | role |
|---|---|---|---|---|
| `mapillary` | yes, local reprojection | yes, sequence graph | CC BY-SA | training and eval |
| `dataset` (osv5m, later) | no, single fixed view | no | CC BY-SA 4.0 | 5.1M-image scale |
| `google` (later) | yes | yes, true pano links | ToS-restricted | eval and demo only |

Capability gaps surface as unregistered tools, never as a different observation schema, so a policy trained against one backend runs unmodified against another. Registering a tool that always errors would just teach a policy to burn its step budget.

## Determinism

```python
reset(split="eval", index=7)   # exact task, byte-identical   -> GRPO, eval
reset(seed=42)                 # tasks[42 % len(tasks)]       -> replay
reset()                        # random, index in metadata    -> UI "next"
```

Three things make repeats byte-identical. Panorama bytes come from local disk, never an expiring CDN URL. Reprojection is pure numpy with integer sampling. The initial heading is pinned to the panorama's own `compass_angle`, so `look(0)` is true north in every task.

A GRPO group calls `reset(split=s, index=k)` N times and gets N identical starting observations.

## Task API

Tasks are consumed through `openenv.core.harness` rather than a bespoke index. `GeoGuesserSessionFactory` in `harness.py` maps a task dict to `reset_kwargs={"task_index": ...}`, which gives three things unchanged:

- `CollectRunner(tasks=...)` for JSONL rollout collection with resume, with `EpisodeRecord.task` recording which task produced each episode.
- `build_harness_rollout_func(...)`, a TRL-compatible rollout function where each prompt is a task.
- `EvalConfig` and `EvalResult`, whose `harness_version`, `library_versions` and `dataset` fields are the provenance an eval score needs.

`harness.py` works, but the training in this repository does not use it. `train/grpo_geoguesser.py` drives `GRPOTrainer(environment_factory=...)` against the HTTP client directly. Nothing here imports `harness.py` and no test covers it, so treat it as a supported surface that is currently unexercised.

## Imagery is a lazy cache, not a bundled corpus

Mapillary `thumb_*_url` values are expiring signed CDN URLs, so imagery is resolved to a local cache and never fetched mid-rollout from a URL stored in the index. The index holds image ids, coordinates, sequence ids, headings, capture dates, creator attribution and a sha256 per start frame.

At build time each task's start frame is downloaded, about 29 MB per 100 tasks. At runtime movement frames fetch on first use and cache to disk. `--prefetch-frames N` warms a task's whole sequence for a frozen eval.

`MAPILLARY_API_KEY` is needed by the builder, and at runtime only on a cache miss. A fully warmed cache runs offline.

## Reward

```
geo     = exp(-haversine_km / 1492.7)          # in [0, 1]
partial = 0.15 * country_hit + 0.10 * region_hit
cost    = 0.01*looks + 0.01*maps + 0.02*pins + 0.05*moves
reward  = clip(geo + partial, 0, 1) - cost
```

An unparseable or out-of-range guess scores 0.0 with feedback. Extraction failures belong in the score, not hidden in the harness.

## The pin loop, and the trap in it

`place_pin(lat, lon)` returns a rendered map plus a description of what the agent pinned: country, subregion, nearest city with distance and bearing, and the distance to its own earlier pins. It reveals nothing about the target.

If pin feedback carried any signal about the truth, whether distance, warmer or colder, or a highlighted region, the optimal policy would be binary search. About twenty pins would reach metre-level accuracy and the environment would measure bisection instead of geographic reasoning. Distance and score arrive only from `submit_guess`, which is terminal.

The same reasoning constrains map detail. Detail is a function of zoom alone, never of proximity to the answer. Prefetching high-resolution map data around task locations would turn the cache into a ground-truth oracle.

## Measured facts behind these choices

Probed against the live Graph API.

- `camera_type` returns `spherical`, not the `equirectangular` the docs claim. Filtering on the documented value matches nothing.
- Panoramas are true 2:1 equirectangular: `thumb_2048` is 2048×1024, the original 7680×3840. Faces and plates arrive pre-blurred.
- Sequence frames sit about 3.3 m apart, measured over 12 frames with a mean of 3.3 m, min 3.1 and max 3.7. That is finer than Street View's roughly 10 m.
- Reprojection costs about 23 ms per 640×640 view in numpy.
- `/images` search is not a bulk endpoint. `limit` does not cap the scan, and dense bboxes beyond about ±0.0005 degrees fail with "reduce the amount of data". Discovery therefore uses many tiny bboxes.
- Panorama coverage at Street-View coordinates is thin: any imagery at 21 of 45 locations, full 360-degree panoramas at only 7 of 45. Coverage is heavily clustered, so expect a Europe-weighted task distribution and document it rather than hiding it.

## One guess per episode

`submit_guess` is terminal, so an episode is exactly one guess. The play page's five-round game is a wrapper around five separate episodes. Nothing in the environment accepts a second guess, and the pin loop is deliberately not a second chance. It is how a policy checks its own arithmetic before committing.

## Zoom needs the original panorama

Zooming a 2048×1024 panorama is resolution-starved. A 30-degree view samples about 170 source pixels and the measured mean gradient barely moves, 6.60 at 90 degrees against 7.03 at 30. The 7680×3840 original roughly doubles it, 10.23 and 14.87.

Each panorama is therefore cached twice and the field of view selects which is used. Wide views render from the 2048 in about 30 ms; views at or below 45 degrees render from the original in about 70 ms. A missing original degrades to a soft view rather than failing the step.

## Known gaps versus the real game

Movement is bounded by captured sequences, and dead-ends exist. Frame spacing varies enormously between sequences, from about 3 m to about 57 m, so `move()` reports the distance it actually travelled rather than the distance requested. There is no multi-round cumulative score in the environment itself, no satellite layer on the guess map, and a step budget replaces the wall-clock timer.

NMPZ mode is nearly free, needing only `place_pin` and `submit_guess` registered, and should ship as a difficulty tier. Coverage hints and web search are deliberately excluded: the first is a crutch and the second turns the task into retrieval.
