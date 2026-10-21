FROM python:3.12-slim AS base
WORKDIR /app

# System deps for lxml (C compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

# The package lives in plugin/server/ (see pyproject.toml); install it as the
# wheel would, so the image runs the same `mcp-legal-it` entry point as uvx.
COPY pyproject.toml LICENSE NOTICE ./
COPY LICENSES/ LICENSES/
COPY plugin/server/mcp_legal_it/ plugin/server/mcp_legal_it/
RUN pip install --no-cache-dir . && rm -rf plugin build

ENV LEGAL_PROFILE=full
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp
EXPOSE 8000

# An unprivileged user owns the cache. The generators create their own 0700
# output folder under /tmp at the first document (a folder pre-created here by
# root would be refused as not ours).
RUN useradd --system --uid 10001 --home-dir /app legal \
    && mkdir -p /app/.cache/mcp-legal-it \
    && chown -R legal /app/.cache
ENV MCP_CACHE_DIR=/app/.cache/mcp-legal-it
USER legal

CMD ["mcp-legal-it"]
