import cmd
import datetime
import os
import re

from prompt_toolkit import HTML, PromptSession
from prompt_toolkit.completion import Completer, Completion
from pymavlink import mavutil
from rich.console import Console
from serial import SerialException

from connection import find_ardupilot_port
from mav import MAV_AUTOPILOT, MAV_TYPE
from parameters import load_parameters

REGEX_CHARS = "[](){}^$+*?.\\|"

console = Console()


def get_matching_keys(data, regex):
    return [key for key in data.keys() if re.match(regex, key)]


class ParameterCompleter(Completer):
    def __init__(self, parameters):
        self.parameters = parameters

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor().lower()  # Convert to lowercase
        for param in self.parameters:
            if param.lower().startswith(word):  # Convert parameter to lowercase
                yield Completion(param, start_position=-len(word))


class MavlinkCLI(cmd.Cmd):
    intro = (
        "[green]Welcome to the pymavlink CLI.[/green] "
        "Type [bold]help[/bold] or [bold]?[/bold] to list commands.\n"
        "Press Ctrl-C to exit."
    )
    prompt = HTML("(<ansiyellow>pymavlink</ansiyellow>) ")

    connection = None
    parameters = {}

    def __init__(self):
        super().__init__()
        self.session = PromptSession(completer=ParameterCompleter(self.parameters))

    def do_connect(self, arg):
        """Connect to the flight controller.
        Usage: connect [connection_string]
        No argument: auto-scan serial ports.
        Examples:
          connect udpin:0.0.0.0:14550
          connect tcp:192.168.1.5:5760"""
        connection_str = (arg or "").strip()
        if connection_str:
            print(f"Connecting to {connection_str}...")
            try:
                connection = mavutil.mavlink_connection(connection_str)
                print("Waiting for heartbeat...")
                if connection.wait_heartbeat(timeout=10):
                    self.connection = connection
                else:
                    print(f"No heartbeat received from {connection_str}")
                    return
            except Exception as e:
                print(f"Error connecting to {connection_str}: {e}")
                return
        else:
            self.connection = find_ardupilot_port()

        if self.connection:
            self.do_info("")
            self.parameters = load_parameters(self.connection)
            print("parameters loaded")

    def do_info(self, arg):
        """Print information about the connected flight controller."""
        if not self.connection:
            print("Not connected")
            return
        try:
            heartbeat = self.connection.recv_match(type="HEARTBEAT", blocking=True)
        except SerialException as e:
            print(f"Device error: {e}")
            self.connection = None
            self.parameters = {}
            return
        if heartbeat:
            autopilot_type = heartbeat.type
            autopilot_system = heartbeat.autopilot

            print(f"Autopilot Type: {MAV_TYPE.get(autopilot_type, 'Unknown')}")
            print(f"Autopilot System: {MAV_AUTOPILOT.get(autopilot_system, 'Unknown')}")

    def do_dump(self, arg):
        """Print all parameters in the cache."""
        for param_id, param_value in self.parameters.items():
            print(f"{param_id}: {param_value}")

    def do_get(self, arg):
        """Get the value of a specific parameter: get <PARAM_ID>.
        Use a regular expression to match multiple parameters: get <REGEX>"""
        if not self.connection:
            print("Not connected")
            return
        param_id = arg.strip().upper()
        if set(param_id) & set(REGEX_CHARS):
            matching_keys = get_matching_keys(self.parameters, param_id)
            for key in matching_keys:
                print(f"{key}: {self.parameters[key]}")
        elif param_id in self.parameters:
            # print(Fore.WHITE + f"{param_id}: {self.parameters[param_id]}")
            print(f"{param_id}: {self.parameters[param_id]}")
        else:
            print(f"Parameter {param_id} not found in cache. Please read parameters first.")

    def complete_get(self, text, line, begidx, endidx):
        if not self.parameters:
            return []
        completions = [param for param in self.parameters if param.startswith(text)]
        return completions

    def do_set(self, arg):
        "Set the value of a specific parameter: set <PARAM_ID> <VALUE>"
        if not self.connection:
            print("Not connected")
            return
        args = arg.split().upper()
        if len(args) != 2:
            print("Usage: set_parameter <PARAM_ID> <VALUE>")
            return
        param_id, param_value = args
        param_value = float(param_value)
        self.connection.mav.param_set_send(
            self.connection.target_system,
            self.connection.target_component,
            param_id.encode("utf-8"),
            param_value,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )
        # Update the cached value
        self.parameters[param_id] = param_value
        print(f"Parameter {param_id} set to {param_value}")

    def complete_set(self, text, line, begidx, endidx):
        if not self.connection or not self.parameters:
            return []
        return [param for param in self.parameters if param.startswith(text)]

    def do_save_file(self, arg):
        with open(arg or "parameters.txt", "w") as f:
            for param_id, param_value in self.parameters.items():
                f.write(f"{param_id}: {param_value}\n")

    def do_history(self, arg):
        """Print STATUSTEXT messages from the telemetry log (mav.tlog)."""
        tlog_path = "mav.tlog"
        if not os.path.exists(tlog_path):
            print("No telemetry log found (mav.tlog)")
            return
        severity_map = {
            0: "EMERGENCY",
            1: "ALERT",
            2: "CRITICAL",
            3: "ERROR",
            4: "WARNING",
            5: "NOTICE",
            6: "INFO",
            7: "DEBUG",
        }
        log = mavutil.mavlink_connection(tlog_path)
        count = 0
        while True:
            msg = log.recv_match(type="STATUSTEXT", blocking=False)
            if msg is None:
                break
            severity = severity_map.get(msg.severity, "INFO")
            text = msg.text
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            ts = getattr(msg, "_timestamp", None)
            prefix = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S") + " " if ts else ""
            print(f"{prefix}[{severity}] {text.rstrip(chr(0))}")
            count += 1
        if count == 0:
            print("No messages in log.")

    def do_messages(self, arg):
        """Listen for and print STATUSTEXT messages from the flight controller. Press Ctrl-C to stop."""
        if not self.connection:
            print("Not connected")
            return
        severity_map = {
            0: "EMERGENCY",
            1: "ALERT",
            2: "CRITICAL",
            3: "ERROR",
            4: "WARNING",
            5: "NOTICE",
            6: "INFO",
            7: "DEBUG",
        }
        print("Listening for messages (Ctrl-C to stop)...")
        try:
            while True:
                try:
                    msg = self.connection.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
                    if msg:
                        severity = severity_map.get(msg.severity, "INFO")
                        text = msg.text
                        if isinstance(text, bytes):
                            text = text.decode("utf-8")
                        print(f"[{severity}] {text.rstrip(chr(0))}")
                except SerialException as e:
                    print(f"Device error: {e}")
                    self.connection = None
                    self.parameters = {}
                    return
        except KeyboardInterrupt:
            print("\nStopped.")

    def do_disconnect(self, arg):
        "Disconnect from the flight controller"
        if self.connection:
            self.connection.close()
            self.connection = None
            self.parameters = {}
            print("Disconnected")
        else:
            print("No connection to disconnect")

    def do_exit(self, arg):
        "Exit the CLI"
        console.print("[green]Exiting...[/green]")
        return True

    def do_quit(self, arg):
        "Exit the CLI"
        return self.do_exit(arg)

    # def cmdloop(self, intro=None):
    #     print(self.intro)
    #     self.do_connect(None)
    #     try:
    #         super(MavlinkCLI, self).cmdloop(intro)
    #     except KeyboardInterrupt:
    #         print("Exiting...")

    def cmdloop(self, intro=None):
        print(self.intro)
        self.do_connect(None)
        self.session = PromptSession(completer=ParameterCompleter(self.parameters))
        try:
            while True:
                try:
                    line = self.session.prompt(self.prompt)
                    if line.strip().lower() in ["exit", "quit"]:
                        return self.do_exit(line)
                    self.onecmd(line)
                except KeyboardInterrupt:
                    print('\nKeyboardInterrupt: Type "exit" or "quit" to exit the CLI')
        except KeyboardInterrupt:
            print("Exiting...")


if __name__ == "__main__":
    MavlinkCLI().cmdloop()
