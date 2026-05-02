# syntax=docker/dockerfile:1
#
# Wordle NeMo Gym Resources Server
# Pure Python — no E2B or external sandbox needed.
#
# Build (from wordle/ directory):
#   docker build -f nemo_gym/Dockerfile -t wordle-nemo-gym .
#
# Run:
#   docker run -p 11000:11000 wordle-nemo-gym

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY nemo_gym/pyproject.toml ./
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache \
        "nemo_gym @ git+https://github.com/NVIDIA-NeMo/Gym" \
        "pydantic>=2.0.0"

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy shared game logic + server
COPY game.py .
COPY nemo_gym/server.py .
COPY nemo_gym/__init__.py .

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:11000/health')" || exit 1

EXPOSE 11000
CMD ["python", "server.py"]
