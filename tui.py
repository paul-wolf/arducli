#!/usr/bin/env python3
"""
ArduCLI TUI - Terminal User Interface for ArduPilot configuration.

This is the TUI entry point for the application using Textual.
"""

import sys

from interfaces import ArduTUI
from models import ConnectionConfig


def main():
    """Main entry point for ArduCLI TUI."""
    # Create default configuration
    config = ConnectionConfig(baud_rate=57600, timeout=2, auto_connect=False)

    # Launch TUI interface
    app = ArduTUI(config)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
