# syntax=docker/dockerfile:1
# Multi-stage build for jupyter-agent-openenv
# Follows the same pattern as OpenEnv's echo_env Dockerfile.
#
# Build:
#   docker build -t jupyter-agent-openenv .
#
# Run:
#   docker run -p 8000:8000 \
#     -e E2B_API_KEY=e2b_... \
#     -e ENABLE_WEB_INTERFACE=true \
#     jupyter-agent-openenv

ARG BASE_IMAGE=ghcr.io/meta-pytorch/openenv-base:latest

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

ARG BUILD_MODE=standalone

COPY . /app/env
WORKDIR /app/env

# Ensure uv is available
RUN if ! command -v uv >/dev/null 2>&1; then \
        curl -LsSf https://astral.sh/uv/install.sh | sh && \
        mv /root/.local/bin/uv /usr/local/bin/uv && \
        mv /root/.local/bin/uvx /usr/local/bin/uvx; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (cache-friendly two-pass)
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project --no-editable; \
    else \
        uv sync --no-install-project --no-editable; \
    fi

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv sync --no-editable; \
    fi

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM ${BASE_IMAGE}

WORKDIR /app

COPY --from=builder /app/env/.venv /app/.venv
COPY --from=builder /app/env /app/env

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/env:$PYTHONPATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["sh", "-c", "cd /app/env && uvicorn server.app:app --host 0.0.0.0 --port 8000"]
