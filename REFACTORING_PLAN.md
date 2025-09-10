# AutoQACLib Module Reorganization Plan

## Overview
This document outlines the plan to reorganize AutoQACLib modules to comply with:
- 500-line soft limit per file
- 550-line hard limit per file  
- One class per file rule (with exceptions for related classes)

## Current State

| File | Lines | Classes | Status |
|------|-------|---------|--------|
| utils.py | 767 | YAMLLockTimeoutError, YamlManager | **EXCEEDS HARD LIMIT** |
| gui_controller.py | 665 | GuiController | **EXCEEDS HARD LIMIT** |
| cleaning_service.py | 448 | CleaningService | OK |
| state_manager.py | 324 | AppState, StateManager | OK (related classes) |
| config_manager.py | 251 | ConfigManager | OK |
| cleaning_worker.py | 180 | CleaningWorker | OK |
| logging_config.py | 152 | - (functions only) | OK |

## Proposed Module Structure

### 1. Split utils.py → 3 modules

#### yaml_manager.py (~224 lines)
**Move from utils.py lines 18-224:**
- `YAMLLockTimeoutError` exception (lines 18-19)
- Module-level variables:
  - `_yaml_mutexes` (line 22)
  - `_yaml_manager` (line 227)
- `YamlManager` class (lines 38-224)
  - All methods intact: `__init__`, `_get_file_mutex`, `get_value`, `set_value`, `_parse_key_path`, `_load_yaml`, `_save_yaml`

#### process_utils.py (~300 lines)
**Move from utils.py lines 23-26, 447-767:**
- Module-level variables:
  - `_subprocess_semaphore` (line 23)
  - `_active_subprocesses` (line 24)
  - `_max_concurrent_subprocesses` (line 25)
- Functions:
  - `set_max_concurrent_subprocesses()` (lines 447-465)
  - `get_active_subprocess_count()` (lines 468-473)
  - `_subprocess_resource_manager()` (lines 476-492)
  - `safe_popen()` (lines 495-548)
  - `check_process()` (lines 270-304)
  - `run_process()` (lines 389-444)
  - `run_process_with_realtime_output()` (lines 551-767)

#### game_detection.py (~200 lines)
**Move from utils.py lines 230-267, 307-386, 770-end:**
- Helper functions:
  - `yaml_settings()` (lines 230-242)
  - `yaml_settings_write()` (lines 245-267)
- Game detection:
  - `detect_game_from_load_order()` (lines 307-345)
  - `detect_xedit_game()` (lines 348-386)
- Monitoring:
  - `monitor_log_file()` (lines 770-end if present)

### 2. Split gui_controller.py → 3 modules

#### gui_controller.py (~400 lines)
**Keep in gui_controller.py:**
- Lines 1-27: Imports and constants
- Lines 27-62: GuiController class definition and `__init__`
- Lines 64-86: `_load_configuration()`
- Lines 431-490: `start_cleaning()`
- Lines 492-506: `stop_cleaning()`
- Lines 508-573: `cleanup()`
- Lines 575-612: `_defer_config_save()`, `_process_pending_config_saves()`
- Lines 614-626: `_on_plugin_completed()`, `_on_cleaning_finished()`
- Lines 628-644: `refresh_configuration()`
- Lines 646-664: `get_state_summary()`

#### configuration_dialogs.py (~200 lines)
**Move from gui_controller.py lines 88-297:**
- Import GuiController type for type hints
- Move as methods of a new ConfigurationDialogs class:
  - `configure_load_order()` (lines 88-134)
  - `configure_mo2()` (lines 136-183)
  - `configure_xedit()` (lines 185-259)
  - `toggle_mo2_mode()` (lines 261-281)
  - `toggle_partial_forms()` (lines 283-297)

#### plugin_validator.py (~150 lines)
**Move from gui_controller.py lines 19-21, 299-429:**
- Constants:
  - `PLUGIN_EXTENSIONS` (line 19)
  - `PREFIX_CHARS` (line 20)
  - `SEPARATOR_CHARS` (line 21)
- Create PluginValidator class with methods:
  - `get_plugins_to_clean()` (lines 299-368)
  - `_validate_plugin_line()` (lines 370-429)

### 3. Files Remaining As-Is
- **state_manager.py** - Contains related AppState and StateManager classes
- **config_manager.py** - Single ConfigManager class
- **cleaning_service.py** - Single CleaningService class  
- **cleaning_worker.py** - Single CleaningWorker class
- **logging_config.py** - Logging configuration functions

## Implementation Steps

1. **Create new module files:**
   - `yaml_manager.py`
   - `process_utils.py`
   - `game_detection.py`
   - `configuration_dialogs.py`
   - `plugin_validator.py`

2. **Move code sections as specified above**
   - Preserve all existing logic
   - Maintain thread safety mechanisms
   - Keep all imports needed for each module

3. **Update imports across codebase:**
   - Update all files importing from `utils`
   - Update gui_controller internal imports
   - Update test files

4. **Verify functionality:**
   - Run all tests
   - Check type hints with mypy
   - Verify no circular imports

## Benefits

1. **Compliance:** All files under 550-line hard limit
2. **Maintainability:** Clear separation of concerns
3. **Testability:** Smaller, focused modules easier to test
4. **Readability:** Related functionality grouped logically
5. **Minimal Risk:** Mostly moving code, no logic changes

## Import Changes Required

### Files importing from utils.py:
- `AutoQAC_Interface.py`
- `cleaning_service.py`
- `cleaning_worker.py`
- `config_manager.py`
- `gui_controller.py`
- Test files

### Example import changes:
```python
# Before
from AutoQACLib.utils import yaml_settings, run_process, detect_game_from_load_order

# After  
from AutoQACLib.yaml_manager import YamlManager
from AutoQACLib.process_utils import run_process
from AutoQACLib.game_detection import detect_game_from_load_order, yaml_settings
```

## Notes

- The `yaml_settings()` and `yaml_settings_write()` functions remain in `game_detection.py` for backward compatibility as they're simple wrappers
- Thread safety mechanisms (QMutex, QReadWriteLock) preserved in all moved code
- All logging statements maintained
- Type hints preserved and updated as needed