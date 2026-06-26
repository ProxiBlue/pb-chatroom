FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system .

EXPOSE 7476

HEALTHCHECK --interval=10s --timeout=3s \
    CMD curl -fsS http://127.0.0.1:7476/healthz || exit 1

CMD ["uvicorn", "pb_chatroom.app:app", "--host", "0.0.0.0", "--port", "7476"]
