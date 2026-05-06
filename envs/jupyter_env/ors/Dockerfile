# syntax=docker/dockerfile:1
#
# Jupyter Agent ORS Environment Server
# Deployable to: Docker, HF Spaces, OpenReward (openreward.ai)
#
# Build:
#   docker build -t jupyter-agent-ors .
#
# Run:
#   docker run -p 8080:8080 -e E2B_API_KEY=e2b_xxx jupyter-agent-ors
#
# OpenReward deployment:
#   Push to GitHub → connect on openreward.ai → auto-builds on port 8080

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency spec first (cache-friendly)
COPY pyproject.toml ./

# Install dependencies into a virtual env
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache \
        "openreward>=0.1.33" \
        "e2b-code-interpreter>=1.0.0" \
        "pydantic>=2.0.0" \
        "python-dotenv>=1.0.0"

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Activate venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy application source (only what's needed)
COPY server.py .
COPY tasks.py .
COPY e2b_sandbox.py .
COPY notebook_tracker.py .
COPY __init__.py .

# OpenReward mounts data files here — fallback to inline TASKS if not present
# COPY *.parquet /orwd_data/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

EXPOSE 8080

# Server entrypoint — works both standalone and on OpenReward
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8080"]
