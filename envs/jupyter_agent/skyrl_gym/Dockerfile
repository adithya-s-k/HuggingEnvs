# SkyRL Gym runs IN-PROCESS — no separate Docker container needed.
# Install deps in the training venv instead:
#   pip install skyrl-gym e2b-code-interpreter
#
# This Dockerfile is for standalone testing only.

FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir skyrl-gym e2b-code-interpreter python-dotenv
COPY *.py ./
CMD ["python", "-c", "from env import JupyterTextEnv; print('SkyRL Gym env ready')"]
