# Resolved versions

The `uv` header of `train/watercolour_grpo.py` pins no versions, following the
convention of the TRL and OpenEnv example scripts. The runs in this project installed
whatever resolved on their launch day. The job logs record "Installed 158 packages" but
not which ones, so the closest available record is this resolution, taken with
`uv pip compile` on 2026-09-02, one day after `judge-led` and `hps-led` launched and two
days after `hps-only`:

```
accelerate==1.14.0
datasets==5.0.1
openenv==0.4.1
peft==0.20.0
torch==2.13.0
torchvision==0.28.0
trackio==0.37.0
transformers==5.16.1
trl==1.12.0
```

To reproduce with these exact versions, add `==` pins for these packages to the script
header before launching. A resolution taken later may differ.
