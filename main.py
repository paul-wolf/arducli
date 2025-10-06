#!/usr/bin/env python3
"""
ArduCLI - Command-line interface for ArduPilot configuration and testing.

This is the main entry point for the application.
"""

import sys

from interfaces import CLIInterface
from models import ConnectionConfig


def main():
    """Main entry point for ArduCLI."""
    # Create default configuration
    config = ConnectionConfig(baud_rate=57600, timeout=2, auto_connect=True)

    # Launch CLI interface
    cli = CLIInterface(config)
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
