"""Tests for MAVLinkService."""

from unittest.mock import Mock, patch

import pytest

from services import MAVLinkService


class TestMAVLinkService:
    """Tests for MAVLink service orchestration."""

    @pytest.fixture
    def service(self, connection_config):
        """Create a MAVLink service instance."""
        return MAVLinkService(connection_config)

    def test_initialization(self, service):
        """Test service initialization."""
        assert service.connection_service is not None
        assert service.parameter_service is not None
        assert not service.is_connected()

    def test_is_connected_delegates_to_connection_service(self, service):
        """Test that is_connected delegates to connection service."""
        assert not service.is_connected()

        # Mock the connection service
        service.connection_service.connection = Mock()
        assert service.is_connected()

    def test_disconnect(self, service):
        """Test disconnect clears both connection and parameters."""
        # Set up some state
        service.connection_service.connection = Mock()
        service.parameter_service.parameters = {"TEST": 1.0}

        service.disconnect()

        assert service.connection_service.connection is None
        assert len(service.parameter_service.parameters) == 0

    def test_get_device_info(self, service, device_info):
        """Test getting device info."""
        assert service.get_device_info() is None

        service.connection_service.device_info = device_info
        assert service.get_device_info() == device_info

    def test_load_parameters_when_not_connected(self, service):
        """Test loading parameters when not connected raises error."""
        with pytest.raises(RuntimeError, match="Not connected to a device"):
            service.load_parameters()

    def test_load_parameters_when_connected(self, service, sample_parameters, mock_mavlink_connection):
        """Test loading parameters when connected."""
        service.connection_service.connection = mock_mavlink_connection

        with patch.object(service.parameter_service, "load_parameters", return_value=sample_parameters):
            params = service.load_parameters()
            assert params == sample_parameters

    def test_get_parameter(self, service, sample_parameters):
        """Test getting a parameter."""
        service.parameter_service.parameters = sample_parameters
        assert service.get_parameter("SYSID_THISMAV") == 1.0
        assert service.get_parameter("NONEXISTENT") is None

    def test_get_parameters_matching(self, service, sample_parameters):
        """Test getting parameters with regex."""
        service.parameter_service.parameters = sample_parameters
        rc_params = service.get_parameters_matching(r"RC\d+_OPTION")
        assert len(rc_params) == 2

    def test_set_parameter_when_not_connected(self, service):
        """Test setting parameter when not connected raises error."""
        with pytest.raises(RuntimeError, match="Not connected to a device"):
            service.set_parameter("TEST_PARAM", 123.0)

    def test_set_parameter_when_connected(self, service, mock_mavlink_connection):
        """Test setting parameter when connected."""
        service.connection_service.connection = mock_mavlink_connection

        with patch.object(service.parameter_service, "set_parameter", return_value=True):
            result = service.set_parameter("TEST_PARAM", 123.0)
            assert result is True

    def test_get_all_parameters(self, service, sample_parameters):
        """Test getting all parameters."""
        service.parameter_service.parameters = sample_parameters
        all_params = service.get_all_parameters()
        assert len(all_params) == 6

    def test_save_parameters_to_file(self, service, sample_parameters, tmp_path):
        """Test saving parameters to file."""
        service.parameter_service.parameters = sample_parameters
        filepath = tmp_path / "params.txt"

        result = service.save_parameters_to_file(str(filepath))
        assert result is True
        assert filepath.exists()

    def test_has_parameters(self, service, sample_parameters):
        """Test checking if parameters are loaded."""
        assert not service.has_parameters()

        service.parameter_service.parameters = sample_parameters
        assert service.has_parameters()
