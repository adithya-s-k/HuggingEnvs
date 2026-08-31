"""HPSv3 behind one endpoint.

The model is loaded on the first request rather than at import, so the Space
answers `/health` while 16.6GB of weights are still arriving and a failed load
reports itself instead of crash-looping the container.
"""

import base64
import io
import math
import threading

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="watercolour-hpsv3")

_scorer = None
_error: str | None = None
_lock = threading.Lock()


def scorer():
    """Return the loaded inferencer, loading it once."""
    global _scorer, _error
    with _lock:
        if _scorer is None and _error is None:
            try:
                from hpsv3 import HPSv3RewardInferencer

                _scorer = HPSv3RewardInferencer(device="cuda")
            except Exception as exc:  # noqa: BLE001
                _error = f"{type(exc).__name__}: {exc}"
    return _scorer


class Request(BaseModel):
    png_base64: str
    prompt: str = "a watercolour painting"


@app.get("/health")
def health() -> dict:
    """Report whether the model is loaded, without loading it."""
    return {"loaded": _scorer is not None, "error": _error}


@app.post("/score")
def score(request: Request) -> dict:
    """Return HPSv3's reward for one painting."""
    model = scorer()
    if model is None:
        return {"score": 0.0, "available": False, "error": _error}
    from PIL import Image

    png = base64.b64decode(request.png_base64)
    path = "/tmp/submission.png"
    Image.open(io.BytesIO(png)).save(path)
    try:
        value = model.reward([path], [request.prompt])[0]
        # Two numbers per image, not one: HPSv3 predicts a distribution, so it is
        # mu and sigma. Measured on our reference pool at 448x448, mu runs from
        # -9.2 on the `meh` tier to +5.2 on `love`, with no overlap between them.
        while isinstance(value, (list, tuple)) and len(value) == 1:
            value = value[0]
        flat = [
            float(x)
            for x in (value.flatten().tolist() if hasattr(value, "flatten") else list(value))
        ]
        mu = flat[0]
        return {
            "mu": mu,
            "sigma": flat[1] if len(flat) > 1 else None,
            # A logistic, so the caller gets something in [0, 1] with no clipping
            # and no hard calibration to a pool that will change. Zero is the
            # natural centre of a Bradley-Terry reward, and a scale of 4 puts the
            # measured tiers at 0.13 for `meh` and 0.70 for `love`.
            "score": 1.0 / (1.0 + math.exp(-mu / 4.0)),
            "available": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {"score": 0.0, "available": False, "error": f"{type(exc).__name__}: {exc}"}
