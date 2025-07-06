# Test Output Directory Setup Documentation

## Overview

The test suite has been updated to use a dedicated output directory (`tests/test_output/`) for all test-related files. This provides better organization and ensures that test artifacts don't clutter the main project directory.

## Changes Made

### 1. Directory Structure

- **Created**: `tests/test_output/` directory
- **Added**: `.gitkeep` file to ensure the directory is tracked by git
- **Added**: `README.md` with usage instructions

### 2. Git Configuration

Updated `.gitignore` to ignore test output files while preserving the directory:

```gitignore
# Test output directory - ignore contents but keep the directory
tests/test_output/*
!tests/test_output/.gitkeep
```

### 3. Test Fixtures (conftest.py)

Added new fixtures for test file management:

- `test_output_dir`: Returns the Path to the test output directory
- `temp_test_file`: Creates a temporary file with automatic cleanup
- `temp_test_config_file`: Creates a temporary YAML config file
- `test_file_factory`: Factory function for creating multiple test files
- Updated `temp_config_file`: Now uses the test output directory

### 4. Logging Configuration

Updated `TestLoggingConfig` in `logging_config.py` to use the test output directory:

```python
log_dir: Path | str = "tests/test_output"
```

### 5. Test Validation

Created `test_output_directory.py` to validate the new setup:

- Tests that the directory exists and is accessible
- Verifies that fixtures work correctly
- Ensures test files are created in the correct location
- Confirms automatic cleanup works

## Benefits

1. **Organization**: All test output is centralized in one location
2. **Git Hygiene**: Test files are automatically ignored by git
3. **Cleanup**: Automatic cleanup of temporary files after tests
4. **Consistency**: All tests use the same output directory structure
5. **Debugging**: Test artifacts are preserved until the next test run

## Usage Examples

### Using the Test File Factory

```python
def test_yaml_processing(test_file_factory: callable) -> None:
    """Test YAML processing with the file factory."""
    # Create a test YAML file
    yaml_file = test_file_factory("test_config.yaml", "key: value")
    
    # Use the file in your test
    assert yaml_file.exists()
    # ... test logic ...
    
    # File is automatically cleaned up after the test
```

### Using Individual Fixtures

```python
def test_config_file(temp_test_config_file: Path) -> None:
    """Test configuration file handling."""
    # Create config content
    temp_test_config_file.write_text("setting: enabled")
    
    # Use in test
    config_manager = ConfigManager(temp_test_config_file)
    # ... test logic ...
    
    # File is automatically cleaned up
```

## Migration Guide

For existing tests that use `tempfile.NamedTemporaryFile`:

**Before:**
```python
def test_something():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        f.write("content")
        file_path = Path(f.name)
    
    try:
        # test logic
        pass
    finally:
        file_path.unlink(missing_ok=True)
```

**After:**
```python
def test_something(test_file_factory: callable):
    file_path = test_file_factory("test.yaml", "content")
    
    # test logic
    # automatic cleanup
```

## Verification

To verify the setup is working correctly:

1. Run tests: `poetry run pytest tests/test_output_directory.py -v`
2. Check directory contents: `ls tests/test_output/`
3. Verify git status: `git status tests/test_output/`

The test output directory should contain only the log file and documentation files, with all temporary test files automatically cleaned up.
