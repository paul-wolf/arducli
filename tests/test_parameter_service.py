"""Tests for ParameterService."""

from unittest.mock import Mock

import pytest

from services import ParameterService


class TestParameterService:
    """Tests for parameter service."""

    @pytest.fixture
    def service(self):
        """Create a parameter service instance."""
        return ParameterService()

    def test_initialization(self, service):
        """Test service initialization."""
        assert service.parameters == {}
        assert not service.has_parameters()

    def test_get_parameter_empty(self, service):
        """Test getting parameter when cache is empty."""
        assert service.get_parameter("SYSID_THISMAV") is None

    def test_get_parameter_case_insensitive(self, service, sample_parameters):
        """Test parameter retrieval is case-insensitive."""
        service.parameters = sample_parameters
        assert service.get_parameter("sysid_thismav") == 1.0
        assert service.get_parameter("SYSID_THISMAV") == 1.0
        assert service.get_parameter("SysId_ThisMav") == 1.0

    def test_get_parameters_matching_regex(self, service, sample_parameters):
        """Test regex pattern matching for parameters."""
        service.parameters = sample_parameters

        # Match RC parameters
        rc_params = service.get_parameters_matching(r"RC\d+_OPTION")
        assert len(rc_params) == 2
        assert "RC1_OPTION" in rc_params
        assert "RC2_OPTION" in rc_params

        # Match SYSID parameters
        sysid_params = service.get_parameters_matching(r"SYSID_.*")
        assert len(sysid_params) == 2
        assert "SYSID_THISMAV" in sysid_params
        assert "SYSID_MYGCS" in sysid_params

    def test_get_parameters_matching_invalid_regex(self, service, sample_parameters):
        """Test invalid regex returns empty dict."""
        service.parameters = sample_parameters
        result = service.get_parameters_matching("[invalid")
        assert result == {}

    def test_get_all_parameters(self, service, sample_parameters):
        """Test getting all parameters."""
        service.parameters = sample_parameters
        all_params = service.get_all_parameters()
        assert len(all_params) == 6
        assert all_params == sample_parameters
        # Ensure it's a copy
        all_params["NEW_PARAM"] = 999.0
        assert "NEW_PARAM" not in service.parameters

    def test_has_parameters(self, service, sample_parameters):
        """Test has_parameters check."""
        assert not service.has_parameters()
        service.parameters = sample_parameters
        assert service.has_parameters()

    def test_load_parameters(self, service, mock_mavlink_connection):
        """Test loading parameters from connection."""
        # Mock parameter messages - using strings with null terminator
        param_messages = [
            Mock(
                param_id="SYSID_THISMAV\x00",
                param_value=1.0,
                param_count=3,
                param_index=0,
            ),
            Mock(
                param_id="SYSID_MYGCS\x00",
                param_value=255.0,
                param_count=3,
                param_index=1,
            ),
            Mock(
                param_id="ARMING_CHECK\x00",
                param_value=1.0,
                param_count=3,
                param_index=2,
            ),
        ]

        mock_mavlink_connection.recv_match.side_effect = param_messages

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        params = service.load_parameters(mock_mavlink_connection, on_progress)

        assert len(params) == 3
        assert params["SYSID_THISMAV"] == 1.0
        assert params["SYSID_MYGCS"] == 255.0
        assert params["ARMING_CHECK"] == 1.0

        # Check progress was called
        assert len(progress_calls) == 3
        assert progress_calls[0] == (1, 3)
        assert progress_calls[-1] == (3, 3)

    def test_save_to_file(self, service, sample_parameters, tmp_path):
        """Test saving parameters to file."""
        service.parameters = sample_parameters
        filepath = tmp_path / "test_params.txt"

        success = service.save_to_file(str(filepath))
        assert success
        assert filepath.exists()

        # Read back and verify
        content = filepath.read_text()
        assert "SYSID_THISMAV: 1.0" in content
        assert "SYSID_MYGCS: 255.0" in content
        assert "RC1_OPTION: 0.0" in content

    def test_save_to_file_invalid_path(self, service, sample_parameters):
        """Test saving to invalid path fails gracefully."""
        service.parameters = sample_parameters
        success = service.save_to_file("/invalid/path/that/does/not/exist/params.txt")
        assert not success
