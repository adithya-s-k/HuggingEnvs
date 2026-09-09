# Building the dataset

The task splits already exist and are published. You only need this directory if you want to rebuild them, extend coverage, or understand how contamination was handled.

| split | tasks | countries | where |
|---|---:|---:|---|
| `eval` | 200 | 73, capped at 4 each | `../env/tasks/eval_pano_v3.jsonl`, committed |
| `train` | 3,452 | 132 | [`HuggingEnvs/geoguesser-tasks`](https://huggingface.co/datasets/HuggingEnvs/geoguesser-tasks) |
| imagery | 86,366 panoramas | n/a | [`HuggingEnvs/geoguesser-panos`](https://huggingface.co/buckets/HuggingEnvs/geoguesser-panos), 22 GB |

## The pipeline

Each step prints the next one. Expect the whole thing to take a day, mostly waiting on Mapillary.

```bash
python harvest_tiles.py                              # enumerate sequences worldwide
python build_tasks.py --tasks 2500 --mirror all      # pick tasks, mirror frames
python verify_offline.py tasks/pool_offline_5k.jsonl # top up anything missing
python split_tasks.py tasks/pool_offline_5k.jsonl --eval 200
```

| file | does |
|---|---|
| `harvest_tiles.py` | walk Mapillary's tile index and collect candidate sequences |
| `build_pano_tasks.py` | turn one sequence into a task: frames, headings, coordinates |
| `build_tasks.py` | do that at scale, with country balancing |
| `split_tasks.py` | cut eval and train apart, enforcing the contamination rules |
| `verify_offline.py` | check every frame in an index is mirrored locally, and fetch what is not |
| `fetch_detail_geo.py` | build the street-detail vectors the minimap uses |
| `readiness_check.py` | audit whether the environment is fit to train against |
| `deploy_hub.py` | push the Space, the dataset and the imagery bucket |

## Why the indexes hold no images

A task index is metadata only: every frame's coordinates, heading and capture date. That is enough to walk down a road without touching the network.

Image bytes are separate because Mapillary serves them through expiring signed URLs, which cannot be stored. They are mirrored once into a bucket and read from there.

## Contamination

Both splits come from one 3,673-task pool, so the rules are enforced once, before the split rather than after:

- no Mapillary sequence appears in both splits
- no training task sits within 1 km of an eval task

Frames are about 3.3 m apart. Holding out one image while keeping its neighbour holds out nothing, which is why the unit is the sequence and not the frame.

## Licence

Imagery is Mapillary, CC BY-SA 4.0. Every task carries its contributor and the environment displays the credit. If you rebuild the dataset, keep that field.
