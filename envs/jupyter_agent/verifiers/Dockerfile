# Verifiers runs IN-PROCESS — no separate Docker container needed.
# Install deps in the training venv instead:
#   pip install verifiers e2b-code-interpreter
#
# This Dockerfile is for standalone testing only:
#   docker build -t jupyter-agent-verifiers .
#   docker run -e E2B_API_KEY=... jupyter-agent-verifiers python -c "from env import JupyterToolkit; print('OK')"

FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir verifiers e2b-code-interpreter python-dotenv
COPY *.py ./
CMD ["python", "-c", "from env import JupyterToolkit; tk=JupyterToolkit(); print('Verifiers env ready')"]
