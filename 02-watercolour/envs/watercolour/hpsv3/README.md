---
title: Watercolour HPSv3 Scorer
emoji: 🎨
colorFrom: indigo
colorTo: pink
sdk: docker
pinned: false
app_port: 8000
---

# HPSv3 behind one endpoint

[HPSv3](https://huggingface.co/MizzenAI/HPSv3) carries **0.30 of the reward** in the
watercolour environment, and 0.90 in the run without the pairwise judge. Without it
the reward is 0.10 at most.

It lives in its own Space rather than inside the environment for one reason: it is a
7B preference model and needs a GPU, while the environment needs a browser and does
not. Splitting them keeps a single expensive machine from having to do both.

> [!WARNING]
> **Needs a GPU. `a100-large` is what this project used.** The model is 16.6 GB of
> weights, loaded on the first request rather than at import, so the Space answers
> `/health` while they are still arriving.

## Deploy it

Upload these four files to a new Space with `sdk: docker` and GPU hardware. Then
point the environment at it:

```
WATERCOLOUR_HPSV3_URL=https://<your-space>.hf.space
```

## The endpoint

```
POST /score   {"png_base64": "...", "prompt": "a loose watercolour flower"}
      ->      {"mu": 6.62, "score": 0.834}
```

`mu` is the raw preference score. `score` is `1 / (1 + exp(-mu / 4))`, which is what
the reward uses. The prompt matters: swapping it moves every image in the predicted
direction, which is how we established that HPSv3 is the term deciding "is this a
flower" while the pairwise judge decides "is it well painted".

## Cost, said plainly

This is the piece that surprises people. A scorer left running costs more than the
training that uses it: over this project the Space sat on `a100-large` for **at least
97 hours**, more than every a100-large training job put together. It has to stay up
for the whole run, and it does not switch itself off.
