#!/usr/bin/env python3
"""Web UI entry point for ArduCLI. Opens at http://localhost:8080"""

from interfaces.web_interface import WebInterface
from models import ConnectionConfig

# Route registration must happen at module level so NiceGUI reload works.
# The subprocess re-imports this module with __name__ == "__mp_main__",
# which re-registers routes before ui.run() is called.
_iface = WebInterface(ConnectionConfig(baud_rate=57600, timeout=2, auto_connect=True))
_iface.register_routes()

if __name__ in {"__main__", "__mp_main__"}:
    _iface.run(reload=True)
