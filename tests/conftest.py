"""Pytest fixtures and configuration."""

from unittest.mock import MagicMock, Mock

import pytest

from models import ConnectionConfig, DeviceInfo


@pytest.fixture
def connection_config():
    """Create a test connection configuration."""
    return ConnectionConfig(
        port="/dev/ttyUSB0",
        baud_rate=57600,
        timeout=2,
        auto_connect=False,
    )


@pytest.fixture
def device_info():
    """Create a test device info object."""
    return DeviceInfo(
        system_id=1,
        component_id=1,
        autopilot_type=3,
        vehicle_type=2,
        autopilot_name="ArduPilot",
        vehicle_name="Quadrotor",
        port="/dev/ttyUSB0",
    )


@pytest.fixture
def mock_mavlink_connection():
    """Create a mock MAVLink connection."""
    mock = MagicMock()
    mock.target_system = 1
    mock.target_component = 1

    # Mock heartbeat message
    heartbeat = Mock()
    heartbeat.type = 2  # Quadrotor
    heartbeat.autopilot = 3  # ArduPilot
    mock.recv_match.return_value = heartbeat
    mock.wait_heartbeat.return_value = True

    return mock


@pytest.fixture
def mock_serial_ports(mocker):
    """Mock serial port listing."""
    mock_port = Mock()
    mock_port.device = "/dev/ttyUSB0"

    mocker.patch(
        "serial.tools.list_ports.comports",
        return_value=[mock_port],
    )
    return ["/dev/ttyUSB0"]


@pytest.fixture
def sample_parameters():
    """Sample flight controller parameters."""
    return {
        "SYSID_THISMAV": 1.0,
        "SYSID_MYGCS": 255.0,
        "RC1_OPTION": 0.0,
        "RC2_OPTION": 0.0,
        "ARMING_CHECK": 1.0,
        "BATT_MONITOR": 4.0,
    }
