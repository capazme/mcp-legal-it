#!/usr/bin/env python3
"""Root entry point — delegates to plugin/server/run_server.py for dev/Docker."""
import os
import sys
import runpy

_server = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin", "server")
sys.path.insert(0, _server)
os.chdir(_server)
runpy.run_path(os.path.join(_server, "run_server.py"), run_name="__main__")
