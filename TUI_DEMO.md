# TUI Demo Instructions

## Launch the TUI

```bash
python tui.py
```

## What You'll See

### Header
- Application title: "ArduCLI - TUI"
- Subtitle: "ArduPilot Configuration Tool"

### Connection Status Box
- Shows "✗ Not connected" in red when disconnected
- Shows "✓ Connected: [device info]" in green when connected

### Controls Section
- **Filter Input**: Type regex patterns to filter parameters (e.g., `RC.*_OPTION`, `SYSID.*`)
- **Connect Button**: Auto-scan and connect to flight controller
- **Refresh Button**: Reload parameters from connected device
- **Load All Button**: Force reload all parameters

### Parameter Table
- Displays all parameters in two columns: Parameter | Value
- Zebra striping for easy reading
- Scrollable with mouse or arrow keys
- Auto-updates when filtering

### Footer
- Shows available keyboard shortcuts

## Usage Flow

1. **Launch**: `python tui.py`
2. **Connect**: Press 'c' or click "Connect" button
   - App scans serial ports automatically
   - Shows progress notifications
   - Displays device info when connected
3. **View Parameters**: Auto-loads after connection
   - Scroll through the table
   - Watch the notifications for progress
4. **Filter**: Press 's' to focus filter input
   - Type `RC` to see all RC parameters
   - Type `SYSID.*` to see system ID parameters
   - Type `ARMING.*` for arming parameters
5. **Refresh**: Press 'r' to reload from device
6. **Quit**: Press 'q' to exit

## Without Hardware

If you don't have a flight controller connected:
- The TUI will launch but show "Not connected"
- You can still explore the interface
- Click Connect to see the port scanning in action
- It will gracefully handle no devices found

## Features Demonstrated

- **Async operations**: Connect and load parameters without blocking UI
- **Reactive UI**: Status updates in real-time
- **Notifications**: Toast messages for user feedback
- **Keyboard navigation**: Full keyboard control
- **Mouse support**: Click and scroll
- **Live filtering**: Instant parameter search
- **Cross-platform**: Works on Windows, macOS, Linux

## Architecture Highlight

The TUI uses the **exact same** `MAVLinkService` as the CLI!
- No code duplication
- Shared business logic
- Different presentation layer only
- Easy to add more interfaces (web, GUI, etc.)
