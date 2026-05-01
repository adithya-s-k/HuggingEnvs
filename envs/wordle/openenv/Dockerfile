# syntax=docker/dockerfile:1
#
# Wordle OpenEnv MCP Server
# Pure Python — no E2B or external sandbox needed.
#
# Build (from wordle/ directory):
#   docker build -f openenv/Dockerfile -t wordle-openenv .
#
# Run:
#   docker run -p 8002:8002 wordle-openenv

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY openenv/pyproject.toml ./
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache \
        "fastmcp>=0.1.0" \
        "fastapi>=0.100.0" \
        "uvicorn>=0.20.0"

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy shared game logic + server
COPY game.py .
COPY openenv/server/app.py ./server/app.py
COPY openenv/__init__.py .

EXPOSE 8002

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8002"]
