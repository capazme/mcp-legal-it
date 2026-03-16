"""Entry point: python -m src"""

from src.server import mcp

mcp.run(transport="stdio")
