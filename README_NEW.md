# ArduCLI - ArduPilot Configuration & Testing Tool

A Python-based command-line interface for managing ArduPilot flight controller parameters and configuration testing.

## Architecture

The codebase has been refactored with clean separation of concerns:

```
arducli/
├── models/              # Data structures
│   ├── device_info.py   # Device information model
│   └── connection_config.py  # Connection configuration
├── services/            # Business logic layer
│   ├── connection_service.py  # Connection management
│   ├── parameter_service.py   # Parameter operations
│   └── mavlink_service.py     # Main MAVLink orchestration
├── interfaces/          # User interfaces
│   ├── cli_interface.py       # Command-line interface
│   └── tui_interface.py       # Terminal UI (Textual)
├── constants/           # Constants and enumerations
│   ├── mav.py          # MAVLink type definitions
│   └── rc_option.py    # RC option constants
├── main.py             # CLI entry point
└── tui.py              # TUI entry point
```

## Features

- **Auto-discovery**: Automatically scans and connects to ArduPilot devices
- **Connection Management**: Smart port detection with last-used port prioritization
- **Parameter Operations**: Read, write, and search flight controller parameters
- **Multiple Interfaces**: CLI (command-line) and TUI (full-screen terminal UI)
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Modern UI**: TUI built with Textual for rich terminal experience

## Installation

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Start

**CLI Mode** (Command-line):
```bash
python main.py
```

**TUI Mode** (Full-screen terminal UI):
```bash
python tui.py
```

Both interfaces automatically scan for and connect to ArduPilot devices.

### CLI Commands

- **connect [port]** - Connect to a flight controller (auto-detects if no port specified)
- **disconnect** - Disconnect from the flight controller
- **info** - Display device information
- **get <param>** - Get parameter value (supports regex patterns)
- **set <param> <value>** - Set parameter value
- **dump** - Display all parameters
- **save [file]** - Save parameters to file (default: parameters.txt)
- **help** - Show available commands
- **exit/quit** - Exit the application

### TUI Features

The Terminal UI provides a rich, interactive experience:

- **Real-time Status**: Visual connection status indicator
- **Parameter Table**: Sortable, searchable table with zebra striping
- **Live Filtering**: Type to filter parameters (supports regex)
- **Keyboard Shortcuts**:
  - `q` - Quit application
  - `c` - Connect to device
  - `r` - Refresh parameters
  - `s` - Focus search/filter input
  - `Tab` - Navigate between widgets
- **Mouse Support**: Click buttons and scroll through parameters

### CLI Examples

```bash
# Get a specific parameter
get SYSID_THISMAV

# Get all parameters matching a pattern
get RC[0-9]+_OPTION

# Set a parameter
set SYSID_THISMAV 1

# Save parameters to file
save my_params.txt
```

## Extending the Application

### Adding a New Interface

Create a new interface in `interfaces/`. The TUI is a great example:

```python
from textual.app import App
from services import MAVLinkService
from models import ConnectionConfig

class MyInterface(App):
    def __init__(self, config: ConnectionConfig = None):
        super().__init__()
        self.mavlink_service = MAVLinkService(config)

    def compose(self):
        # Your UI layout
        pass
```

See `interfaces/tui_interface.py` for a complete example of building a full-screen terminal UI.

### Adding New Services

Services should inherit from or use the existing service layer:

```python
from services import MAVLinkService

class ConfigTestService:
    def __init__(self, mavlink_service: MAVLinkService):
        self.mavlink = mavlink_service

    def test_configuration(self):
        # Your testing logic
        pass
```

## Development

The architecture separates:
- **Models**: Data structures and types
- **Services**: Business logic (platform-independent where possible)
- **Interfaces**: User interaction layer (CLI, GUI, API, etc.)

This allows you to:
1. Swap out the CLI for a GUI or web interface
2. Use the services in automated testing scripts
3. Build configuration testing tools on top of the service layer

## Platform Notes

- **Serial Port Detection**: Uses `pyserial` for cross-platform port enumeration
- **MAVLink Protocol**: Handled by `pymavlink` library
- **Path Handling**: Uses `os.path.expanduser()` for cross-platform home directory access

## License

See LICENSE file for details.
