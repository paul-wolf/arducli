"""Tests for data models."""

import pytest

from models import ConnectionConfig, DeviceInfo


class TestConnectionConfig:
    """Tests for ConnectionConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConnectionConfig()
        assert config.port is None
        assert config.baud_rate == 57600
        assert config.timeout == 2
        assert config.auto_connect is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConnectionConfig(
            port="/dev/ttyUSB0",
            baud_rate=115200,
            timeout=5,
            auto_connect=False,
        )
        assert config.port == "/dev/ttyUSB0"
        assert config.baud_rate == 115200
        assert config.timeout == 5
        assert config.auto_connect is False

    def test_connection_string_with_port(self):
        """Test connection string generation."""
        config = ConnectionConfig(port="/dev/ttyUSB0")
        assert config.connection_string == "/dev/ttyUSB0"

    def test_connection_string_without_port(self):
        """Test connection string raises error without port."""
        config = ConnectionConfig()
        with pytest.raises(ValueError, match="Port must be specified"):
            _ = config.connection_string


class TestDeviceInfo:
    """Tests for DeviceInfo model."""

    def test_device_info_creation(self, device_info):
        """Test device info creation."""
        assert device_info.system_id == 1
        assert device_info.component_id == 1
        assert device_info.autopilot_type == 3
        assert device_info.vehicle_type == 2
        assert device_info.autopilot_name == "ArduPilot"
        assert device_info.vehicle_name == "Quadrotor"
        assert device_info.port == "/dev/ttyUSB0"

    def test_device_description(self, device_info):
        """Test device description property."""
        expected = "Quadrotor running ArduPilot on /dev/ttyUSB0"
        assert device_info.description == expected

    def test_different_vehicle_types(self):
        """Test description with different vehicle types."""
        device = DeviceInfo(
            system_id=1,
            component_id=1,
            autopilot_type=3,
            vehicle_type=1,  # Fixed-wing
            autopilot_name="ArduPilot",
            vehicle_name="Fixed-wing aircraft",
            port="/dev/ttyACM0",
        )
        expected = "Fixed-wing aircraft running ArduPilot on /dev/ttyACM0"
        assert device.description == expected
