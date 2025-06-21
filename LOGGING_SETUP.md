# XEdit-PACT Logging Configuration

## Overview

XEdit-PACT now uses a centralized rotating file logging system instead of console output. This provides better debugging capabilities and log persistence while maintaining a clean console interface.

## Features

- **Rotating File Logs**: Log files automatically rotate when they reach 5MB in size
- **Backup Management**: Keeps up to 5 backup log files
- **UTF-8 Encoding**: Proper support for international characters
- **Structured Format**: Consistent timestamp and log level formatting
- **Thread-Safe**: Safe for multi-threaded operations
- **Separate Test Logs**: Tests use a separate log file with smaller rotation size

## Log Files

### Main Application
- **Location**: `logs/xedit_pact.log`
- **Max Size**: 5MB
- **Backup Count**: 5 files
- **Rotation**: `xedit_pact.log.1`, `xedit_pact.log.2`, etc.

### Tests
- **Location**: `logs/test_xedit_pact.log`
- **Max Size**: 1MB
- **Backup Count**: 3 files
- **Rotation**: `test_xedit_pact.log.1`, `test_xedit_pact.log.2`, etc.

### Migration Script
- **Location**: `logs/migration.log`
- **Max Size**: 5MB
- **Backup Count**: 5 files

## Log Levels

- **Console Output**: WARNING and above (errors and warnings only)
- **File Output**: DEBUG and above (all log levels)
- **Format**: `YYYY-MM-DD HH:MM:SS - module_name - LEVEL - message`

## Usage

### In Application Code

```python
from PactLib.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Application started")
logger.warning("Configuration issue detected")
logger.error("Failed to process plugin")
```

### Setup Logging

```python
from PactLib.logging_config import setup_logging, log_startup_info

# Setup logging (called automatically in main application)
setup_logging()

# Log startup information
logger = get_logger(__name__)
log_startup_info(logger, "XEdit-PACT", "2.0.0")
```

### Custom Configuration

```python
from PactLib.logging_config import setup_logging

# Custom logging setup
setup_logging(
    log_dir="custom_logs",
    log_file="my_app.log",
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=10,
    console_level=logging.INFO,
    file_level=logging.DEBUG
)
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `log_dir` | `"logs"` | Directory to store log files |
| `log_file` | `"xedit_pact.log"` | Main log file name |
| `max_bytes` | `5MB` | Maximum file size before rotation |
| `backup_count` | `5` | Number of backup files to keep |
| `console_level` | `WARNING` | Log level for console output |
| `file_level` | `DEBUG` | Log level for file output |
| `encoding` | `"utf-8"` | File encoding |

## Benefits

1. **Persistent Logs**: All application activity is recorded for debugging
2. **Automatic Rotation**: Prevents log files from growing too large
3. **Clean Console**: Only important messages appear in console
4. **Thread Safety**: Safe for concurrent operations
5. **Centralized Configuration**: Easy to modify logging behavior
6. **Separate Test Logs**: Test output doesn't interfere with application logs

## Migration from Console Logging

The application automatically migrates from console-only logging to file-based logging. No user action is required. The console will now only show warnings and errors, while detailed logs are written to files.

## Troubleshooting

### Log Files Not Created
- Ensure the application has write permissions to the `logs` directory
- Check that the `logs` directory exists (created automatically)

### Large Log Files
- Log files automatically rotate at 5MB
- Old backup files are automatically deleted
- You can manually delete old log files if needed

### Missing Log Messages
- Check the log level configuration
- Ensure the correct log file is being checked
- Verify file permissions and disk space 