import re
from typing import Callable, Dict, Optional

from pymavlink import mavutil


class ParameterService:
    """Service for managing ArduPilot parameters."""

    def __init__(self):
        self.parameters: Dict[str, float] = {}

    def load_parameters(
        self,
        connection: mavutil.mavlink_connection,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, float]:
        """
        Load all parameters from the flight controller.

        Args:
            connection: Active MAVLink connection
            on_progress: Optional callback for progress (current, total)

        Returns:
            Dictionary of parameter name -> value
        """
        self.parameters = {}

        # Request all parameters
        connection.mav.param_request_list_send(connection.target_system, connection.target_component)

        # Get first message to determine total count
        first_message = connection.recv_match(type="PARAM_VALUE", blocking=True)
        if not first_message:
            return self.parameters

        total_params = first_message.param_count
        self.parameters[first_message.param_id.strip("\x00")] = first_message.param_value

        if on_progress:
            on_progress(1, total_params)

        # Receive remaining parameters
        while True:
            message = connection.recv_match(type="PARAM_VALUE", blocking=True)
            if message:
                param_id = message.param_id.strip("\x00")
                param_value = message.param_value
                self.parameters[param_id] = param_value

                if on_progress:
                    on_progress(message.param_index + 1, total_params)

                # Check if all parameters received
                if message.param_index + 1 == message.param_count:
                    break

        return self.parameters

    def get_parameter(self, param_name: str) -> Optional[float]:
        """Get a single parameter value by name."""
        return self.parameters.get(param_name.upper())

    def get_parameters_matching(self, pattern: str) -> Dict[str, float]:
        """Get all parameters matching a regex pattern."""
        try:
            regex = re.compile(pattern)
            return {key: value for key, value in self.parameters.items() if regex.match(key)}
        except re.error:
            return {}

    def set_parameter(
        self,
        connection: mavutil.mavlink_connection,
        param_name: str,
        param_value: float,
    ) -> bool:
        """
        Set a parameter value on the flight controller.

        Args:
            connection: Active MAVLink connection
            param_name: Parameter name
            param_value: New value

        Returns:
            True if successful
        """
        try:
            param_name = param_name.upper()
            connection.mav.param_set_send(
                connection.target_system,
                connection.target_component,
                param_name.encode("utf-8"),
                float(param_value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
            )

            # Update local cache
            self.parameters[param_name] = float(param_value)
            return True

        except Exception:
            return False

    def get_all_parameters(self) -> Dict[str, float]:
        """Get all cached parameters."""
        return self.parameters.copy()

    def save_to_file(self, filepath: str) -> bool:
        """
        Save parameters to a file.

        Args:
            filepath: Path to save file

        Returns:
            True if successful
        """
        try:
            with open(filepath, "w") as f:
                for param_id, param_value in sorted(self.parameters.items()):
                    f.write(f"{param_id}: {param_value}\n")
            return True
        except Exception:
            return False

    def has_parameters(self) -> bool:
        """Check if parameters have been loaded."""
        return len(self.parameters) > 0
