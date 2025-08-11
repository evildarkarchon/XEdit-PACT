# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AutoQAC is a PySide6 (Qt) application for batch cleaning Bethesda game plugins using xEdit's quickautoclean. It removes Identical To Master Records (ITMs) and Undisabled References (UDRs) from game plugins for Fallout 3/NV/4 and Skyrim SE.

## Essential Commands

```bash
# Install dependencies
poetry install --with dev

# Run linting and formatting
poetry run ruff check .                  # Check for issues
poetry run ruff check . --fix           # Auto-fix issues
poetry run ruff check . --diff          # Show what needs fixing
poetry run ruff format .                # Format code

# Run type checking
poetry run mypy AutoQAC_Interface.py AutoQACLib/*.py

# Run tests
pytest                                   # All tests  
pytest -m unit                          # Unit tests only
pytest -m integration                   # Integration tests only
pytest tests/test_state_manager.py     # Single test file
pytest -v                               # Verbose output
pytest --cov=AutoQACLib --cov=AutoQAC_Interface --cov-report=html  # With coverage

# Run the application
python AutoQAC_Interface.py
```

## Architecture

### Core Components

1. **StateManager** (`state_manager.py`): Centralized thread-safe state management with `AppState` dataclass. All state mutations go through here with QMutex/QReadWriteLock protection and Qt signals for changes.

2. **ConfigManager** (`config_manager.py`): YAML configuration file I/O. Two instances used:
   - Main config (`AutoQAC Data/AutoQAC Main.yaml`): Game configs, skip lists
   - User config (`AutoQAC Data/AutoQAC Config.yaml`): User settings, paths

3. **CleaningService** (`cleaning_service.py`): Pure business logic for plugin cleaning. No Qt dependencies. Handles subprocess execution and output parsing.

4. **GuiController** (`gui_controller.py`): Mediator between GUI and business logic. Manages worker threads and coordinates state updates.

5. **CleaningWorker** (`cleaning_worker.py`): QThread for background cleaning operations. Communicates via Qt signals only.

6. **AutoQAC_Interface.py**: Main entry point and GUI implementation using PySide6.

### Critical Threading Rules

**MUST use PySide6 threading exclusively**:
- Use: `QThread`, `QThreadPool`, `QMutex`, `QReadWriteLock`, `QWaitCondition`
- NEVER use: Python's `threading`, `asyncio`, or `concurrent.futures`
- All inter-thread communication through Qt signals/slots only
- All shared data access must be synchronized via StateManager
- Resource limit for concurrent subprocesses controlled by `max_concurrent_subprocesses` in AppState

### Key Technical Constraints

- **Python Version**: 3.12+ required
- **File Encoding**: UTF-8 always
- **Logging**: Rotating file logs in `logs/` directory (not console)
- **Type Annotations**: Required for all new code
- **Line Length**: 120 characters maximum
- **State Updates**: Only through StateManager, never direct manipulation
- **Test Coverage**: Unit tests 90%, integration tests 80%, critical paths 100%

### Test Coverage Requirements

- **Unit Tests**: Minimum 90% line coverage
- **Integration Tests**: Minimum 80% line coverage  
- **Critical Paths**: 100% coverage (error handling, thread safety, file I/O)
- All new functionality MUST have tests
- All bug fixes MUST include regression tests
- Tests use fixtures from `conftest.py` with test output in `tests/test_output/`

### Workflow

1. User configures paths via GUI → saved to YAML configs
2. GuiController validates environment (xEdit.exe, load order files)
3. CleaningWorker (QThread) processes plugins sequentially
4. For each plugin:
   - Check skip list in main config
   - Build xEdit command with QAC flags
   - Execute subprocess with timeout (default 300s)
   - Parse output for ITMs/UDRs/deleted navmeshes
   - Update state and emit progress signals
5. GUI updates based on Qt signals
6. Final summary displayed on completion

### Configuration Files

- `pyproject.toml`: Poetry dependencies, tool configs (ruff, mypy, pytest, coverage)
- `AutoQAC Data/AutoQAC Main.yaml`: Game configurations, plugin skip lists
- `AutoQAC Data/AutoQAC Config.yaml`: User settings, file paths
- `PACT Settings.yaml`: Legacy config for backward compatibility
- `PACT Ignore.yaml`: Additional ignore list for plugins
- Both YAML files managed by ConfigManager with thread-safe operations

### Project Structure

```
XEdit-PACT/
├── AutoQAC_Interface.py       # Main GUI application entry point
├── AutoQACLib/                # Core library modules
│   ├── state_manager.py       # Centralized state management
│   ├── config_manager.py      # Configuration file handling
│   ├── cleaning_service.py    # Business logic (no Qt)
│   ├── gui_controller.py      # GUI-business logic mediator
│   ├── cleaning_worker.py     # QThread for cleaning operations
│   ├── logging_config.py      # Logging setup and configuration
│   └── utils.py               # Utility functions
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest fixtures
│   ├── test_output/          # Test artifacts directory
│   └── test_*.py             # Test modules
├── AutoQAC Data/             # Configuration files
└── logs/                     # Application logs (auto-created)
```

### Dependency Injection Pattern

Components receive dependencies through constructors:
```python
def __init__(self, state: StateManager, config: ConfigManager):
    self.state = state
    self.config = config
```

No global variables or direct imports between layers.