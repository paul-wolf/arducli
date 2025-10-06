from typing import Callable, Dict, Optional

from models import ConnectionConfig, DeviceInfo

from .connection_service import ConnectionService
from .parameter_service import ParameterService


class MAVLinkService:
    """
    Main service for MAVLink operations.
    Orchestrates connection and parameter management.
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.connection_service = ConnectionService(config)
        self.parameter_service = ParameterService()

    # Connection methods

    def connect(self, port: Optional[str] = None, on_progress: Optional[Callable[[str], None]] = None) -> bool:
        """
        Connect to ArduPilot device.

        Args:
            port: Specific port to connect to, or None for auto-detection
            on_progress: Optional callback for connection progress

        Returns:
            True if connected successfully
        """
        if port:
            return self.connection_service.connect_to_port(port, on_progress)
        else:
            return self.connection_service.auto_connect(on_progress)

    def disconnect(self) -> None:
        """Disconnect from the device."""
        self.connection_service.disconnect()
        self.parameter_service.parameters.clear()

    def is_connected(self) -> bool:
        """Check if connected to a device."""
        return self.connection_service.is_connected()

    def get_device_info(self) -> Optional[DeviceInfo]:
        """Get information about the connected device."""
        return self.connection_service.get_device_info()

    # Parameter methods

    def load_parameters(self, on_progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, float]:
        """
        Load all parameters from the flight controller.

        Args:
            on_progress: Optional callback for progress (current, total)

        Returns:
            Dictionary of parameters

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()
        return self.parameter_service.load_parameters(connection, on_progress)

    def get_parameter(self, param_name: str) -> Optional[float]:
        """Get a parameter value."""
        return self.parameter_service.get_parameter(param_name)

    def get_parameters_matching(self, pattern: str) -> Dict[str, float]:
        """Get parameters matching a regex pattern."""
        return self.parameter_service.get_parameters_matching(pattern)

    def set_parameter(self, param_name: str, param_value: float) -> bool:
        """
        Set a parameter value.

        Args:
            param_name: Parameter name
            param_value: New value

        Returns:
            True if successful

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()
        return self.parameter_service.set_parameter(connection, param_name, param_value)

    def get_all_parameters(self) -> Dict[str, float]:
        """Get all cached parameters."""
        return self.parameter_service.get_all_parameters()

    def save_parameters_to_file(self, filepath: str) -> bool:
        """Save parameters to a file."""
        return self.parameter_service.save_to_file(filepath)

    def has_parameters(self) -> bool:
        """Check if parameters have been loaded."""
        return self.parameter_service.has_parameters()
