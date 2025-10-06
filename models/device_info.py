from dataclasses import dataclass
from typing import Optional


@dataclass
class DeviceInfo:
    """Information about a connected ArduPilot device."""

    system_id: int
    component_id: int
    autopilot_type: int
    vehicle_type: int
    autopilot_name: str
    vehicle_name: str
    port: str
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    board_type: Optional[str] = None

    @property
    def description(self) -> str:
        """Human-readable description of the device."""
        return f"{self.vehicle_name} running {self.autopilot_name} on {self.port}"

    @property
    def full_description(self) -> str:
        """Detailed description with version info."""
        parts = [f"{self.vehicle_name} ({self.autopilot_name})"]
        if self.firmware_version:
            parts.append(f"FW: {self.firmware_version}")
        if self.board_type:
            parts.append(f"Board: {self.board_type}")
        parts.append(f"Port: {self.port}")
        return " | ".join(parts)
