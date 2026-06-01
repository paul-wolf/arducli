from typing import Callable, Dict, Optional

from models import ConnectionConfig, DeviceInfo

from .connection_service import ConnectionService
from .parameter_service import ParameterService
from .telemetry_service import TelemetryData, TelemetryService


class MAVLinkService:
    """
    Main service for MAVLink operations.
    Orchestrates connection and parameter management.
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.connection_service = ConnectionService(config)
        self.parameter_service = ParameterService()
        self.telemetry_service = TelemetryService()

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

    # Telemetry methods

    def start_telemetry(self) -> None:
        """Start telemetry data streams."""
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")
        connection = self.connection_service.get_connection()
        self.telemetry_service.request_data_streams(connection)

    def update_telemetry(self) -> bool:
        """
        Update telemetry data from the connection.

        Returns:
            True if any data was updated
        """
        if not self.is_connected():
            return False
        connection = self.connection_service.get_connection()
        return self.telemetry_service.update(connection)

    def get_telemetry(self) -> TelemetryData:
        """Get current telemetry data."""
        return self.telemetry_service.get_data()

    def get_gps_status(self) -> str:
        """Get GPS status string."""
        return self.telemetry_service.get_gps_status()

    def get_messages(self, limit=None):
        """Get recent messages."""
        return self.telemetry_service.get_messages(limit)

    # Command methods

    def motor_test(self, motor_number: int, throttle_percent: int, duration_sec: float = 2.0) -> bool:
        """
        Test a motor.

        Args:
            motor_number: Motor number (1-based, typically 1-8)
            throttle_percent: Throttle percentage (0-100)
            duration_sec: Test duration in seconds

        Returns:
            True if command was sent successfully

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()

        try:
            # MAV_CMD_DO_MOTOR_TEST (209)
            # param1: motor sequence number (1-based)
            # param2: throttle type (0=%, 1=PWM, 2=pilot)
            # param3: throttle value
            # param4: timeout/duration in seconds
            # param5: motor count (0=just one motor)
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                209,  # MAV_CMD_DO_MOTOR_TEST
                0,  # confirmation
                motor_number,  # param1: motor number
                0,  # param2: throttle type (0 = percentage)
                throttle_percent,  # param3: throttle
                duration_sec,  # param4: timeout
                0,  # param5: motor count (0 = single motor)
                0,  # param6
                0,  # param7
            )
            return True
        except Exception:
            return False

    def test_all_motors(self, throttle_percent: int, duration_sec: float = 2.0) -> bool:
        """
        Test all motors in sequence.

        Args:
            throttle_percent: Throttle percentage (0-100)
            duration_sec: Test duration per motor in seconds

        Returns:
            True if command was sent successfully
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()

        try:
            # Use motor count = 8 to test all motors in sequence
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                209,  # MAV_CMD_DO_MOTOR_TEST
                0,  # confirmation
                1,  # param1: start from motor 1
                0,  # param2: throttle type (0 = percentage)
                throttle_percent,  # param3: throttle
                duration_sec,  # param4: timeout
                8,  # param5: motor count (test motors 1-8)
                0,  # param6
                0,  # param7
            )
            return True
        except Exception:
            return False

    def start_compass_calibration(self, autosave: bool = True) -> bool:
        """
        Start compass calibration.

        Args:
            autosave: Automatically save calibration on completion

        Returns:
            True if command was sent successfully

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()

        try:
            # MAV_CMD_DO_START_MAG_CAL (42424)
            # param1: mag_mask (0 = all magnetometers)
            # param2: retry (0 = no retry, 1 = retry if fails)
            # param3: autosave (0 = no, 1 = yes)
            # param4: delay (0 = no delay)
            # param5: autoreboot (0 = no)
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                42424,  # MAV_CMD_DO_START_MAG_CAL
                0,  # confirmation
                0,  # param1: all magnetometers
                0,  # param2: no retry
                1 if autosave else 0,  # param3: autosave
                0,  # param4: no delay
                0,  # param5: no autoreboot
                0,  # param6
                0,  # param7
            )
            return True
        except Exception:
            return False

    def cancel_compass_calibration(self) -> bool:
        """
        Cancel compass calibration.

        Returns:
            True if command was sent successfully

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()

        try:
            # MAV_CMD_DO_CANCEL_MAG_CAL (42425)
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                42425,  # MAV_CMD_DO_CANCEL_MAG_CAL
                0,  # confirmation
                0,  # param1: all magnetometers
                0,  # param2-7: unused
                0,
                0,
                0,
                0,
                0,
            )
            return True
        except Exception:
            return False

    def accept_compass_calibration(self) -> bool:
        """
        Accept compass calibration results.

        Returns:
            True if command was sent successfully

        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to a device")

        connection = self.connection_service.get_connection()

        try:
            # MAV_CMD_DO_ACCEPT_MAG_CAL (42426)
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                42426,  # MAV_CMD_DO_ACCEPT_MAG_CAL
                0,  # confirmation
                0,  # param1: all magnetometers
                0,  # param2-7: unused
                0,
                0,
                0,
                0,
                0,
            )
            return True
        except Exception:
            return False

    def get_compass_offsets(self) -> dict:
        """
        Get compass offset parameters to check if calibration has been done.

        Returns:
            Dictionary of compass offset parameters
        """
        offsets = {}
        try:
            # Check compass 1 offsets
            offsets["COMPASS_OFS_X"] = self.get_parameter("COMPASS_OFS_X")
            offsets["COMPASS_OFS_Y"] = self.get_parameter("COMPASS_OFS_Y")
            offsets["COMPASS_OFS_Z"] = self.get_parameter("COMPASS_OFS_Z")

            # Check if calibrated (offsets should not be 0,0,0)
            offsets["calibrated"] = not (
                offsets["COMPASS_OFS_X"] == 0 and offsets["COMPASS_OFS_Y"] == 0 and offsets["COMPASS_OFS_Z"] == 0
            )
        except Exception:
            pass

        return offsets
