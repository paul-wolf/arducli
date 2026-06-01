"""Terminal User Interface using Textual."""

import asyncio
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
)

from models import ConnectionConfig
from services import MAVLinkService


class ConnectionStatus(Static):
    """Widget to display connection status."""

    def __init__(self, **kwargs):
        super().__init__("✗ Not connected", **kwargs)
        self.add_class("disconnected")

    def update_status(self, connected: bool, device_info=None):
        """Update the connection status display."""
        if connected:
            if device_info:
                # Show detailed info with version
                parts = [f"✓ {device_info.vehicle_name}"]
                if device_info.firmware_version:
                    parts.append(f"v{device_info.firmware_version}")
                parts.append(f"({device_info.autopilot_name})")
                if device_info.board_type:
                    parts.append(f"[{device_info.board_type}]")
                parts.append(f"@ {device_info.port}")
                parts.append(f"SysID:{device_info.system_id}")
                text = " ".join(parts)
            else:
                text = "✓ Connected"
            self.update(text)
            self.add_class("connected")
            self.remove_class("disconnected")
        else:
            self.update("✗ Not connected")
            self.add_class("disconnected")
            self.remove_class("connected")


class ParameterTable(DataTable):
    """Widget to display parameters in a table."""

    def populate_parameters(self, parameters: dict):
        """Populate the table with parameters."""
        self.clear(columns=True)
        self.add_column("Parameter", width=30)
        self.add_column("Value", width=20)

        for param_name, param_value in sorted(parameters.items()):
            self.add_row(param_name, str(param_value))


class TelemetryDisplay(Static):
    """Widget to display real-time telemetry data."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.update_display()

    def _draw_artificial_horizon(self, roll: float, pitch: float) -> str:
        """Draw a simple ASCII artificial horizon."""
        # Limit angles for display
        pitch = max(-30, min(30, pitch))
        roll = max(-45, min(45, roll))

        # Create 7x7 grid
        lines = []
        for row in range(7):
            line_chars = []
            for col in range(7):
                # Calculate position relative to center
                y = (3 - row) * 10  # Center is row 3
                x = (col - 3) * 10  # Center is col 3

                # Apply pitch offset and roll tilt
                horizon_y = pitch + (x * roll / 45.0)

                # Determine sky or ground
                if y > horizon_y:
                    line_chars.append("░")  # Sky
                else:
                    line_chars.append("▓")  # Ground
            lines.append("".join(line_chars))

        # Add center marker
        lines[3] = lines[3][:3] + "+" + lines[3][4:]

        return "\n".join(lines)

    def update_display(
        self,
        gps_status: str = "No GPS",
        battery_voltage: float = 0.0,
        battery_current: float = 0.0,
        battery_remaining: int = 0,
        heading: float = 0.0,
        roll: float = 0.0,
        pitch: float = 0.0,
        armed: bool = False,
        mode: str = "UNKNOWN",
    ):
        """Update the telemetry display."""
        armed_status = "ARMED" if armed else "DISARMED"
        armed_color = "red" if armed else "green"

        horizon = self._draw_artificial_horizon(roll, pitch)

        # Two column layout: horizon | data
        text = f"""[bold]TELEMETRY[/bold]

{horizon}  HDG: {heading:.0f}°
R:{roll:+5.1f}°      GPS: {gps_status}
P:{pitch:+5.1f}°
           BAT: {battery_voltage:.1f}V {battery_current:.1f}A ({battery_remaining}%)

           MODE: {mode}
           [{armed_color}]{armed_status}[/{armed_color}]
