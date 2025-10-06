from dataclasses import dataclass
from typing import Optional


@dataclass
class ConnectionConfig:
    """Configuration for MAVLink connection."""

    port: Optional[str] = None
    baud_rate: int = 57600
    timeout: int = 2
    auto_connect: bool = True

    @property
    def connection_string(self) -> str:
        """Generate MAVLink connection string."""
        if self.port:
            return self.port
        raise ValueError("Port must be specified")
