# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

XEdit-PACT (Plugin Auto Cleaning Tool) is a Python desktop application that automates the process of cleaning game plugins for Bethesda games using xEdit tools. It provides a GUI interface built with PySide6 (Qt6) and supports Fallout 3, Fallout New Vegas, Fallout 4, and Skyrim Special Edition.

## Development Commands

```bash
# Install dependencies
poetry install

# Run the application
poetry run python PACT_Interface.py

# Run linting
poetry run ruff check .
poetry run ruff format .  # Auto-format code

# Run type checking
poetry run mypy .
poetry run pyright

# Build executable (Windows)
poetry run pyinstaller PACT.spec
```

## Architecture Overview

### Two-Layer Architecture
1. **GUI Layer** (`PACT_Interface.py`): Handles all UI interactions using PySide6
2. **Business Logic Layer** (`PACT_Start.py`): Contains core cleaning logic and process management

### Key Components

- **UiPACTMainWin** (PACT_Interface.py): Main window class managing the entire UI state
- **PactThread** (PACT_Interface.py): QThread subclass that runs cleaning operations in background
- **ProgressEmitter** (PACT_Interface.py): Custom QObject for thread-safe progress signals
- **YamlManager** (PACT_Start.py): Singleton managing YAML configuration with atomic writes
- **Info** (PACT_Start.py): Central dataclass holding all runtime configuration and state

### Threading Model
- Main GUI thread handles user interactions
- Background QThread (`PactThread`) executes cleaning operations
- Communication via Qt signals/slots pattern
- Progress updates emitted from background thread to GUI

### Configuration Management
- Main configuration stored in `PACT Data/PACT Main.yaml`
- User-specific settings override defaults
- Game-specific plugin lists and skip lists
- Settings persistence between sessions

### Process Management
- Spawns and monitors external xEdit processes
- CPU usage monitoring with configurable thresholds
- Timeout handling for stuck processes
- Detailed logging of subprocess output

## Critical Development Notes

1. **Unicode Handling**: Always use UTF-8 encoding with error ignoring when dealing with file I/O and subprocess output
2. **Reserved Comments**: Comments marked "RESERVED" are placeholders for future updates - do not modify
3. **Thread Safety**: All GUI updates from background threads must use Qt signals
4. **Path Handling**: Support both forward and backward slashes for cross-platform compatibility
5. **Error Recovery**: Extensive try-except blocks around file operations and subprocess calls
6. **Game Detection**: Automatic detection of installed games and their mod managers (MO2/Vortex)

## Testing Approach

When testing changes:
1. Test with different game configurations (FO3, FNV, FO4, SSE)
2. Test with both MO2 and Vortex mod managers
3. Verify threading doesn't cause UI freezes
4. Check logging output in journal files
5. Test error cases (missing files, invalid paths, process failures)

## Code Style

- Type hints are mandatory (enforced by ruff)
- Use modern Python features (3.12+)
- Follow PEP 8 with ruff's extended ruleset
- Prefer pathlib over os.path for file operations
- Use dataclasses for structured data