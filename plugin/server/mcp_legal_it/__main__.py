"""Entry point: python -m mcp_legal_it"""

import sys

from mcp_legal_it._profilo import ProfiloSconosciuto

try:
    from mcp_legal_it.server import mcp
except ProfiloSconosciuto as exc:  # an unknown LEGAL_PROFILE: a message, not a traceback
    sys.exit(f"mcp-legal-it: {exc}")

mcp.run(transport="stdio")
