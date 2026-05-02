# syntax=docker/dockerfile:1
#
# Jupyter Agent NeMo Gym Resources Server
#
# Build:
#   docker build -t jupyter-agent-nemo-gym .
#
# Run:
#   docker run -p 11000:11000 -e E2B_API_KEY=... jupyter-agent-nemo-gym

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache \
        "nemo_gym @ git+https://github.com/NVIDIA-NeMo/Gym" \
        "e2b-code-interpreter>=1.0.0" \
        "pydantic>=2.0.0" \
        "python-dotenv>=1.0.0"

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY server.py tasks.py e2b_sandbox.py notebook_tracker.py __init__.py ./
COPY configs/ configs/

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:11000/health')" || exit 1

EXPOSE 11000
CMD ["python", "server.py"]
