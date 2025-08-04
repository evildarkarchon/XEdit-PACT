# AutoQAC Development Guide

This file provides guidance to AI coding agents when working with code in this repository.

## Overview

AutoQAC is a PySide6 (Qt) application for batch cleaning Bethesda game plugins using xEdit's quickautoclean. The codebase follows strict architectural patterns with centralized state management and clear separation of concerns.

## Essential Commands

```bash
# Install dependencies
poetry install --with dev

# Run linting and formatting
poetry run ruff check .                  # Check for issues
poetry run ruff check . --fix           # Auto-fix issues
poetry run ruff format .                # Format code

# Run type checking
poetry run mypy AutoQAC_Interface.py AutoQACLib/*.py

# Run tests
pytest                                   # All tests  
pytest -m unit                          # Unit tests only
pytest -m integration                   # Integration tests only
pytest --cov=AutoQACLib --cov=AutoQAC_Interface --cov-report=html  # With coverage
pytest -v                               # Verbose output

# Run the application
python AutoQAC_Interface.py
```

## Architecture

### Core Design Principles

1. **Centralized State Management**: All application state lives in `StateManager` with the `AppState` dataclass. Thread-safe access via QMutex with Qt signals for state changes.

2. **Layer Separation**:
   - `state_manager.py`: Pure state management (no business logic)
   - `config_manager.py`: Configuration file handling only
   - `cleaning_service.py`: Business logic (no Qt dependencies)
   - `gui_controller.py`: Mediator between GUI and business logic
   - `cleaning_worker.py`: Thread management for background operations

3. **Dependency Injection**: Components receive dependencies through constructors. No direct coupling between layers.

### Critical Threading Rules

**MUST use PySide6 threading only**:
- Use: `QThread`, `QThreadPool`, `QMutex`, `QReadWriteLock`, `QWaitCondition`
- NEVER use: Python's `threading`, `asyncio`, or `concurrent.futures`
- All inter-thread communication through Qt signals/slots only
- All shared data access must be synchronized

### Configuration Architecture

Two separate YAML configs managed by `ConfigManager`:
- **Main Config** (`AutoQAC Data/AutoQAC Main.yaml`): Game configurations, skip lists by game
- **User Config** (`AutoQAC Data/AutoQAC Config.yaml`): User settings, tool paths

Game-specific skip lists follow pattern: `{GAME}_skip_list = ["official.esm", "dlc.esm", ...]`

### Game Integration Pattern

xEdit command building follows this pattern:
```python
# With MO2: run through MO2's virtual filesystem
f'"{mo2_path}" run "{xedit_path}" -a "-{game_mode} -QAC -autoexit -autoload \\"{plugin}\\""'
# Without MO2: direct execution
f'"{xedit_path}" -a -{game_mode} -QAC -autoexit -autoload "{plugin}"'
```

Game detection via load order file parsing: look for `Skyrim.esm` → `sse`, `Fallout4.esm` → `fo4`, etc.

### Test Coverage Requirements

- **Unit Tests**: Minimum 90% line coverage
- **Integration Tests**: Minimum 80% line coverage
- **Critical Paths**: 100% coverage (error handling, thread safety, file I/O)
- All new functionality MUST have tests
- All bug fixes MUST include regression tests

### Key Technical Constraints

1. **File Operations**: UTF-8 encoding always
2. **Logging**: Use rotating file logs in `logs/` directory, not console output
3. **Type Annotations**: Required for all new code (Python 3.12+)
4. **Line Length**: 120 characters maximum
5. **State Updates**: Only through `StateManager`, never direct manipulation

### Common Development Tasks

```bash
# Check what needs linting/formatting
poetry run ruff check . --diff

# Auto-fix linting issues
poetry run ruff check . --fix

# Run a single test file
pytest tests/test_state_manager.py

# Generate HTML coverage report
pytest --cov=AutoQACLib --cov-report=html
# Open htmlcov/index.html to view
```

### Data Flow

1. **Initialization**: `AutoQAC_Interface.py` → creates `StateManager`, two `ConfigManager` instances → `GuiController` coordinates
2. **Configuration**: User sets paths → `GuiController` validates → saves to YAML via `ConfigManager`
3. **Cleaning Process**: `GuiController` → spawns `CleaningWorker` QThread → calls `CleaningService` → subprocess execution
4. **Progress Updates**: Worker emits Qt signals → GUI updates via signal/slot connections
5. **Results**: Parsed from xEdit logs → stored in `AppState` → displayed in `CleaningProgressDialog`

### Testing Patterns

Use `tests/conftest.py` fixtures:
- `test_output_dir`: For temporary files
- `temp_test_file`: Auto-cleanup temp files
- Mock Qt components with `pytest-qt`
- Thread safety tests use `QMutex`/`QReadWriteLock` patterns