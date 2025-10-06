"""Tests for ConnectionService."""

from unittest.mock import Mock, patch

import pytest

from services import ConnectionService


class TestConnectionService:
    """Tests for connection service."""

    @pytest.fixture
    def service(self, connection_config):
        """Create a connection service instance."""
        return ConnectionService(connection_config)

    def test_initialization(self, service, connection_config):
        """Test service initialization."""
        assert service.config == connection_config
        assert service.connection is None
        assert service.device_info is None
        assert not service.is_connected()

    def test_list_serial_ports(self, service, mock_serial_ports):
        """Test listing serial ports."""
        ports = service.list_serial_ports()
        assert len(ports) == 1
        assert "/dev/ttyUSB0" in ports

    def test_get_last_used_port_not_exists(self, service):
        """Test getting last port when file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            assert service.get_last_used_port() is None

    def test_get_last_used_port_exists(self, service, tmp_path):
        """Test getting last port when file exists."""
        # Create a temp file with port info
        port_file = tmp_path / "last_port"
        port_file.write_text("/dev/ttyACM0")

        with patch.object(service, "LAST_PORT_FILE", str(port_file)):
            port = service.get_last_used_port()
            assert port == "/dev/ttyACM0"

    def test_save_last_used_port(self, service, tmp_path):
        """Test saving last used port."""
        port_file = tmp_path / "last_port"

        with patch.object(service, "LAST_PORT_FILE", str(port_file)):
            service.save_last_used_port("/dev/ttyUSB0")
            assert port_file.read_text() == "/dev/ttyUSB0"

    def test_prioritize_ports_with_last_port(self, service):
        """Test port prioritization with last used port."""
        ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"]

        with patch.object(service, "get_last_used_port", return_value="/dev/ttyACM0"):
            prioritized = service.prioritize_ports(ports)
            assert prioritized[0] == "/dev/ttyACM0"
            assert len(prioritized) == 3

    def test_prioritize_ports_without_last_port(self, service):
        """Test port prioritization without last used port."""
        ports = ["/dev/ttyUSB0", "/dev/ttyUSB1"]

        with patch.object(service, "get_last_used_port", return_value=None):
            prioritized = service.prioritize_ports(ports)
            assert prioritized == ports

    def test_prioritize_ports_last_port_not_in_list(self, service):
        """Test prioritization when last port not in current list."""
        ports = ["/dev/ttyUSB0", "/dev/ttyUSB1"]

        with patch.object(service, "get_last_used_port", return_value="/dev/ttyACM0"):
            prioritized = service.prioritize_ports(ports)
            assert prioritized == ports

    def test_disconnect_when_connected(self, service, mock_mavlink_connection):
        """Test disconnecting when connected."""
        service.connection = mock_mavlink_connection
        service.device_info = Mock()

        service.disconnect()

        assert service.connection is None
        assert service.device_info is None
        mock_mavlink_connection.close.assert_called_once()

    def test_disconnect_when_not_connected(self, service):
        """Test disconnecting when not connected."""
        service.disconnect()  # Should not raise error
        assert service.connection is None

    def test_is_connected(self, service, mock_mavlink_connection):
        """Test connection status check."""
        assert not service.is_connected()

        service.connection = mock_mavlink_connection
        assert service.is_connected()

        service.connection = None
        assert not service.is_connected()

    def test_get_connection(self, service, mock_mavlink_connection):
        """Test getting connection object."""
        assert service.get_connection() is None

        service.connection = mock_mavlink_connection
        assert service.get_connection() == mock_mavlink_connection

    def test_get_device_info(self, service, device_info):
        """Test getting device info."""
        assert service.get_device_info() is None

        service.device_info = device_info
        assert service.get_device_info() == device_info
