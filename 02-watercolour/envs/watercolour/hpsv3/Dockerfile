FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Every cache under /app, because the container's home is not writable and the
# libraries do not agree on which variable to read. Triton in particular ignores
# HF_HOME and falls back to $HOME/.triton, which resolved to /.triton and made
# every scoring request fail with a permission error *after* the model had loaded
# fine, so `/health` reported ready while nothing worked.
ENV HOME=/app
ENV HF_HOME=/app/.cache
ENV XDG_CACHE_HOME=/app/.cache
ENV TRITON_CACHE_DIR=/app/.cache/triton
ENV TORCHINDUCTOR_CACHE_DIR=/app/.cache/inductor
ENV MPLCONFIGDIR=/app/.cache/matplotlib
RUN mkdir -p /app/.cache/triton /app/.cache/inductor /app/.cache/matplotlib \
    && chmod -R 777 /app/.cache

COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
