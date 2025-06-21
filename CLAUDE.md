# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

XEdit-PACT is a PySide6 (Qt) application for batch cleaning Bethesda game plugins using xEdit's quickautoclean. The codebase follows strict architectural patterns with centralized state management and clear separation of concerns.

## Essential Commands

```bash
# Install dependencies
poetry install --with dev

# Run linting
poetry run ruff check .
poetry run ruff format .

# Run type checking
poetry run mypy PACT_Interface.py state_manager.py config_manager.py

# Run tests
pytest                                    # All tests
pytest --cov=PactLib --cov=PACT_Interface --cov-report=html  # With coverage
pytest -m unit                           # Unit tests only
pytest -m integration                    # Integration tests only
python run_tests.py                      # Custom test runner
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

# Run tests with verbose output
pytest -v

# Generate HTML coverage report
pytest --cov=PactLib --cov-report=html
# Open htmlcov/index.html to view
```

### Configuration Files

- **Main Config** (`PACT Main.yaml`): Game configurations, skip lists
- **User Config** (`PACT Config.yaml`): User settings, paths
- Both handled by `ConfigManager` with thread-safe operations

### Workflow Overview

1. User configures paths → saved to YAML configs
2. GuiController validates environment
3. CleaningWorker (QThread) processes plugins sequentially
4. For each plugin: check skip list → build command → execute → parse output
5. Progress updates via Qt signals → UI updates
6. Final summary displayed on completion