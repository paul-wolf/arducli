import os
import time
from typing import Callable, List, Optional

import serial.tools.list_ports
from pymavlink import mavutil

from constants.mav import MAV_AUTOPILOT, MAV_TYPE
from models import ConnectionConfig, DeviceInfo


class ConnectionService:
    """Service for managing MAVLink connections to ArduPilot devices."""

    LAST_PORT_FILE = os.path.expanduser("~/.arducli_last_port")

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self.connection: Optional[mavutil.mavlink_connection] = None
        self.device_info: Optional[DeviceInfo] = None

    def list_serial_ports(self) -> List[str]:
        """List all available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def get_last_used_port(self) -> Optional[str]:
        """Retrieve the last successfully used port."""
        if os.path.exists(self.LAST_PORT_FILE):
            try:
                with open(self.LAST_PORT_FILE) as f:
                    return f.read().strip()
            except Exception:
                return None
        return None

    def save_last_used_port(self, port: str) -> None:
        """Save the successfully connected port for future use."""
        try:
            with open(self.LAST_PORT_FILE, "w") as f:
                f.write(port)
        except Exception:
            pass  # Non-critical, fail silently

    def prioritize_ports(self, ports: List[str]) -> List[str]:
        """Prioritize ports with last used port first."""
        last_port = self.get_last_used_port()
        if last_port and last_port in ports:
            prioritized = [last_port]
            prioritized.extend([p for p in ports if p != last_port])
            return prioritized
        return ports

    def connect_to_port(
        self,
        port: str,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Attempt to connect to a specific port.

        Args:
            port: Serial port to connect to
            on_progress: Optional callback for progress updates

        Returns:
            True if connection successful, False otherwise
        """
        if on_progress:
            on_progress(f"Trying port: {port}")

        try:
            # Attempt connection
            connection = mavutil.mavlink_connection(port, baud=self.config.baud_rate)

            # Wait for heartbeat
            start_time = time.time()
            while time.time() - start_time < self.config.timeout:
                if connection.wait_heartbeat(timeout=1):
                    # Heartbeat received, parse device info
                    heartbeat = connection.recv_match(type="HEARTBEAT", blocking=True)
                    if heartbeat:
                        self.connection = connection
                        self.device_info = DeviceInfo(
                            system_id=connection.target_system,
                            component_id=connection.target_component,
                            autopilot_type=heartbeat.autopilot,
                            vehicle_type=heartbeat.type,
                            autopilot_name=MAV_AUTOPILOT.get(heartbeat.autopilot, "Unknown"),
                            vehicle_name=MAV_TYPE.get(heartbeat.type, "Unknown"),
                            port=port,
                        )

                        # Request autopilot version info
                        self._request_autopilot_version(connection)

                        self.save_last_used_port(port)

                        if on_progress:
                            on_progress(f"Connected: {self.device_info.description}")

                        return True

            if on_progress:
                on_progress(f"No heartbeat on port {port} within {self.config.timeout} seconds")

        except Exception as e:
            if on_progress:
                on_progress(f"Error connecting to port {port}: {e}")

        return False

    def auto_connect(self, on_progress: Optional[Callable[[str], None]] = None) -> bool:
        """
        Automatically scan and connect to an ArduPilot device.

        Args:
            on_progress: Optional callback for progress updates

        Returns:
            True if connection successful, False otherwise
        """
        ports = self.list_serial_ports()

        if not ports:
            if on_progress:
                on_progress("No serial ports found")
            return False

        if on_progress:
            on_progress(f"Scanning ports: {', '.join(ports)}")

        # Prioritize last used port
        ports = self.prioritize_ports(ports)

        # Try each port
        for port in ports:
            if self.connect_to_port(port, on_progress):
                return True

        if on_progress:
            on_progress("No ArduPilot device found on any port")

        return False

    def disconnect(self) -> None:
        """Disconnect from the current device."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.device_info = None

    def is_connected(self) -> bool:
        """Check if currently connected to a device."""
        return self.connection is not None

    def get_connection(self) -> Optional[mavutil.mavlink_connection]:
        """Get the active MAVLink connection."""
        return self.connection

    def get_device_info(self) -> Optional[DeviceInfo]:
        """Get information about the connected device."""
        return self.device_info

    def _request_autopilot_version(self, connection: mavutil.mavlink_connection) -> None:
        """Request autopilot version information."""
        try:
            # Request autopilot version
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                0,  # confirmation
                mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION,  # param1: message ID
                0,
                0,
                0,
                0,
                0,
                0,
            )

            # Wait for response (non-blocking)
            start_time = time.time()
            while time.time() - start_time < 2:  # 2 second timeout
                msg = connection.recv_match(type="AUTOPILOT_VERSION", blocking=False, timeout=0.1)
                if msg:
                    self._parse_autopilot_version(msg)
                    break
        except Exception:
            # Non-critical, continue without version info
            pass

    def _parse_autopilot_version(self, msg) -> None:
        """Parse autopilot version message."""
        if not self.device_info:
            return

        try:
            # Extract version numbers
            major = (msg.flight_sw_version >> 24) & 0xFF
            minor = (msg.flight_sw_version >> 16) & 0xFF
            patch = (msg.flight_sw_version >> 8) & 0xFF
            fw_type = msg.flight_sw_version & 0xFF

            # Version type suffix
            fw_type_str = {0: "", 64: "-dev", 128: "-alpha", 192: "-beta", 255: "-rc"}.get(fw_type, "")

            self.device_info.firmware_version = f"{major}.{minor}.{patch}{fw_type_str}"

            # Board version if available
            if msg.board_version > 0:
                self.device_info.hardware_version = f"{msg.board_version}"

            # Product ID can indicate board type
            if msg.product_id > 0:
                self.device_info.board_type = f"ID:{msg.product_id}"

        except Exception:
            # If parsing fails, just skip
            pass
