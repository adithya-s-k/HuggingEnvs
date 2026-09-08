# SPDX-License-Identifier: BSD-3-Clause

"""Perspective views out of an equirectangular panorama.

`look()` is a gnomonic reprojection: build a camera ray for every output
pixel, rotate it by the requested heading and pitch, convert to spherical
coordinates and sample the source image. Integer sampling keeps it
deterministic — the same arguments always produce the same bytes, which is
what lets a GRPO group share one starting observation.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image


DEFAULT_SIZE = (640, 640)


def look(
    pano: Image.Image,
    heading_deg: float,
    pitch_deg: float = 0.0,
    fov_deg: float = 90.0,
    size: tuple[int, int] = DEFAULT_SIZE,
) -> Image.Image:
    """
    Render one perspective view out of an equirectangular panorama.

    Args:
        pano (`PIL.Image.Image`):
            Source panorama, 2:1 equirectangular.
        heading_deg (`float`):
            Compass heading in degrees, `0` being the panorama's own north.
        pitch_deg (`float`, *optional*, defaults to `0.0`):
            Vertical angle in degrees; positive looks up.
        fov_deg (`float`, *optional*, defaults to `90.0`):
            Horizontal field of view. Smaller values zoom in.
        size (`tuple[int, int]`, *optional*, defaults to `(640, 640)`):
            Output width and height in pixels.

    Returns:
        `PIL.Image.Image`: The rendered view.

    Examples:

    ```python
    view = look(Image.open("pano.jpg"), heading_deg=90, fov_deg=30)
    ```
    """
    src = np.asarray(pano.convert("RGB"))
    src_h, src_w = src.shape[:2]
    width, height = size

    focal = 0.5 * width / np.tan(np.radians(fov_deg) / 2)
    xs, ys = np.meshgrid(np.arange(width) - width / 2, np.arange(height) - height / 2)
    rays = np.stack([xs, -ys, np.full_like(xs, focal, dtype=float)], axis=-1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)

    pitch, heading = np.radians(pitch_deg), np.radians(heading_deg)
    rot_x = np.array(
        [
            [1, 0, 0],
            [0, np.cos(pitch), -np.sin(pitch)],
            [0, np.sin(pitch), np.cos(pitch)],
        ]
    )
    rot_y = np.array(
        [
            [np.cos(heading), 0, np.sin(heading)],
            [0, 1, 0],
            [-np.sin(heading), 0, np.cos(heading)],
        ]
    )
    rays = rays @ rot_x.T @ rot_y.T

    lon = np.arctan2(rays[..., 0], rays[..., 2])
    lat = np.arcsin(np.clip(rays[..., 1], -1.0, 1.0))
    u = ((lon / (2 * np.pi) + 0.5) * src_w).astype(np.int32) % src_w
    v = np.clip(((0.5 - lat / np.pi) * src_h).astype(np.int32), 0, src_h - 1)
    return Image.fromarray(src[v, u])


def to_base64(image: Image.Image, fmt: str = "JPEG", quality: int = 85) -> str:
    """
    Encode an image for transport inside an observation.

    Args:
        image (`PIL.Image.Image`):
            Image to encode.
        fmt (`str`, *optional*, defaults to `"JPEG"`):
            Pillow format name. Views use JPEG; maps use PNG.
        quality (`int`, *optional*, defaults to `85`):
            JPEG quality, ignored for PNG.

    Returns:
        `str`: Base64-encoded image bytes, without a data URI prefix.
    """
    buf = io.BytesIO()
    if fmt.upper() == "JPEG":
        image.save(buf, format="JPEG", quality=quality, optimize=True)
    else:
        image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")
