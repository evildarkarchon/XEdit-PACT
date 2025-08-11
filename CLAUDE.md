# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AutoQAC is a PySide6 (Qt) application for batch cleaning Bethesda game plugins using xEdit's quickautoclean. It removes Identical To Master Records (ITMs) and Undisabled References (UDRs) from game plugins for Fallout 3/NV/4 and Skyrim SE.

## Essential Commands

```bash
# Install dependencies
poetry install --with dev

# Run linting and formatting
poetry run ruff check .         # Check for linting issues
poetry run ruff check . --fix   # Auto-fix issues
poetry run ruff format .        # Format code

# Type checking (focus on critical files)
poetry run mypy AutoQAC_Interface.py state_manager.py config_manager.py

# Testing
poetry run pytest                                                          # All tests
poetry run pytest --cov=AutoQACLib --cov=AutoQAC_Interface --cov-report=html  # With HTML coverage
poetry run pytest -m unit                                                 # Unit tests only
poetry run pytest -m integration                                          # Integration tests only
poetry run pytest tests/test_state_manager.py                           # Single test file
poetry run pytest -v                                                      # Verbose output
```

## Architecture

### Centralized State Management

All application state lives in `StateManager` with the `AppState` dataclass - the single source of truth. Thread-safe access via QReadWriteLock with Qt signals for state changes.

**Key Pattern**:
```python
# ✅ CORRECT: Update through StateManager
self.state.update(is_cleaning=True, current_plugin="example.esp")

# ❌ WRONG: Never modify state directly
self.state._state.is_cleaning = True
```

### Layer Separation (Strict Boundaries)

1. **`state_manager.py`**: Pure state management, thread-safe with QMutex/QReadWriteLock
2. **`config_manager.py`**: YAML file I/O only, no Qt dependencies
3. **`cleaning_service.py`**: Business logic for plugin cleaning, no Qt
4. **`gui_controller.py`**: Mediator between GUI and business logic, handles Qt signals
5. **`cleaning_worker.py`**: QThread worker for background operations
6. **`AutoQAC_Interface.py`**: PySide6 GUI, connects via signals/slots

### Critical Threading Rules

**MUST use PySide6 threading only**:
- Use: `QThread`, `QThreadPool`, `QMutex`, `QReadWriteLock`, `QWaitCondition`
- NEVER use: Python's `threading`, `asyncio`, or `concurrent.futures`
- Inter-thread communication through Qt signals/slots only
- All shared data access must be synchronized with Qt locks

### xEdit Integration

Subprocess patterns for launching xEdit:
```bash
# MO2 Mode
"ModOrganizer.exe" run "SSEEdit.exe" -a "-QAC -autoexit -autoload \"plugin.esp\""

# Standalone Mode
"SSEEdit.exe" -a -QAC -autoexit -autoload "plugin.esp"
```

Key behaviors:
- Sequential processing (one plugin at a time)
- 5-minute timeout per plugin (configurable)
- CPU monitoring for hang detection
- Automatic skip list management in `PACT Ignore.txt`

## Test Coverage Requirements

- **Unit Tests**: Minimum 90% line coverage
- **Integration Tests**: Minimum 80% line coverage
- **Critical Paths**: 100% coverage (threading, file I/O, error handling)
- All new functionality MUST have tests
- Use `test_output_dir` fixture for temporary files (not `tmp_path`)

## Configuration System

Two YAML configs with distinct purposes:
- **`AutoQAC Main.yaml`**: Game-specific settings, skip lists, xEdit configurations
- **`AutoQAC Config.yaml`**: User paths, preferences, runtime settings

Both use `ruamel.yaml` to preserve comments and formatting.

## Key Technical Constraints

1. **File Operations**: UTF-8 encoding always, atomic operations for configs
2. **Logging**: Rotating file logs in `logs/` directory, not console output
3. **Type Annotations**: Required for all new code (Python 3.12+)
4. **Line Length**: 120 characters maximum
5. **State Updates**: Only through `StateManager.update()`, never direct manipulation
6. **Error Handling**: Qt message boxes for user-facing errors, log files for debugging

## Common Development Patterns

### Working with State
```python
# Get read-only state snapshot
state = self.state.state  # Returns frozen AppState copy

# Update state atomically
self.state.update(
    is_cleaning=True,
    total_plugins=len(plugins),
    progress=0
)
```

### Subprocess Management
```python
# Use resource-limited subprocess execution
from AutoQACLib.utils import run_process_with_realtime_output

result = run_process_with_realtime_output(
    command,
    timeout=300,
    log_callback=self._on_log_output,
    progress_callback=self._on_progress
)
```

### Configuration Access
```python
# Read config values
skip_list = self.main_config.get("AutoQAC_Data.Skip_Lists.Skyrim", [])

# Update config with thread safety
self.user_config.set("Settings.MO2_Mode", True)
self.user_config.save()
```