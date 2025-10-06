"""Integration tests for the system."""


class TestImports:
    """Test that all modules can be imported correctly."""

    def test_import_models(self):
        """Test importing models."""
        from models import ConnectionConfig, DeviceInfo

        assert ConnectionConfig is not None
        assert DeviceInfo is not None

    def test_import_services(self):
        """Test importing services."""
        from services import ConnectionService, MAVLinkService, ParameterService

        assert ConnectionService is not None
        assert MAVLinkService is not None
        assert ParameterService is not None

    def test_import_interfaces(self):
        """Test importing interfaces."""
        from interfaces import CLIInterface

        assert CLIInterface is not None

    def test_import_constants(self):
        """Test importing constants."""
        from constants import MAV_AUTOPILOT, MAV_TYPE, RC_OPTION_DESCRIPTIONS

        assert MAV_AUTOPILOT is not None
        assert MAV_TYPE is not None
        assert RC_OPTION_DESCRIPTIONS is not None
        assert len(MAV_TYPE) > 0
        assert len(MAV_AUTOPILOT) > 0


class TestConstants:
    """Test constants are properly defined."""

    def test_mav_type_values(self):
        """Test MAV_TYPE contains expected values."""
        from constants import MAV_TYPE

        assert 1 in MAV_TYPE  # Fixed-wing
        assert 2 in MAV_TYPE  # Quadrotor
        assert MAV_TYPE[2] == "Quadrotor"

    def test_mav_autopilot_values(self):
        """Test MAV_AUTOPILOT contains expected values."""
        from constants import MAV_AUTOPILOT

        assert 2 in MAV_AUTOPILOT
        assert MAV_AUTOPILOT[2] == "ArduPilot"
        assert 3 in MAV_AUTOPILOT
        assert MAV_AUTOPILOT[3] == "OpenPilot"

    def test_rc_options_defined(self):
        """Test RC options are defined."""
        from constants import RC_OPTION_DESCRIPTIONS

        assert isinstance(RC_OPTION_DESCRIPTIONS, dict)
        assert len(RC_OPTION_DESCRIPTIONS) > 0


class TestServiceIntegration:
    """Test services work together."""

    def test_mavlink_service_initialization(self):
        """Test MAVLink service can be initialized."""
        from models import ConnectionConfig
        from services import MAVLinkService

        config = ConnectionConfig(auto_connect=False)
        service = MAVLinkService(config)

        assert service is not None
        assert not service.is_connected()
        assert service.connection_service is not None
        assert service.parameter_service is not None

    def test_cli_interface_initialization(self):
        """Test CLI interface can be initialized."""
        from interfaces import CLIInterface
        from models import ConnectionConfig

        config = ConnectionConfig(auto_connect=False)
        cli = CLIInterface(config)

        assert cli is not None
        assert cli.mavlink_service is not None
