# syntax=docker/dockerfile:1
#
# Wordle ORS Environment Server
# Pure Python — no E2B or external sandbox needed.
#
# Build (from wordle/ directory):
#   docker build -f ors/Dockerfile -t wordle-ors .
#
# Run:
#   docker run -p 8080:8080 wordle-ors

# -- Stage 1: Builder --------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY ors/pyproject.toml ./
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache \
        "openreward>=0.1.33" \
        "pydantic>=2.0.0"

# -- Stage 2: Runtime --------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy shared game logic + server
COPY game.py .
COPY ors/server.py .
COPY ors/__init__.py .

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

EXPOSE 8080

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8080"]
