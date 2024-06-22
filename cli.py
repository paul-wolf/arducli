import re

from connection import find_ardupilot_port
from parameters import load_parameters
from mav import MAV_TYPE, MAV_AUTOPILOT

import cmd
from pymavlink import mavutil

from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.completion import Completer, Completion
from rich.console import Console
from rich.prompt import Prompt


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
    intro = "[green]Welcome to the pymavlink CLI.[/green] Type [bold]help[/bold] or [bold]?[/bold] to list commands.\nPress Ctrl-C to exit."
    prompt = HTML("(<ansiyellow>pymavlink</ansiyellow>) ")

    connection = None
    parameters = {}

    def __init__(self):
        super().__init__()
        self.session = PromptSession(completer=ParameterCompleter(self.parameters))

    def do_connect(self, arg):
        """ "Connect to the flight controller by scanning ports and waiting for a heartbeat message."""
        self.connection = find_ardupilot_port()
        if self.connection:
            self.do_info(arg)
            self.parameters = load_parameters(self.connection)
            print("parameters loaded")

    def do_info(self, arg):
        """Print information about the connected flight controller."""
        heartbeat = self.connection.recv_match(type="HEARTBEAT", blocking=True)
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
