from dataclasses import dataclass


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

    @property
    def description(self) -> str:
        """Human-readable description of the device."""
        return f"{self.vehicle_name} running {self.autopilot_name} on {self.port}"
