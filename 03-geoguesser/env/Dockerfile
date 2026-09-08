# syntax=docker/dockerfile:1
#
# Hugging Face Space image for the GeoGuesser environment.
#
# Self-contained on purpose: it inlines the OpenEnv base image's steps rather
# than building `FROM openenv-base:latest`, a locally built tag that does not
# resolve on the Hub. It also vendors
# `src/openenv` rather than installing a release, so the Space runs exactly the
# core this checkout runs -- the Gradio tab naming this environment relies on is
# newer than the published package.
#
# Imagery is NOT in the image: 22 GB cannot fit, and Space disk is ephemeral.
# It arrives through a Storage Bucket mounted read-only at /data.

# 3.12 to match the interpreter this environment is developed and tested on.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pinned to the exact versions this environment is verified against locally,
# not to the pyproject floors. Floors would let the Space drift onto a different
# fastmcp or gradio major than the one the tests ran on, and those two are
# precisely where the MCP tool surface and the play tab would break.
RUN pip install --no-cache-dir \
        "fastapi==0.136.1" \
        "pydantic==2.13.3" \
        "uvicorn==0.46.0" \
        "requests==2.33.1" \
        "typer==0.25.0" \
        "rich==15.0.0" \
        "pyyaml==6.0.3" \
        "huggingface_hub==1.12.2" \
        "websockets==15.0.1" \
        "fastmcp==3.2.4" \
        "gradio==6.13.0" \
        "httpx==0.28.1" \
        "pillow==12.2.0" \
        "numpy==2.4.4" \
        "matplotlib==3.11.1" \
        "tomli>=2.3.0" \
        "tomli-w>=1.2.0" \
        "typing_extensions>=4.0.0"

COPY src /app/src
# As a package directory, not a bare source root. Modules inside do
# `from ..models import ...`, which only resolves when `geoguesser_env` itself
# is the package -- with the sources at a bare source root and PYTHONPATH
# pointing there, `server` becomes top-level and those imports fail with
# "attempted relative
# import beyond top-level package".
COPY geoguesser_env /app/geoguesser_env

ENV PYTHONPATH=/app:/app/src

# The web UI is off in core by default; without this the Space serves a 404 at
# /web and looks broken.
ENV ENABLE_WEB_INTERFACE=true

# Defaults for a Space with the bucket mounted at /data. Space variables
# override these, but baking them in means the image is correct on its own.
ENV GEOGUESSER_TASKS_EVAL=/data/tasks/eval_pano_v3.jsonl \
    GEOGUESSER_TASKS_TRAIN=/data/tasks/train_pano_v3.jsonl \
    GEOGUESSER_DEFAULT_SPLIT=train \
    GEOGUESSER_CACHE=/data/panos \
    GEOGUESSER_ALLOW_FETCH=0 \
    GEOGUESSER_STREET_DETAIL=1 \
    GEOGUESSER_INDEX=/app/geoguesser_env/tasks/eval_pano_v3.jsonl

# Overpass results cache here, on the container's own writable disk, which is
# why street labels work even with Mapillary fetching disabled.
RUN mkdir -p /app/geoguesser_env/data/geo/osm_cache /app/geoguesser_env/data/panos \
    && chmod -R 777 /app/geoguesser_env/data

EXPOSE 8000
CMD ["uvicorn", "geoguesser_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
