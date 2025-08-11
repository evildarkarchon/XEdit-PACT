# AutoQAC Development Guide

This file provides guidance for AI coding agents working with the AutoQAC codebase.

## Overview

AutoQAC is a PySide6 (Qt) application for batch cleaning Bethesda game plugins using xEdit's quickautoclean. The application automates the process of removing Identical To Master Records (ITMs) and Undisabled References (UDRs) from game plugins for Fallout 3/NV/4 and Skyrim SE.

## Essential Commands

```bash
# Install dependencies
poetry install --with dev

# Run linting and formatting
poetry run ruff check .
poetry run ruff format .

# Type checking (critical files only)
poetry run mypy AutoQAC_Interface.py state_manager.py config_manager.py

# Testing with coverage
poetry run pytest                        # All tests
poetry run pytest --cov=AutoQACLib --cov=AutoQAC_Interface --cov-report=html
poetry run pytest -m unit               # Unit tests only  
poetry run pytest -m integration        # Integration tests only
```

## Architecture

### Centralized State Management Pattern

**Core Principle**: All application state lives in `StateManager` with the `AppState` dataclass. This is the single source of truth.

```python
# ✅ CORRECT: Update state through StateManager
self.state.update(is_cleaning=True, current_plugin="example.esp")

# ❌ WRONG: Never modify state directly
self.state._state.is_cleaning = True
```

The `AppState` dataclass tracks configuration paths, runtime state, progress, and results. Use `state.update(**kwargs)` for atomic updates with signal emission.

### Layer Separation (Strict Boundaries)

1. **`state_manager.py`**: Pure state management, no business logic, thread-safe with QMutex/QReadWriteLock
2. **`config_manager.py`**: YAML file I/O only, no Qt dependencies, UTF-8 encoding
3. **`cleaning_service.py`**: Business logic for plugin cleaning, no Qt dependencies, pure Python
4. **`gui_controller.py`**: Mediator between GUI and business logic, handles Qt signals
5. **`cleaning_worker.py`**: QThread worker for background operations, emits progress signals
6. **`AutoQAC_Interface.py`**: PySide6 GUI, connects to controller via signals/slots

### Threading (PySide6 Only)

**CRITICAL**: Use only PySide6 threading primitives:
```python
from PySide6.QtCore import QThread, QMutex, QReadWriteLock, QWaitCondition

# ✅ CORRECT: QThread worker pattern
class CleaningWorker(QThread):
    progress = Signal(int, int)  # current, total
    def run(self):
        # Worker logic here
        
# ❌ WRONG: Never use Python threading
import threading  # Don't do this
```

All inter-thread communication through Qt signals/slots. All shared data access must be synchronized with Qt locks.

## Critical Workflows

### xEdit Integration Pattern

The app launches xEdit subprocesses with specific command patterns:
```bash
# MO2 Mode
"ModOrganizer.exe" run "SSEEdit.exe" -a "-QAC -autoexit -autoload \"plugin.esp\""

# Standalone Mode  
"SSEEdit.exe" -a -QAC -autoexit -autoload "plugin.esp"
```

Game detection via loadorder.txt master files: `Fallout4.esm`, `Skyrim.esm`, etc.

### Subprocess Management

- One plugin cleaned at a time sequentially
- 5-minute timeout per plugin (configurable)
- CPU monitoring to detect hangs (0% usage = error)
- Log parsing for ITM/UDR detection patterns
- Automatic skip list management in `PACT Ignore.txt`

### Configuration System

Two YAML configs with different purposes:
- **Main Config** (`AutoQAC Main.yaml`): Game-specific settings, skip lists
- **User Config** (`AutoQAC Config.yaml`): User paths, preferences

Both use `ruamel.yaml` for preservation of comments and formatting.

## Testing Requirements

- **Unit Tests**: 90% minimum line coverage
- **Integration Tests**: 80% minimum line coverage  
- **Critical Paths**: 100% coverage (threading, file I/O, error handling)
- Use `test_output_dir` fixture instead of `tmp_path` for temporary files
- All Qt code requires `pytest-qt` for proper signal testing

## Project-Specific Patterns

### Error Handling
- Log to rotating files in `logs/` directory, not console
- Use Qt message boxes for user-facing errors
- Subprocess errors trigger automatic skip list updates

### File Operations
- Always UTF-8 encoding with error handling
- Path objects preferred over strings
- Atomic file operations for configs

### State Updates
- Only through `StateManager.update()` method
- Emit specific signals for UI updates
- Batch related updates in single call

This codebase prioritizes thread safety, maintainability, and robust subprocess management for external tool integration.