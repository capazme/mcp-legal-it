"""Entry point: python -m mcp_legal_it"""

from mcp_legal_it.server import mcp

mcp.run(transport="stdio")
