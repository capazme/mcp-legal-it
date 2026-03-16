#!/usr/bin/env python3
"""Entry point for MCP server — supports stdio and SSE transports.

Transport is selected via MCP_TRANSPORT env var (default: stdio).
For SSE, MCP_HOST, MCP_PORT, and MCP_PATH_PREFIX control the server.

Path prefix is propagated to FastMCP via FASTMCP_SSE_PATH and
FASTMCP_MESSAGE_PATH env vars (native pydantic-settings support).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Derive FastMCP path settings from MCP_PATH_PREFIX before importing server
# (FastMCP reads env vars at Settings instantiation time)
prefix = os.environ.get("MCP_PATH_PREFIX", "").rstrip("/")
if prefix:
    os.environ.setdefault("FASTMCP_SSE_PATH", f"{prefix}/sse")
    os.environ.setdefault("FASTMCP_MESSAGE_PATH", f"{prefix}/messages/")

from src.server import mcp  # noqa: E402

transport = os.environ.get("MCP_TRANSPORT", "stdio")

if transport == "sse":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))

    # Mount /health endpoint for liveness probes
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    async def health(request):
        return PlainTextResponse("ok")

    sse_app = mcp.sse_app()
    app = Starlette(
        routes=[Route("/health", health)],
        on_startup=sse_app.router.on_startup,
        on_shutdown=sse_app.router.on_shutdown,
    )
    app.mount("/", sse_app)

    import uvicorn
    uvicorn.run(app, host=host, port=port)
else:
    mcp.run(transport="stdio")
