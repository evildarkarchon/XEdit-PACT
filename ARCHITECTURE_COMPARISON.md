# Architecture Comparison: Old vs Refactored

## Overview

This document compares the old XEdit-PACT architecture with the new refactored version, highlighting improvements in state management, separation of concerns, and maintainability.

## Key Improvements

### 1. Centralized State Management

**Old Architecture:**
- State scattered across multiple locations:
  - GUI instance variables (`self.configured_LO`, etc.)
  - Global `info` instance in `PACT_Start.py`
  - YAML configuration files
  - Thread-local variables

**New Architecture:**
- Single `StateManager` class with `AppState` dataclass
- All state in one place with thread-safe access
- Clear state update patterns with Qt signals
- No global variables

### 2. Clear Separation of Concerns

**Old Architecture:**
- `PACT_Interface.py`: Mixed UI and business logic
- `PACT_Start.py`: Mixed configuration, state, and processing logic
- Direct imports and coupling between layers

**New Architecture:**
- `state_manager.py`: Pure state management
- `config_manager.py`: Configuration handling only
- `cleaning_service.py`: Business logic (no Qt dependencies)
- `gui_controller.py`: Mediates between GUI and business logic
- `cleaning_worker.py`: Thread management
- `PACT_Interface_Refactored.py`: Pure UI code

### 3. Dependency Injection

**Old Architecture:**

```python
# Global imports and instances
from Archive.PACT_Start import info, pact_settings, clean_plugins

# Direct use of globals
if matches_condition(proc.name(), info):
```

**New Architecture:**
```python
# Dependencies passed through constructors
def __init__(self, state: StateManager, config: ConfigManager):
    self.state = state
    self.config = config
```

### 4. Simplified Threading

**Old Architecture:**
- Multiple threading models (QThread + threading module)
- Complex lock management (RLock, Lock, QMutex)
- Scattered thread communication

**New Architecture:**
- Single QThread pattern
- Clear signal/slot communication
- State updates through StateManager signals

### 5. Configuration Management

**Old Architecture:**
- Direct YAML file access throughout code
- Multiple update paths
- Validation scattered across modules

**New Architecture:**
- Single `ConfigManager` interface
- Consistent get/set methods
- Centralized validation

## Migration Path

1. **Run Migration Script:**
   ```bash
   python migrate_to_refactored.py
   ```

2. **Update Import Statements:**
   - Replace imports from `PACT_Start` with new modules
   - Remove global variable usage

3. **Test Refactored Version:**
   ```bash
   python PACT_Interface.py
   ```

## Code Examples

### State Update - Old Way:
```python
# Multiple places to update
self.configured_LO = True  # GUI state
info.LOAD_ORDER_PATH = path  # Global state
yaml_settings_write(CONFIG_FILE, path, "Load_Order.File")  # File state
```

### State Update - New Way:
```python
# Single update through StateManager
self.state.update_configuration_paths(load_order_path=path)
# Automatically emits signals for UI updates
```

### Thread Communication - Old Way:
```python
# Complex progress tracking
with self._counter_lock:
    self._plugins_cleaned += 1
progress_emitter.update_progress.emit(self._plugins_cleaned, total)
```

### Thread Communication - New Way:
```python
# Simple result reporting
self.state.add_result(plugin, "cleaned", "Success")
# Automatically updates progress and emits signals
```

## Benefits Summary

1. **Reduced Complexity:** Single source of truth for state
2. **Better Testability:** No global dependencies
3. **Easier Maintenance:** Clear module boundaries
4. **Fewer Bugs:** Eliminated state synchronization issues
5. **Better Performance:** Reduced redundant updates
6. **Improved Debugging:** Clear state flow and updates

## Gradual Migration Strategy

If you prefer to migrate gradually:

1. **Phase 1:** Add new modules alongside existing code
2. **Phase 2:** Update one feature at a time to use new architecture
3. **Phase 3:** Remove old code once all features migrated
4. **Phase 4:** Delete legacy modules

The refactored architecture is designed to coexist with the old code during migration.