import cmd
from typing import Optional

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completer, Completion
from rich.console import Console
from tqdm import tqdm

from models import ConnectionConfig
from services import MAVLinkService

REGEX_CHARS = "[](){}^$+*?.\\|"

console = Console()


class ParameterCompleter(Completer):
    """Auto-completer for parameter names."""

    def __init__(self, mavlink_service: MAVLinkService):
        self.mavlink_service = mavlink_service

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor().lower()
        params = self.mavlink_service.get_all_parameters()
        for param in params.keys():
            if param.lower().startswith(word):
                yield Completion(param, start_position=-len(word))


class CLIInterface(cmd.Cmd):
    """Command-line interface for ArduPilot configuration."""

    intro = (
        "[green]Welcome to ArduCLI.[/green] "
        "Type [bold]help[/bold] or [bold]?[/bold] to list commands.\n"
        "Press Ctrl-C to exit."
    )
    prompt = HTML("(<ansiyellow>arducli</ansiyellow>) ")

    def __init__(self, config: Optional[ConnectionConfig] = None):
        super().__init__()
        self.mavlink_service = MAVLinkService(config)
        self.session = PromptSession(completer=ParameterCompleter(self.mavlink_service))

    def do_connect(self, arg):
        """Connect to the flight controller by scanning ports and waiting for a heartbeat message."""
        port = arg.strip() if arg.strip() else None

        def on_progress(message: str):
            console.print(message)

        if self.mavlink_service.connect(port, on_progress):
            self._show_device_info()
            self._load_parameters()
        else:
            console.print("[red]Connection failed[/red]")

    def _show_device_info(self):
        """Display information about the connected device."""
        device_info = self.mavlink_service.get_device_info()
        if device_info:
            console.print(f"[green]Connected to: {device_info.description}[/green]")
            console.print(f"System ID: {device_info.system_id}")
            console.print(f"Component ID: {device_info.component_id}")

    def _load_parameters(self):
        """Load parameters with progress bar."""
        console.print("[yellow]Loading parameters...[/yellow]")

        total_params = [0]
        pbar = [None]

        def on_progress(current: int, total: int):
            if total_params[0] == 0:
                total_params[0] = total
                pbar[0] = tqdm(total=total, desc="Loading Parameters", unit="param")
            if pbar[0]:
                pbar[0].update(1)

        try:
            self.mavlink_service.load_parameters(on_progress)
            if pbar[0]:
                pbar[0].close()
            console.print("[green]Parameters loaded successfully[/green]")
        except Exception as e:
            console.print(f"[red]Error loading parameters: {e}[/red]")

    def do_disconnect(self, arg):
        """Disconnect from the flight controller."""
        if self.mavlink_service.is_connected():
            self.mavlink_service.disconnect()
            console.print("[green]Disconnected[/green]")
        else:
            console.print("[yellow]Not connected[/yellow]")

    def do_info(self, arg):
        """Display information about the connected flight controller."""
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        self._show_device_info()

    def do_dump(self, arg):
        """Display all cached parameters."""
        if not self.mavlink_service.has_parameters():
            console.print("[yellow]No parameters loaded[/yellow]")
            return

        params = self.mavlink_service.get_all_parameters()
        for param_id, param_value in sorted(params.items()):
            console.print(f"{param_id}: {param_value}")

    def do_get(self, arg):
        """
        Get parameter value(s).
        Usage: get <PARAM_ID>
               get <REGEX_PATTERN>
        """
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        param_id = arg.strip().upper()
        if not param_id:
            console.print("[red]Please specify a parameter name or pattern[/red]")
            return

        # Check if it's a regex pattern
        if set(param_id) & set(REGEX_CHARS):
            matching_params = self.mavlink_service.get_parameters_matching(param_id)
            if matching_params:
                for key, value in sorted(matching_params.items()):
                    console.print(f"{key}: {value}")
            else:
                console.print(f"[yellow]No parameters match pattern: {param_id}[/yellow]")
        else:
            value = self.mavlink_service.get_parameter(param_id)
            if value is not None:
                console.print(f"{param_id}: {value}")
            else:
                console.print(f"[yellow]Parameter {param_id} not found[/yellow]")

    def complete_get(self, text, line, begidx, endidx):
        """Auto-complete for get command."""
        params = self.mavlink_service.get_all_parameters()
        return [p for p in params.keys() if p.startswith(text.upper())]

    def do_set(self, arg):
        """
        Set a parameter value.
        Usage: set <PARAM_ID> <VALUE>
        """
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        args = arg.split()
        if len(args) != 2:
            console.print("[red]Usage: set <PARAM_ID> <VALUE>[/red]")
            return

        param_id = args[0].upper()
        try:
            param_value = float(args[1])
        except ValueError:
            console.print("[red]Invalid parameter value (must be a number)[/red]")
            return

        if self.mavlink_service.set_parameter(param_id, param_value):
            console.print(f"[green]Parameter {param_id} set to {param_value}[/green]")
        else:
            console.print(f"[red]Failed to set parameter {param_id}[/red]")

    def complete_set(self, text, line, begidx, endidx):
        """Auto-complete for set command."""
        params = self.mavlink_service.get_all_parameters()
        return [p for p in params.keys() if p.startswith(text.upper())]

    def do_save(self, arg):
        """
        Save parameters to a file.
        Usage: save [filename]
        """
        if not self.mavlink_service.has_parameters():
            console.print("[yellow]No parameters loaded[/yellow]")
            return

        filename = arg.strip() or "parameters.txt"
        if self.mavlink_service.save_parameters_to_file(filename):
            console.print(f"[green]Parameters saved to {filename}[/green]")
        else:
            console.print(f"[red]Failed to save parameters to {filename}[/red]")

    def do_exit(self, arg):
        """Exit the CLI."""
        if self.mavlink_service.is_connected():
            self.mavlink_service.disconnect()
        console.print("[green]Goodbye![/green]")
        return True

    def do_quit(self, arg):
        """Exit the CLI."""
        return self.do_exit(arg)

    def do_motor_test(self, arg):
        """
        Test a motor.
        Usage: motor_test <motor_number> <throttle_%> [duration_sec]
               motor_test all <throttle_%> [duration_sec]
        Example: motor_test 1 10 2
        """
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        args = arg.split()
        if len(args) < 2:
            console.print("[red]Usage: motor_test <motor_number|all> <throttle_%> [duration][/red]")
            return

        motor_arg = args[0].lower()
        try:
            throttle = int(args[1])
            duration = float(args[2]) if len(args) > 2 else 2.0
        except ValueError:
            console.print("[red]Invalid throttle or duration value[/red]")
            return

        if throttle < 1 or throttle > 100:
            console.print("[red]Throttle must be 1-100%[/red]")
            return

        if duration < 0.5 or duration > 10:
            console.print("[red]Duration must be 0.5-10 seconds[/red]")
            return

        console.print("[bold red]⚠️  WARNING: Remove propellers before testing![/bold red]")

        if motor_arg == "all":
            success = self.mavlink_service.test_all_motors(throttle, duration)
            msg = f"Testing all motors at {throttle}% for {duration}s"
        else:
            try:
                motor = int(motor_arg)
                if motor < 1 or motor > 8:
                    console.print("[red]Motor number must be 1-8[/red]")
                    return
                success = self.mavlink_service.motor_test(motor, throttle, duration)
                msg = f"Testing motor {motor} at {throttle}% for {duration}s"
            except ValueError:
                console.print("[red]Invalid motor number[/red]")
                return

        if success:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            console.print("[red]Failed to send motor test command[/red]")

    def do_compass_health(self, arg):
        """Check compass calibration status and health."""
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        console.print("[cyan]Checking compass health...[/cyan]")

        # Get compass offsets
        offsets = self.mavlink_service.get_compass_offsets()

        # Check if calibrated
        if offsets.get("calibrated"):
            console.print("[green]✓ Compass is calibrated[/green]")
            console.print(
                f"  Offsets: X={offsets.get('COMPASS_OFS_X', 0):.0f} "
                f"Y={offsets.get('COMPASS_OFS_Y', 0):.0f} "
                f"Z={offsets.get('COMPASS_OFS_Z', 0):.0f}"
            )
        else:
            console.print("[red]✗ Compass NOT calibrated (offsets are 0,0,0)[/red]")

        # Magnetic field strength
        telem = self.mavlink_service.get_telemetry()
        mag_field = telem.mag_field_strength
        if mag_field > 0:
            if 200 < mag_field < 700:
                console.print(f"[green]✓ Mag field: {mag_field:.0f} mG (normal)[/green]")
            else:
                console.print(f"[yellow]⚠️  Mag field: {mag_field:.0f} mG (check for interference)[/yellow]")
        else:
            console.print("[yellow]⚠️  Mag field: No data available[/yellow]")

    def do_compass_cal(self, arg):
        """
        Start or cancel compass calibration.
        Usage: compass_cal start  - Start calibration
               compass_cal cancel - Cancel calibration
        """
        if not self.mavlink_service.is_connected():
            console.print("[yellow]Not connected[/yellow]")
            return

        cmd = arg.strip().lower()
        if cmd == "start":
            if self.mavlink_service.start_compass_calibration(autosave=True):
                console.print("[cyan]🧭 Compass calibration started[/cyan]")
                console.print("[yellow]Rotate vehicle in all orientations...[/yellow]")
            else:
                console.print("[red]Failed to start compass calibration[/red]")
        elif cmd == "cancel":
            if self.mavlink_service.cancel_compass_calibration():
                console.print("[yellow]Compass calibration cancelled[/yellow]")
            else:
                console.print("[red]Failed to cancel compass calibration[/red]")
        else:
            console.print("[red]Usage: compass_cal start|cancel[/red]")

    def cmdloop(self, intro=None):
        """Main command loop with auto-connect."""
        console.print(self.intro)

        # Auto-connect on startup
        def on_progress(message: str):
            console.print(message)

        self.mavlink_service.connect(on_progress=on_progress)
        if self.mavlink_service.is_connected():
            self._load_parameters()

        # Update session with parameter completer
        self.session = PromptSession(completer=ParameterCompleter(self.mavlink_service))

        # Command loop
        try:
            while True:
                try:
                    line = self.session.prompt(self.prompt)
                    if line.strip().lower() in ["exit", "quit"]:
                        return self.do_exit(line)
                    self.onecmd(line)
                except KeyboardInterrupt:
                    console.print('\n[yellow]KeyboardInterrupt: Type "exit" or "quit" to exit[/yellow]')
        except (KeyboardInterrupt, EOFError):
            return self.do_exit("")
