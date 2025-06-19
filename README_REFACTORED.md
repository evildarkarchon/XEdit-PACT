# XEdit-PACT Refactored Architecture

## Overview

This is a refactored version of XEdit-PACT that addresses the complex state management issues in the original codebase. The new architecture provides:

- **Centralized state management** through a single `StateManager`
- **Clear separation of concerns** with distinct modules for each responsibility
- **Dependency injection** instead of global variables
- **Simplified threading** with consistent patterns
- **Better testability** and maintainability

## Architecture Components

### Core Modules

1. **`state_manager.py`**
   - Central state store with `AppState` dataclass
   - Thread-safe state updates with Qt signals
   - No external dependencies on business logic

2. **`config_manager.py`**
   - Single interface for all configuration
   - Wraps YAML file operations
   - Provides typed configuration access

3. **`cleaning_service.py`**
   - Pure business logic for plugin cleaning
   - No Qt dependencies
   - Returns result objects instead of side effects

4. **`cleaning_worker.py`**
   - QThread implementation for background processing
   - Clear signal-based communication
   - Simple start/stop interface

5. **`gui_controller.py`**
   - Mediates between GUI and business logic
   - Handles user actions and coordinates responses
   - Manages worker threads

6. **`PACT_Interface_Refactored.py`**
   - Pure UI code with no business logic
   - Responds to state changes via signals
   - Clean separation from processing logic

## Key Design Principles

### 1. Single Source of Truth
All application state lives in `StateManager`. No more scattered state across globals, instance variables, and files.

### 2. Unidirectional Data Flow
```
User Action → Controller → State Update → UI Update
                ↓
           Service/Worker
```

### 3. Dependency Injection
All dependencies are passed through constructors, making the code testable and dependencies explicit.

### 4. Clear Module Boundaries
Each module has a single, well-defined responsibility. No mixing of UI and business logic.

## Usage

### Running the Refactored Version

```bash
# First, migrate your existing configuration
python migrate_to_refactored.py

# Then run the refactored interface
python PACT_Interface.py
```

### Development Commands

```bash
# Install dependencies
poetry install

# Run linting
poetry run ruff check .
poetry run ruff format .

# Run type checking
poetry run mypy PACT_Interface.py state_manager.py config_manager.py
```

## Migration from Old Architecture

### Automatic Migration
Run the migration script to automatically transfer your existing configuration:
```bash
python migrate_to_refactored.py
```

### Manual Integration
If you want to gradually integrate the new architecture:

1. Add the new modules to your project
2. Update imports one feature at a time
3. Replace global state access with `StateManager`
4. Remove old code once fully migrated

## Example: Adding a New Feature

Here's how to add a new feature in the refactored architecture:

```python
# 1. Add state to AppState (state_manager.py)
@dataclass
class AppState:
    # ... existing fields ...
    new_feature_enabled: bool = False

# 2. Add configuration if needed (config_manager.py)
def get_new_feature_config(self):
    return self.get("PACT_Settings.NewFeature", {})

# 3. Add business logic (new_service.py or cleaning_service.py)
def process_new_feature(self, data: str) -> Result:
    # Pure function - no side effects
    return Result(success=True, data=processed_data)

# 4. Add UI control (gui_controller.py)
def toggle_new_feature(self, enabled: bool):
    self.state.update(new_feature_enabled=enabled)
    self.config.set("PACT_Settings.NewFeature.Enabled", enabled)

# 5. Update UI (PACT_Interface.py)
@Slot(str, object)
def _on_state_changed(self, prop: str, value: object):
    if prop == "new_feature_enabled":
        self.new_feature_button.setChecked(value)
```

## Testing

The refactored architecture makes testing much easier:

```python
# Test state management
def test_state_update():
    state = StateManager()
    state.update(is_cleaning=True)
    assert state.state.is_cleaning == True

# Test business logic (no Qt required)
def test_cleaning_service():
    config = MockConfig()
    state = MockState()
    service = CleaningService(config, state)
    result = service.clean_plugin("test.esp")
    assert result.success

# Test configuration
def test_config_manager():
    config = ConfigManager(test_path)
    config.set("test.key", "value")
    assert config.get("test.key") == "value"
```

## Benefits Over Old Architecture

1. **Maintainability**: Clear module boundaries make changes easier
2. **Debugging**: State changes are traceable through signals
3. **Testing**: Pure functions and dependency injection
4. **Performance**: Fewer redundant updates and file operations
5. **Reliability**: Thread-safe state management prevents races
6. **Extensibility**: Easy to add new features without touching existing code

## Troubleshooting

### State Not Updating
- Check signal connections in `MainWindow.__init__`
- Verify state property names match exactly
- Enable debug logging for state changes

### Configuration Not Persisting
- Ensure config directory exists with write permissions
- Check YAML file syntax if manually edited
- Verify ConfigManager initialization succeeded

### Threading Issues
- All UI updates must go through signals
- Don't access GUI elements from worker threads
- Use StateManager for thread-safe state access