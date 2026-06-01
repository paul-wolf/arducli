"""Service for managing MAVLink telemetry data."""

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

from pymavlink import mavutil

from constants.mav import COPTER_MODES, PLANE_MODES, ROVER_MODES


@dataclass
class TelemetryData:
    """Container for telemetry data."""

    # GPS
    gps_fix_type: int = 0  # 0=No GPS, 1=No Fix, 2=2D Fix, 3=3D Fix
    gps_satellites: int = 0
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_alt: float = 0.0

    # Battery
    battery_voltage: float = 0.0  # Volts
    battery_current: float = 0.0  # Amps
    battery_remaining: int = 0  # Percentage

    # Attitude
    heading: float = 0.0  # Degrees
    roll: float = 0.0  # Degrees
    pitch: float = 0.0  # Degrees

    # System
    armed: bool = False
    mode: str = "UNKNOWN"

    # Compass
    compass_healthy: bool = False
    compass_variance: float = 0.0
    mag_field_strength: float = 0.0  # milligauss


class TelemetryService:
    """Service for handling telemetry data from MAVLink."""

    def __init__(self):
        self.data = TelemetryData()
        self._stream_requested = False
        self._vehicle_type = None  # Will be set from heartbeat
        self._messages: Deque[Tuple[str, str]] = deque(maxlen=100)  # (severity, text)

    def request_data_streams(self, connection: mavutil.mavlink_connection) -> None:
        """Request telemetry data streams from the autopilot."""
        if self._stream_requested:
            return

        # Request data streams at 2 Hz
        connection.mav.request_data_stream_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            2,  # Hz
            1,  # Start
        )
        self._stream_requested = True

    def update(self, connection: mavutil.mavlink_connection) -> bool:
        """
        Update telemetry data from MAVLink messages.

        Args:
            connection: Active MAVLink connection

        Returns:
            True if any data was updated
        """
        updated = False
        msg = connection.recv_match(blocking=False)

        while msg:
            msg_type = msg.get_type()

            if msg_type == "GPS_RAW_INT":
                self.data.gps_fix_type = msg.fix_type
                self.data.gps_satellites = msg.satellites_visible
                self.data.gps_lat = msg.lat / 1e7
                self.data.gps_lon = msg.lon / 1e7
                self.data.gps_alt = msg.alt / 1000.0
                updated = True

            elif msg_type == "SYS_STATUS":
                self.data.battery_voltage = msg.voltage_battery / 1000.0
                self.data.battery_current = msg.current_battery / 100.0
                self.data.battery_remaining = msg.battery_remaining
                updated = True

            elif msg_type == "VFR_HUD":
                self.data.heading = msg.heading
                updated = True

            elif msg_type == "ATTITUDE":
                import math

                self.data.roll = math.degrees(msg.roll)
                self.data.pitch = math.degrees(msg.pitch)
                updated = True

            elif msg_type == "HEARTBEAT":
                self.data.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

                # Store vehicle type for mode decoding
                if self._vehicle_type is None:
                    self._vehicle_type = msg.type

                # Decode flight mode from custom_mode
                mode_num = msg.custom_mode
                mode_name = self._decode_mode(self._vehicle_type, mode_num)
                self.data.mode = mode_name
                updated = True

            elif msg_type == "STATUSTEXT":
                # Capture text messages
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
                severity = severity_map.get(msg.severity, "INFO")
                text = msg.text.decode("utf-8") if isinstance(msg.text, bytes) else msg.text
                self._messages.append((severity, text))
                updated = True

            elif msg_type == "RAW_IMU":
                # Get magnetometer readings
                try:
                    import math

                    # Calculate magnetic field strength (milligauss)
                    mag_x = msg.xmag
                    mag_y = msg.ymag
                    mag_z = msg.zmag
                    self.data.mag_field_strength = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
                    updated = True
                except Exception:
                    # If RAW_IMU doesn't have mag data, skip
                    pass

            elif msg_type == "MAG_CAL_REPORT":
                # Compass calibration report
                # fitness is the quality metric (lower is better, < 200 is good)
                # We can use this to assess calibration quality
                try:
                    if hasattr(msg, "fitness"):
                        # Good calibration: fitness < 200
                        # Acceptable: 200-400
                        # Poor: > 400
                        self.data.compass_healthy = msg.fitness < 400
                    updated = True
                except Exception:
                    pass

            msg = connection.recv_match(blocking=False)

        return updated

    def get_data(self) -> TelemetryData:
        """Get the current telemetry data."""
        return self.data

    def _decode_mode(self, vehicle_type: int, mode_num: int) -> str:
        """Decode flight mode based on vehicle type."""
        # Copter types: 2 (Quadrotor), 13 (Hexarotor), 14 (Octorotor), 15 (Tricopter)
        if vehicle_type in [2, 13, 14, 15]:
            return COPTER_MODES.get(mode_num, f"Mode {mode_num}")
        # Plane type: 1 (Fixed-wing)
        elif vehicle_type == 1:
            return PLANE_MODES.get(mode_num, f"Mode {mode_num}")
        # Rover types: 10 (Ground rover), 11 (Surface vessel)
        elif vehicle_type in [10, 11]:
            return ROVER_MODES.get(mode_num, f"Mode {mode_num}")
        else:
            return f"Mode {mode_num}"

    def get_gps_status(self) -> str:
        """Get human-readable GPS status."""
        fix_types = {
            0: "No GPS",
            1: "No Fix",
            2: "2D Fix",
            3: "3D Fix",
            4: "DGPS",
            5: "RTK Float",
            6: "RTK Fixed",
        }
        fix = fix_types.get(self.data.gps_fix_type, "Unknown")
        return f"{fix} ({self.data.gps_satellites} sats)"

    def get_messages(self, limit: Optional[int] = None) -> List[Tuple[str, str]]:
        """Get recent messages.

        Args:
            limit: Maximum number of messages to return (most recent first)

        Returns:
            List of (severity, text) tuples
        """
        messages = list(self._messages)
        messages.reverse()  # Most recent first
        if limit:
            return messages[:limit]
        return messages