"""
        self.update(text)


class MessageDisplay(VerticalScroll):
    """Widget to display MAVLink messages."""

    def compose(self) -> ComposeResult:
        """Compose the message log."""
        yield RichLog(highlight=True, markup=True, id="msg-log")

    def add_messages(self, messages: list):
        """Add messages to the display."""
        try:
            log = self.query_one("#msg-log", RichLog)
        except Exception:
            return

        # Clear and repopulate (we could optimize this later)
        log.clear()

        for severity, text in messages:
            # Color code by severity
            if severity in ["EMERGENCY", "ALERT", "CRITICAL"]:
                color = "red"
            elif severity == "ERROR":
                color = "orange1"
            elif severity == "WARNING":
                color = "yellow"
            elif severity == "NOTICE":
                color = "cyan"
            else:  # INFO, DEBUG
                color = "white"

            log.write(f"[{color}][{severity}][/{color}] {text}")


class CommandPanel(VerticalScroll):
    """Widget for testing commands."""

    def __init__(self, mavlink_service: MAVLinkService, **kwargs):
        super().__init__(**kwargs)
        self.mavlink_service = mavlink_service

    def compose(self) -> ComposeResult:
        """Compose the command panel."""
        yield Label("[bold]TEST RESULTS[/bold]")
        with Container(id="test-log-container"):
            yield RichLog(id="test-log", highlight=True, markup=True)

        yield Label("")  # Spacer
        yield Label("[bold]MOTOR TEST[/bold]")
        yield Label("⚠️  Remove props first!")

        with Horizontal():
            yield Label("Motor:")
            yield Select(
                [(f"Motor {i}", i) for i in range(1, 9)] + [("All Motors", 0)],
                id="motor-select",
                value=1,
            )

        with Horizontal():
            yield Label("Throttle %:")
            yield Input(placeholder="5-15", id="throttle-input", value="10")

        with Horizontal():
            yield Label("Duration (s):")
            yield Input(placeholder="1-5", id="duration-input", value="2")

        yield Button("Run Motor Test", id="btn-motor-test", variant="warning")

        yield Label("")  # Spacer
        yield Label("[bold]COMPASS TEST[/bold]")
        with Horizontal():
            yield Button("Check Health", id="btn-compass-check", variant="primary")
            yield Button("Start Cal", id="btn-compass-start", variant="success")
            yield Button("Cancel", id="btn-compass-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-motor-test":
            self.run_motor_test()
        elif event.button.id == "btn-compass-check":
            self.check_compass_health()
        elif event.button.id == "btn-compass-start":
            self.start_compass_calibration()
        elif event.button.id == "btn-compass-cancel":
            self.cancel_compass_calibration()

    def log_test_result(self, message: str, color: str = "white"):
        """Log a test result to the test log."""
        try:
            test_log = self.query_one("#test-log", RichLog)
            test_log.write(f"[{color}]{message}[/{color}]")
        except Exception:
            pass

    def run_motor_test(self):
        """Execute motor test."""
        if not self.mavlink_service.is_connected():
            self.log_test_result("❌ Motor test failed: Not connected", "red")
            return

        try:
            # Get values
            motor_select = self.query_one("#motor-select", Select)
            throttle_input = self.query_one("#throttle-input", Input)
            duration_input = self.query_one("#duration-input", Input)

            motor = int(motor_select.value)
            throttle = int(throttle_input.value)
            duration = float(duration_input.value)

            # Validate
            if throttle < 1 or throttle > 100:
                self.log_test_result("❌ Throttle must be 1-100%", "red")
                return

            if duration < 0.5 or duration > 10:
                self.log_test_result("❌ Duration must be 0.5-10 seconds", "red")
                return

            # Execute
            if motor == 0:
                success = self.mavlink_service.test_all_motors(throttle, duration)
                msg = f"Testing all motors at {throttle}% for {duration}s"
            else:
                success = self.mavlink_service.motor_test(motor, throttle, duration)
                msg = f"Testing motor {motor} at {throttle}% for {duration}s"

            if success:
                self.log_test_result(f"⚠️  {msg}", "yellow")
            else:
                self.log_test_result("❌ Failed to send motor test command", "red")

        except ValueError:
            self.log_test_result("❌ Invalid input values", "red")
        except Exception as e:
            self.log_test_result(f"❌ Error: {e}", "red")

    def start_compass_calibration(self):
        """Start compass calibration."""
        if not self.mavlink_service.is_connected():
            self.log_test_result("❌ Compass cal failed: Not connected", "red")
            return

        try:
            success = self.mavlink_service.start_compass_calibration(autosave=True)
            if success:
                self.log_test_result("🧭 Compass calibration started - rotate vehicle in all orientations", "cyan")
            else:
                self.log_test_result("❌ Failed to start compass calibration", "red")
        except Exception as e:
            self.log_test_result(f"❌ Error: {e}", "red")

    def cancel_compass_calibration(self):
        """Cancel compass calibration."""
        if not self.mavlink_service.is_connected():
            self.log_test_result("❌ Cancel failed: Not connected", "red")
            return

        try:
            success = self.mavlink_service.cancel_compass_calibration()
            if success:
                self.log_test_result("🧭 Compass calibration cancelled", "yellow")
            else:
                self.log_test_result("❌ Failed to cancel compass calibration", "red")
        except Exception as e:
            self.log_test_result(f"❌ Error: {e}", "red")

    def check_compass_health(self):
        """Check compass calibration and health."""
        if not self.mavlink_service.is_connected():
            self.log_test_result("❌ Compass check failed: Not connected", "red")
            return

        try:
            self.log_test_result("🧭 Checking compass health...", "cyan")

            # Get compass offsets
            offsets = self.mavlink_service.get_compass_offsets()

            # Get current telemetry
            telem = self.mavlink_service.get_telemetry()

            # Check if calibrated
            if offsets.get("calibrated"):
                self.log_test_result("✓ Compass is calibrated", "green")
                self.log_test_result(
                    f"  Offsets: X={offsets.get('COMPASS_OFS_X', 0):.0f} "
                    f"Y={offsets.get('COMPASS_OFS_Y', 0):.0f} "
                    f"Z={offsets.get('COMPASS_OFS_Z', 0):.0f}",
                    "white",
                )
            else:
                self.log_test_result("✗ Compass NOT calibrated (offsets are 0,0,0)", "red")

            # Magnetic field strength
            mag_field = telem.mag_field_strength
            if mag_field > 0:
                # Earth's magnetic field is typically 250-650 milligauss
                if 200 < mag_field < 700:
                    self.log_test_result(f"✓ Mag field: {mag_field:.0f} mG (normal)", "green")
                else:
                    self.log_test_result(f"⚠️  Mag field: {mag_field:.0f} mG (check for interference)", "yellow")
            else:
                self.log_test_result("⚠️  Mag field: No data available", "yellow")

        except Exception as e:
            self.log_test_result(f"❌ Error checking compass: {e}", "red")


class ParameterScreen(Screen):
    """Main parameter management screen."""

    CSS = """
    ParameterScreen {
        layout: vertical;
    }

    ConnectionStatus {
        height: 5;
        border: solid $primary;
        padding: 1;
        margin: 1;
        content-align: center middle;
        text-style: bold;
    }

    ConnectionStatus.connected {
        border: solid green;
        background: $surface;
        color: $text;
    }

    ConnectionStatus.disconnected {
        border: solid red;
        background: $surface;
        color: $text;
    }

    #controls {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin: 1;
        align: left middle;
    }

    #filter-section {
        width: 1fr;
        height: auto;
    }

    #button-row {
        height: auto;
        width: auto;
        align: right middle;
    }

    #main-content {
        height: 1fr;
    }

    #parameter-container {
        width: 2fr;
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }

    #telemetry-container {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        margin: 1;
        padding: 1;
    }

    #commands-container {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }

    ParameterTable {
        height: 1fr;
    }

    TelemetryDisplay {
        width: 100%;
        height: 100%;
    }

    CommandPanel {
        width: 100%;
        height: 100%;
    }

    CommandPanel Input {
        width: 10;
    }

    CommandPanel Select {
        width: 15;
    }

    CommandPanel Label {
        margin: 0 1 0 0;
    }

    #test-log-container {
        height: 10;
        border: solid $primary;
        margin: 1 0;
    }

    #test-log {
        height: 100%;
    }

    #messages-container {
        width: 100%;
        height: 10;
        border: solid $primary;
        margin: 1;
    }

    MessageDisplay {
        width: 100%;
        height: 100%;
    }

    Button {
        margin: 0 1;
    }

    Input {
        margin: 0;
    }

    Label {
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("s", "search", "Search"),
        ("c", "connect", "Connect"),
    ]

    def __init__(self, mavlink_service: MAVLinkService):
        super().__init__()
        self.mavlink_service = mavlink_service

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        with Container():
            yield ConnectionStatus(id="status")

            with Horizontal(id="controls"):
                with Vertical(id="filter-section"):
                    yield Label("Filter Parameters:")
                    yield Input(placeholder="Type to filter (e.g., RC.*_OPTION)", id="filter-input")

                with Horizontal(id="button-row"):
                    yield Button("Connect", id="btn-connect", variant="primary")
                    yield Button("Refresh", id="btn-refresh", variant="success")
                    yield Button("Load All", id="btn-load", variant="warning")

            with Horizontal(id="main-content"):
                with Container(id="parameter-container"):
                    yield ParameterTable(id="param-table", zebra_stripes=True)

                with Vertical():
                    with Container(id="telemetry-container"):
                        yield TelemetryDisplay(id="telemetry")

                    with Container(id="commands-container"):
                        yield CommandPanel(self.mavlink_service, id="commands")

            with Container(id="messages-container"):
                yield MessageDisplay(id="messages")

        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.update_connection_status()

        # If already connected, start telemetry
        if self.mavlink_service.is_connected():
            try:
                self.mavlink_service.start_telemetry()
            except Exception:
                pass

            if self.mavlink_service.has_parameters():
                self.load_parameters()

        # Start telemetry updates
        self.set_interval(0.5, self.update_telemetry_display)

    def update_connection_status(self):
        """Update the connection status widget."""
        status_widget = self.query_one("#status", ConnectionStatus)
        device_info = self.mavlink_service.get_device_info()
        status_widget.update_status(self.mavlink_service.is_connected(), device_info)

    def update_telemetry_display(self):
        """Update the telemetry display with current data."""
        try:
            if not self.mavlink_service.is_connected():
                return

            # Update telemetry data from MAVLink
            self.mavlink_service.update_telemetry()

            # Get telemetry data
            telem = self.mavlink_service.get_telemetry()
            gps_status = self.mavlink_service.get_gps_status()

            # Update the display
            telemetry_widget = self.query_one("#telemetry", TelemetryDisplay)
            telemetry_widget.update_display(
                gps_status=gps_status,
                battery_voltage=telem.battery_voltage,
                battery_current=telem.battery_current,
                battery_remaining=telem.battery_remaining,
                heading=telem.heading,
                roll=telem.roll,
                pitch=telem.pitch,
                armed=telem.armed,
                mode=telem.mode,
            )

            # Update messages
            messages = self.mavlink_service.get_messages(limit=50)
            message_widget = self.query_one("#messages", MessageDisplay)
            message_widget.add_messages(messages)
        except Exception as e:
            # Log error but don't crash
            self.app.log(f"Telemetry update error: {e}")

    @on(Button.Pressed, "#btn-connect")
    def handle_connect(self):
        """Handle connect button press."""
        if self.mavlink_service.is_connected():
            self.notify("Already connected", severity="information")
        else:
            self.connect_to_device()

    @on(Button.Pressed, "#btn-refresh")
    def handle_refresh(self):
        """Handle refresh button press."""
        if not self.mavlink_service.is_connected():
            self.notify("Not connected to a device", severity="error")
            return
        self.load_parameters()

    @on(Button.Pressed, "#btn-load")
    def handle_load_all(self):
        """Handle load all button press."""
        if not self.mavlink_service.is_connected():
            self.notify("Not connected to a device", severity="error")
            return
        self.load_parameters()

    @on(Input.Changed, "#filter-input")
    def handle_filter(self, event: Input.Changed):
        """Handle filter input changes."""
        filter_text = event.value.strip().upper()
        table = self.query_one("#param-table", ParameterTable)

        if not filter_text:
            # Show all parameters
            params = self.mavlink_service.get_all_parameters()
            table.populate_parameters(params)
        else:
            # Filter parameters
            try:
                params = self.mavlink_service.get_parameters_matching(filter_text)
                table.populate_parameters(params)
            except Exception:
                # If regex fails, do simple substring match
                all_params = self.mavlink_service.get_all_parameters()
                filtered = {k: v for k, v in all_params.items() if filter_text in k}
                table.populate_parameters(filtered)

    @work(exclusive=True)
    async def connect_to_device(self):
        """Connect to a device asynchronously."""
        self.notify("Scanning for devices...", severity="information")

        def on_progress(message: str):
            self.notify(message, timeout=2)

        # Run connection in a thread
        connected = await asyncio.to_thread(self.mavlink_service.connect, on_progress=on_progress)

        if connected:
            self.update_connection_status()
            self.notify("Connected successfully!", severity="success")
            # Start telemetry stream
            try:
                self.mavlink_service.start_telemetry()
            except Exception:
                pass  # Non-critical
            # Auto-load parameters
            await self.async_load_parameters()
        else:
            self.update_connection_status()
            self.notify("Connection failed", severity="error")

    async def async_load_parameters(self):
        """Load parameters asynchronously."""
        self.notify("Loading parameters...", severity="information")

        def on_progress(current: int, total: int):
            if current % 50 == 0:  # Update every 50 params to avoid spam
                self.notify(f"Loading parameters: {current}/{total}", timeout=1)

        try:
            params = await asyncio.to_thread(self.mavlink_service.load_parameters, on_progress=on_progress)
            table = self.query_one("#param-table", ParameterTable)
            table.populate_parameters(params)
            self.notify(f"Loaded {len(params)} parameters", severity="success")
        except Exception as e:
            self.notify(f"Error loading parameters: {e}", severity="error")

    @work(exclusive=True)
    async def load_parameters(self):
        """Load parameters (for refresh button)."""
        await self.async_load_parameters()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_refresh(self) -> None:
        """Refresh parameters."""
        self.handle_refresh()

    def action_search(self) -> None:
        """Focus the search input."""
        self.query_one("#filter-input", Input).focus()

    def action_connect(self) -> None:
        """Connect to device."""
        self.handle_connect()


class ArduTUI(App):
    """Main Textual application for ArduPilot configuration."""

    TITLE = "ArduCLI - TUI"
    SUB_TITLE = "ArduPilot Configuration Tool"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        super().__init__()
        self.mavlink_service = MAVLinkService(config)

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.push_screen(ParameterScreen(self.mavlink_service))

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        if self.mavlink_service.is_connected():
            self.mavlink_service.disconnect()
