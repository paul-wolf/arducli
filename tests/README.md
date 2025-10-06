# Test Suite Documentation

This directory contains the test suite for ArduCLI. Tests use **pytest** with **mocking** to avoid requiring actual hardware.

## Test Structure

```
tests/
├── conftest.py                    # Fixtures and test configuration
├── test_models.py                 # Data model tests
├── test_parameter_service.py      # Parameter service tests
├── test_connection_service.py     # Connection service tests
├── test_mavlink_service.py        # MAVLink orchestration tests
└── test_integration.py            # Integration and import tests
```

## Running Tests

```bash
# Run all tests
.venv/bin/pytest

# Run with verbose output
.venv/bin/pytest -v

# Run specific test file
.venv/bin/pytest tests/test_models.py

# Run tests matching a pattern
.venv/bin/pytest -k "parameter"

# Generate HTML coverage report
.venv/bin/pytest --cov-report=html
# Then open htmlcov/index.html
```

## Test Coverage

Current coverage: **76%**

- **models/** - 100% ✓
- **services/parameter_service.py** - 85%
- **services/mavlink_service.py** - 92%
- **services/connection_service.py** - 54% (hardware-dependent code not tested)

## What's Tested

✅ **Models**
- ConnectionConfig initialization and validation
- DeviceInfo creation and description generation

✅ **Parameter Service**
- Parameter caching and retrieval
- Regex pattern matching
- Parameter loading (mocked)
- File save operations
- Case-insensitive lookups

✅ **Connection Service**
- Port listing and prioritization
- Last-used port persistence
- Connection state management
- Disconnect handling

✅ **MAVLink Service**
- Service orchestration
- Error handling (not connected)
- Parameter operations delegation
- Connection lifecycle

✅ **Integration**
- Module imports
- Constants validation
- Service initialization
- Cross-module integration

## What's NOT Tested

❌ Actual hardware connections
❌ Real MAVLink protocol communication
❌ Serial port I/O
❌ CLI interactive user sessions
❌ Network timeouts and retries

These are intentionally excluded as they require physical hardware or would be slow/unreliable.

## Fixtures

Available test fixtures (defined in `conftest.py`):

- `connection_config` - Test ConnectionConfig object
- `device_info` - Test DeviceInfo object
- `mock_mavlink_connection` - Mocked MAVLink connection
- `mock_serial_ports` - Mocked serial port listing
- `sample_parameters` - Sample flight controller parameters

## Adding New Tests

1. Create a new test file: `test_<feature>.py`
2. Import necessary fixtures from conftest
3. Use mocking for external dependencies (pymavlink, serial ports)
4. Follow the pattern: `class Test<Feature>` with `test_<behavior>` methods
5. Run tests to verify

Example:
```python
import pytest
from services import MyNewService

class TestMyNewService:
    @pytest.fixture
    def service(self):
        return MyNewService()

    def test_some_feature(self, service):
        result = service.do_something()
        assert result is not None
```

## CI/CD Integration

Tests are configured to run automatically via pre-commit hooks. The pytest configuration in `pyproject.toml` includes:
- Coverage tracking
- Strict marker checking
- Test discovery in `tests/` directory

To add tests to CI/CD pipeline, use:
```yaml
- run: .venv/bin/pytest --cov --cov-report=xml
```
