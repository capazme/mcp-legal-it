FROM python:3.12-slim AS base
WORKDIR /app

# System deps for lxml (C compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Replicate plugin/server structure expected by run_server.py
COPY plugin/server/src/ plugin/server/src/
COPY plugin/server/run_server.py plugin/server/run_server.py
COPY run_server.py .

ENV LEGAL_PROFILE=full
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
EXPOSE 8000

# Cache and temp directories
RUN mkdir -p /app/.cache/mcp-legal-it /tmp/mcp-legal-it
ENV MCP_CACHE_DIR=/app/.cache/mcp-legal-it

CMD ["python", "run_server.py"]
