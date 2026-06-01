"""Service for managing MAVLink telemetry data."""

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from pymavlink import mavutil

from constants.mav import COPTER_MODES, PLANE_MODES, ROVER_MODES


@dataclass
class TelemetryData:
    """Container for telemetry data."""

    # GPS
    gps_fix_type: int = 0
    gps_satellites: int = 0
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_alt: float = 0.0  # MSL metres
    gps_hdop: float = 0.0
    gps_vdop: float = 0.0
    rel_alt: float = 0.0  # relative to home, metres

    # Battery
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    battery_remaining: int = 0

    # Attitude
    heading: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw_rate: float = 0.0  # deg/s

    # VFR HUD
    airspeed: float = 0.0  # m/s
    groundspeed: float = 0.0  # m/s
    throttle: int = 0  # %
    climb_rate: float = 0.0  # m/s  (positive = climbing)
    alt_vfr: float = 0.0  # barometric altitude, metres

    # System
    armed: bool = False
    mode: str = "UNKNOWN"

    # EKF
    ekf_ok: bool = False
    ekf_flags: int = 0
    ekf_vel_variance: float = 0.0
    ekf_pos_horiz_variance: float = 0.0
    ekf_pos_vert_variance: float = 0.0
    ekf_compass_variance: float = 0.0
    ekf_terrain_variance: float = 0.0

    # Vibration
    vib_x: float = 0.0
    vib_y: float = 0.0
    vib_z: float = 0.0
    vib_clip: int = 0  # total accel clipping count

    # RC / link
    rssi: int = 0  # 0-254 (255 = unknown)

    # Wind (WIND message, not always sent)
    wind_speed: float = 0.0  # m/s
    wind_dir: float = 0.0  # degrees

    # Compass / mag
    compass_healthy: bool = False
    mag_field_strength: float = 0.0  # milligauss


class TelemetryService:
    """Service for handling telemetry data from MAVLink."""

    def __init__(self):
        self.data = TelemetryData()
        self._stream_requested = False
        self._vehicle_type = None
        self._messages: Deque[Tuple[str, str]] = deque(maxlen=100)
        # Raw MAVLink capture: {msg_type: (fields_dict, received_timestamp)}
        self._raw: Dict[str, Tuple[dict, float]] = {}

    def request_data_streams(self, connection: mavutil.mavlink_connection) -> None:
        if self._stream_requested:
            return
        connection.mav.request_data_stream_send(
            connection.target_system,
            connection.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            2,
            1,
        )
        self._stream_requested = True

    def update(self, connection: mavutil.mavlink_connection) -> bool:
        updated = False
        msg = connection.recv_match(blocking=False)

        while msg:
            msg_type = msg.get_type()

            # Capture every message for the raw view
            try:
                fields = {k: v for k, v in msg.to_dict().items() if k != "mavpackettype"}
                self._raw[msg_type] = (fields, time.time())
            except Exception:
                pass

            if msg_type == "GPS_RAW_INT":
                self.data.gps_fix_type = msg.fix_type
                self.data.gps_satellites = msg.satellites_visible
                self.data.gps_lat = msg.lat / 1e7
                self.data.gps_lon = msg.lon / 1e7
                self.data.gps_alt = msg.alt / 1000.0
                self.data.gps_hdop = msg.eph / 100.0 if msg.eph != 65535 else 0.0
                self.data.gps_vdop = msg.epv / 100.0 if msg.epv != 65535 else 0.0
                updated = True

            elif msg_type == "GLOBAL_POSITION_INT":
                self.data.rel_alt = msg.relative_alt / 1000.0
                updated = True

            elif msg_type == "VFR_HUD":
                self.data.airspeed = msg.airspeed
                self.data.groundspeed = msg.groundspeed
                self.data.heading = msg.heading
                self.data.throttle = msg.throttle
                self.data.alt_vfr = msg.alt
                self.data.climb_rate = msg.climb
                updated = True

            elif msg_type == "ATTITUDE":
                self.data.roll = math.degrees(msg.roll)
                self.data.pitch = math.degrees(msg.pitch)
                self.data.yaw_rate = math.degrees(msg.yawspeed)
                updated = True

            elif msg_type == "SYS_STATUS":
                self.data.battery_voltage = msg.voltage_battery / 1000.0
                self.data.battery_current = msg.current_battery / 100.0
                self.data.battery_remaining = msg.battery_remaining
                updated = True

            elif msg_type == "HEARTBEAT":
                self.data.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if self._vehicle_type is None:
                    self._vehicle_type = msg.type
                self.data.mode = self._decode_mode(self._vehicle_type, msg.custom_mode)
                updated = True

            elif msg_type == "EKF_STATUS_REPORT":
                self.data.ekf_flags = msg.flags
                self.data.ekf_vel_variance = msg.velocity_variance
                self.data.ekf_pos_horiz_variance = msg.pos_horiz_variance
                self.data.ekf_pos_vert_variance = msg.pos_vert_variance
                self.data.ekf_compass_variance = msg.compass_variance
                self.data.ekf_terrain_variance = getattr(msg, "terrain_alt_variance", 0.0)
                # EKF is healthy when key flags are set
                self.data.ekf_ok = bool(msg.flags & 0x1F)
                updated = True

            elif msg_type == "VIBRATION":
                self.data.vib_x = msg.vibration_x
                self.data.vib_y = msg.vibration_y
                self.data.vib_z = msg.vibration_z
                self.data.vib_clip = msg.clipping_0 + msg.clipping_1 + msg.clipping_2
                updated = True

            elif msg_type == "RC_CHANNELS":
                self.data.rssi = msg.rssi
                updated = True

            elif msg_type == "WIND":
                self.data.wind_speed = msg.speed
                self.data.wind_dir = msg.direction
                updated = True

            elif msg_type == "STATUSTEXT":
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
                try:
                    self.data.mag_field_strength = math.sqrt(msg.xmag**2 + msg.ymag**2 + msg.zmag**2)
                    updated = True
                except Exception:
                    pass

            msg = connection.recv_match(blocking=False)

        return updated

    def get_data(self) -> TelemetryData:
        return self.data

    def _decode_mode(self, vehicle_type: int, mode_num: int) -> str:
        if vehicle_type in [2, 13, 14, 15]:
            return COPTER_MODES.get(mode_num, f"Mode {mode_num}")
        elif vehicle_type == 1:
            return PLANE_MODES.get(mode_num, f"Mode {mode_num}")
        elif vehicle_type in [10, 11]:
            return ROVER_MODES.get(mode_num, f"Mode {mode_num}")
        return f"Mode {mode_num}"

    def get_gps_status(self) -> str:
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
        messages = list(self._messages)
        messages.reverse()
        if limit:
            return messages[:limit]
        return messages
