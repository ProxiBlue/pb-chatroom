FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system .

EXPOSE 7477

HEALTHCHECK --interval=10s --timeout=3s \
    CMD curl -fsS --max-time 2 http://127.0.0.1:7477/ > /dev/null 2>&1 || exit 0

CMD ["python", "-m", "pb_chatroom_mcp.server"]
