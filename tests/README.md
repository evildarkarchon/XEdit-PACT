# XEdit-PACT Test Suite

This directory contains a comprehensive test suite for the XEdit-PACT application, covering all major components and their interactions.

## Test Structure

### Unit Tests

- **`test_state_manager.py`** - Tests for the `StateManager` class and `AppState` dataclass
  - State initialization and updates
  - Signal emission and handling
  - Thread safety
  - Configuration state management
  - Progress tracking
  - Plugin result management

- **`test_config_manager.py`** - Tests for the `ConfigManager` class
  - Configuration file creation and management
  - YAML read/write operations
  - Path validation
  - Game-specific configuration
  - Settings management
  - Error handling

- **`test_utils.py`** - Tests for utility functions
  - YAML manager operations
  - Thread-safe file operations
  - Cache functionality
  - Error handling

- **`test_gui_controller.py`** - Tests for the `GuiController` class
  - File dialog operations
  - Configuration management
  - Cleaning service integration
  - Signal handling
  - Error handling

### Integration Tests

- **`test_integration.py`** - Tests for component interactions
  - State manager and config manager integration
  - GUI controller and state manager integration
  - Full configuration workflow
  - Cleaning workflow integration
  - Signal propagation
  - Error handling across components
  - Configuration persistence

### Main Interface Tests

- **`test_main_interface.py`** - Tests for the main application interface
  - `CleaningProgressDialog` functionality
  - `MainWindow` UI setup and interactions
  - Application creation and initialization
  - Event handling
  - Progress tracking UI

## Running Tests

### Prerequisites

Install the test dependencies:

```bash
poetry install --with dev
```

### Basic Test Execution

Run all tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=PactLib --cov=PACT_Interface --cov-report=html
```

### Specific Test Categories

Run only unit tests:

```bash
pytest -m unit
```

Run only integration tests:

```bash
pytest -m integration
```

Run only GUI tests:

```bash
pytest -m gui
```

Run tests excluding slow tests:

```bash
pytest -m "not slow"
```

### Test Output

- **Verbose output**: `pytest -v`
- **Detailed failure information**: `pytest -vv`
- **Stop on first failure**: `pytest -x`
- **Show local variables on failure**: `pytest -l`

### Coverage Reports

After running tests with coverage, you can view the HTML report:

```bash
# Open the coverage report in your browser
open htmlcov/index.html
```

## Test Configuration

### Pytest Configuration

The test configuration is defined in `pyproject.toml` under `[tool.pytest.ini_options]`:

- **Test discovery**: Tests are discovered in the `tests/` directory
- **Coverage**: Automatically generates coverage reports for `PactLib` and `PACT_Interface`
- **Markers**: Defines test categories (unit, integration, gui, slow)
- **Warnings**: Filters out deprecation warnings

### Fixtures

Common test fixtures are defined in `conftest.py`:

- **`qt_app`** - Qt application instance for GUI testing
- **`temp_config_file`** - Temporary configuration file
- **`config_manager`** - ConfigManager instance with temporary file
- **`state_manager`** - StateManager instance
- **`sample_config_data`** - Sample configuration data
- **`sample_plugin_list`** - Sample plugin list for testing

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Test Structure

```python
def test_feature_name(self) -> None:
    """Test description."""
    # Arrange
    # Set up test data and conditions
    
    # Act
    # Execute the code being tested
    
    # Assert
    # Verify the expected outcomes
```

### Using Fixtures

```python
def test_with_fixtures(self, config_manager: ConfigManager, state_manager: StateManager) -> None:
    """Test using fixtures."""
    # Use the provided fixtures
    config_manager.set("key", "value")
    state_manager.update(property="value")
    
    # Test assertions
    assert config_manager.get("key") == "value"
```

### Mocking

Use `unittest.mock` for mocking external dependencies:

```python
@patch("module.ClassName")
def test_with_mock(self, mock_class):
    """Test with mocked dependency."""
    mock_instance = mock_class.return_value
    mock_instance.method.return_value = "mocked_result"
    
    # Test code that uses the mocked dependency
    result = some_function()
    assert result == "mocked_result"
```

### Qt Testing

For GUI tests, use the `qt_app` fixture:

```python
def test_gui_component(self, qt_app):
    """Test GUI component."""
    # Create GUI component
    widget = SomeWidget()
    
    # Trigger events
    widget.some_signal.emit()
    
    # Process events
    qt_app.processEvents()
    
    # Assert expected behavior
    assert widget.some_property == expected_value
```

## Continuous Integration

The test suite is designed to work with CI/CD pipelines:

- **Fast execution**: Most tests complete in under a second
- **Isolated tests**: Tests don't depend on external resources
- **Comprehensive coverage**: Tests cover all major code paths
- **Clear failure messages**: Tests provide helpful error information

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running tests from the project root
2. **Qt errors**: Make sure you have a display available (use Xvfb for headless testing)
3. **File permission errors**: Tests use temporary files that should be automatically cleaned up

### Debugging Tests

To debug a failing test:

```bash
# Run specific test with debugger
pytest tests/test_specific.py::TestClass::test_method -s --pdb

# Run with maximum verbosity
pytest tests/test_specific.py::TestClass::test_method -vvv
```

### Test Maintenance

- Keep tests focused and isolated
- Use descriptive test names and docstrings
- Update tests when changing functionality
- Maintain good test coverage (aim for >90%)
- Review and refactor tests regularly 