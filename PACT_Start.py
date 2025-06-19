from __future__ import annotations

import datetime
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias

import portalocker
import psutil
import requests
import ruamel.yaml
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker

"""AUTHOR NOTES (POET)
- Comments marked as RESERVED in all scripts are intended for future updates or tests, do not edit / move / remove.
- (..., encoding="utf-8", errors="ignore") needs to go with every opened file because unicode errors are a bitch.
"""


from typing import Any

PACT_YAML_PATH = Path("PACT Data") / "PACT Main.yaml"
PACT_IGNORE_PATH = Path("PACT Ignore.yaml")
PACT_JOURNAL_PATH = Path("PACT Journal.log")
class ProgressEmitter(QObject):  # type: ignore
    """
    Thread-safe progress emitter for plugin cleaning process.

    This class is responsible for handling and reporting progress updates, including
    the maximum value, current progress, and plugin-specific messages, as well as
    emitting signals to indicate task completion and visibility updates. It provides
    a structured way to track and communicate the status of a plugin cleaning operation.

    All methods are thread-safe and can be called from any thread.
    """

    # Template used for formatting progress messages for plugins
    PROGRESS_MESSAGE_TEMPLATE = "Cleaning {plugin} %v/%m - %p%"


    # Signal definitions with proper type annotations
    progress = Signal(int)  # Current progress value
    max_value = Signal(int)  # Maximum progress value
    plugin_value = Signal(str)  # Plugin-specific progress details
    done = Signal()  # Signals progress completion
    visible = Signal(bool)  # Controls progress tracking visibility

    def __init__(self) -> None:
        """Initialize the thread-safe ProgressEmitter."""
        super().__init__()
        self._mutex = QMutex()
        self._task_completed = False
        self._is_done = False

    @property
    def task_completed(self) -> bool:
        """Thread-safe getter for task completion status."""
        with QMutexLocker(self._mutex):
            return self._task_completed

    @task_completed.setter
    def task_completed(self, value: bool) -> None:
        """Thread-safe setter for task completion status."""
        with QMutexLocker(self._mutex):
            self._task_completed = value

    @property
    def is_done(self) -> bool:
        """Thread-safe getter for done status."""
        with QMutexLocker(self._mutex):
            return self._is_done

    @is_done.setter
    def is_done(self, value: bool) -> None:
        """Thread-safe setter for done status."""
        with QMutexLocker(self._mutex):
            self._is_done = value

    @staticmethod
    def _initialize_plugin_info() -> int:
        """
        Initialize plugin information and retrieve the maximum plugin count.

        Returns:
            int: The maximum plugin count.
        """
        return init_plugins_info()[1]

    def emit_max_value(self) -> None:
        """
        Thread-safe method to emit the maximum value for progress tracking.

        Calculates the maximum count of data being processed and emits this value
        via the `max_value` signal.
        """
        with QMutexLocker(self._mutex):
            max_count = self._initialize_plugin_info()
            self.max_value.emit(max_count)

    def emit_progress(self, current_count: int) -> None:
        """
        Thread-safe method to emit the current progress value.

        Args:
            current_count: The current progress value.
        """
        with QMutexLocker(self._mutex):
            self.progress.emit(current_count)

    def emit_plugin_info(self, plugin_name: str) -> None:
        """
        Thread-safe method to emit a formatted description about the current plugin process.

        Args:
            plugin_name: The name of the current plugin.
        """
        with QMutexLocker(self._mutex):
            formatted_message = self.PROGRESS_MESSAGE_TEMPLATE.format(plugin=plugin_name)
            self.plugin_value.emit(formatted_message)

    def emit_done(self) -> None:
        """
        Thread-safe method to mark the process as complete.

        Emits the `done` signal and updates the task completion status.
        """
        with QMutexLocker(self._mutex):
            self.done.emit()
            self._task_completed = True
            self._is_done = True

    def emit_visibility(self, is_visible: bool = True) -> None:
        """
        Thread-safe method to emit a signal to set visibility.

        Args:
            is_visible: Whether the progress should be visible. Defaults to True.
        """
        with QMutexLocker(self._mutex):
            self.visible.emit(is_visible)


# =================== PACT TOML FILE ===================


class YamlManager:
    """
    Thread-safe YAML file manager with caching capabilities and file locking.

    This class provides thread-safe access to YAML files with automatic
    file locking to prevent concurrent access issues.
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.RLock()  # Reentrant lock for cache access
        self._file_locks: dict[str, threading.RLock] = {}  # Per-file locks
        self._file_locks_lock = threading.Lock()  # Lock for managing file locks
        self._yaml = ruamel.yaml.YAML()
        self._yaml.indent(offset=2)
        self._yaml.width = 300

    def _get_file_lock(self, yaml_path: str) -> threading.RLock:
        """Get or create a lock for the specified file path."""
        with self._file_locks_lock:
            if yaml_path not in self._file_locks:
                self._file_locks[yaml_path] = threading.RLock()
            return self._file_locks[yaml_path]

    def get_value(self, yaml_path: str, key_path: str | list[str]) -> Any:
        """
        Thread-safe method to retrieve a value from the YAML file at the specified key path.

        Args:
            yaml_path: Path to the YAML file
            key_path: Dot-separated string or list of keys to traverse

        Returns:
            The value at the specified key path or None if not found
        """
        file_lock = self._get_file_lock(yaml_path)
        with file_lock:
            data = self._load_yaml(yaml_path)
            keys = self._parse_key_path(key_path)

            # Traverse the YAML structure
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    if "Path" not in (key_path if isinstance(key_path, str) else ".".join(key_path)):
                        print(f"❌ ERROR (YamlManager) : Trying to grab a None value for : '{key_path}'")
                    return None  # Key not found

            return value

    def set_value(self, yaml_path: str, key_path: str | list[str], new_value: Any) -> None:
        """
        Thread-safe method to set a value in the YAML file at the specified key path.

        Args:
            yaml_path: Path to the YAML file
            key_path: Dot-separated string or list of keys to traverse
            new_value: Value to set at the specified key path
        """
        file_lock = self._get_file_lock(yaml_path)
        with file_lock:
            data = self._load_yaml(yaml_path)
            keys = self._parse_key_path(key_path)

            # Navigate to the parent of the final key
            current = data
            for key in keys[:-1]:
                current = current[key]

            # Set the value at the final key
            current[keys[-1]] = new_value

            # Save changes back to file
            self._save_yaml(yaml_path, data)

    @staticmethod
    def _parse_key_path(key_path: str | list[str]) -> list[str]:
        """Convert a dot-separated string path to list of keys."""
        return key_path.split(".") if isinstance(key_path, str) else key_path

    def _load_yaml(self, yaml_path: str) -> Any:
        """Thread-safe method to load YAML file, using cache if available."""
        with self._cache_lock:
            if yaml_path not in self._cache:
                try:
                    with self._file_lock_context(yaml_path):
                        with Path(yaml_path).open(encoding="utf-8") as yaml_file:
                            self._cache[yaml_path] = self._yaml.load(yaml_file)
                except (FileNotFoundError, PermissionError, ruamel.yaml.YAMLError) as fileerror:
                    print(f"❌ ERROR: Failed to load YAML file '{yaml_path}': {str(fileerror)}")
                    self._cache[yaml_path] = {}

            return self._cache[yaml_path]

    def _file_lock_context(self, yaml_path: str):
        """Context manager for file-level locking using portalocker."""

        class FileLockContext:
            def __init__(self, file_path: str):
                self.file_path = file_path
                self.lock_file = None

            def __enter__(self):
                # Create a lock file for this YAML file
                lock_path = Path(self.file_path).with_suffix(".lock")
                self.lock_file = open(lock_path, "w")
                try:
                    portalocker.lock(self.lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
                except portalocker.LockException:
                    # If we can't get the lock immediately, wait for it
                    portalocker.lock(self.lock_file, portalocker.LOCK_EX)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.lock_file:
                    portalocker.unlock(self.lock_file)
                    self.lock_file.close()
                    # Clean up the lock file
                    try:
                        Path(self.file_path).with_suffix(".lock").unlink(missing_ok=True)
                    except OSError:
                        pass  # Ignore cleanup errors

        return FileLockContext(yaml_path)

    def _save_yaml(self, yaml_path: str, data: Any) -> None:
        """Thread-safe method to save data to YAML file and update cache."""
        try:
            # Use atomic write operation
            temp_path = Path(yaml_path).with_suffix(".tmp")
            with self._file_lock_context(yaml_path):
                with temp_path.open("w", encoding="utf-8") as temp_file:
                    self._yaml.dump(data, temp_file)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())  # Force write to disk

                # Atomic move
                temp_path.replace(Path(yaml_path))

            # Update cache after successful write
            with self._cache_lock:
                self._cache[yaml_path] = data
        except (FileNotFoundError, PermissionError) as fe:
            print(f"❌ ERROR: Failed to save YAML file '{yaml_path}': {str(fe)}")
            # Clean up temp file if it exists
            try:
                Path(yaml_path).with_suffix(".tmp").unlink(missing_ok=True)
            except OSError:
                pass


# Create a thread-safe singleton instance
yaml_manager = YamlManager()


def yaml_settings(yaml_path: str | Path, key_path: str | list[str], new_value: Any = None) -> Any:
    """
    Access or modify values in a YAML file. This function allows traversing the YAML structure
    using a dot-separated key path or a list of keys.

    Args:
        yaml_path: The file path to the YAML file to be accessed or modified
        key_path: Dot-separated string or list of strings representing the path to the key
        new_value: Optional, the new value to set at the specified key path

    Returns:
        The value at the specified key path in the YAML file, or None if not found
    """
    if new_value is not None:
        yaml_manager.set_value(yaml_path, key_path, new_value)

    return yaml_manager.get_value(yaml_path, key_path)


def pact_settings(setting: str | None = None) -> str | bool | int | list[str] | None:
    """
    Retrieves or initializes the "PACT Settings.yaml" configuration file.

    Args:
        setting: The specific configuration key to retrieve, or None to just initialize

    Returns:
        The value associated with the provided key, or None
    """
    settings_path = "PACT Settings.yaml"

    # Initialize settings file if it doesn't exist
    if not Path(settings_path).exists():
        default_settings = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.default_settings")
        if default_settings is not None:
            with Path(settings_path).open("w", encoding="utf-8") as settings_file:
                settings_file.write(default_settings)
        else:
            print("❌ ERROR: Default settings could not be loaded.")

    # Return requested setting or None
    if setting:
        result = yaml_settings(settings_path, f"PACT_Settings.{setting}")
        if result is None and "Path" not in setting:
            print(f"❌ ERROR (pact_settings)! Trying to grab a None value for: '{setting}'")
        return result

    return None


@dataclass
class Info:
    """
    Thread-safe configuration and data management for various applications and plugins.

    The `Info` class manages paths, settings, and processing details related to Mod Organizer 2 (MO2),
    xEdit, and various plugin lists for Bethesda games like Fallout and Skyrim. It also integrates with
    external settings defined in YAML files for customizable behavior. The class is designed to provide
    organization and processing support for modding tools and their corresponding lists and logs.

    All methods and property access are protected by locks to ensure thread safety.

    Attributes:
        MO2_EXE (str | Path): Path or name of the Mod Organizer 2 executable.
        MO2_PATH (str | Path): Directory path of Mod Organizer 2.
        XEDIT_EXE (str | Path): Path or name of the xEdit executable.
        XEDIT_PATH (str | Path): Directory path of xEdit.
        LOAD_ORDER_TXT (str | Path): Path to the load order text file.
        LOAD_ORDER_PATH (str | Path): Directory path for the load order file.
        Journal_Expiration (int): Default expiration time for journal records, in days.
        Cleaning_Timeout (int): Timeout value for the cleaning process, in seconds.
        MO2Mode (bool): Flag indicating whether Mod Organizer 2 mode is enabled.
        xedit_list_fallout3 (list[str]): xEdit plugin list for Fallout 3.
        lower_fo3 (set[str]): Lowercase set of Fallout 3 xEdit plugin names.
        xedit_list_newvegas (list[str]): xEdit plugin list for Fallout: New Vegas.
        lower_fnv (set[str]): Lowercase set of Fallout: New Vegas xEdit plugin names.
        xedit_list_fallout4 (list[str]): xEdit plugin list for Fallout 4, including Fallout 4 VR.
        lower_fo4 (set[str]): Lowercase set of Fallout 4 xEdit plugin names.
        xedit_list_skyrimse (list[str]): xEdit plugin list for Skyrim Special Edition, including Skyrim VR.
        skyrimvr_list (list[str]): Separate xEdit plugin list for Skyrim VR.
        lower_sse (set[str]): Lowercase set of Skyrim Special Edition xEdit plugin names.
        xedit_list_universal (list[str]): Universal xEdit plugin list.
        xedit_list_specific (list[str]): Concatenated list of xEdit plugins for all specific games.
        lower_specific (set[str]): Lowercase set of specific xEdit plugin names from all games.
        lower_universal (set[str]): Lowercase set of universal xEdit plugin names.
        clean_results_UDR (set[str]): Set of plugins with undetermined references (UDR).
        clean_results_ITM (set[str]): Set of plugins with identical to master (ITM) records.
        clean_results_NVM (set[str]): Set of plugins with deleted navmeshes (NVM).
        clean_results_PARTIAL_FORMS (set[str]): Set of plugins with partial forms.
        clean_failed_list (set[str]): Set of plugins for which cleaning failed.
        plugins_processed (int): Total number of processed plugins.
        plugins_cleaned (int): Total number of cleaned plugins.
        local_skip_list (list[str]): Local skip list for plugins.
        FO3_skip_list (list[str]): Skip list for Fallout 3 plugins.
        FNV_skip_list (list[str]): Skip list for Fallout: New Vegas plugins.
        FO4_skip_list (list[str]): Skip list for Fallout 4 plugins.
        SSE_skip_list (list[str]): Skip list for Skyrim Special Edition plugins.
        VIP_skip_list (list[str]): Combined VIP skip list for priority exceptions.
        XEDIT_LOG_TXT (str): File path for the xEdit log.
        XEDIT_EXC_LOG (str): File path for the xEdit exception log.
    """

    MO2_EXE: str | Path = field(default_factory=Path)
    MO2_PATH: str | Path = field(default_factory=Path)
    XEDIT_EXE: str | Path = field(default_factory=Path)
    XEDIT_PATH: str | Path = field(default_factory=Path)
    LOAD_ORDER_TXT: str | Path = field(default_factory=Path)
    LOAD_ORDER_PATH: str | Path = field(default_factory=Path)
    Journal_Expiration: int = 7
    Cleaning_Timeout: int = 300

    MO2Mode: bool = False
    xedit_list_fallout3: list[str] = field(
        default_factory=lambda: yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.FO3") or []
    )
    xedit_list_newvegas: list[str] = field(
        default_factory=lambda: yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.FNV") or []
    )
    xedit_list_fallout4: list[str] = field(
        default_factory=lambda: yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.FO4") or []
    )
    xedit_list_skyrimse: list[str] = field(
        default_factory=lambda: yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.SSE") or []
    )
    skyrimvr_list: list[str] = field(
        default_factory=lambda: yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.SkyrimVR") or []
    )
    xedit_list_universal: list[str] = field(default_factory=list)
    xedit_list_specific: list[str] = field(default_factory=list)

    # These will be populated in __post_init__
    lower_fo3: set[str] = field(default_factory=set)
    lower_fnv: set[str] = field(default_factory=set)
    lower_fo4: set[str] = field(default_factory=set)
    lower_sse: set[str] = field(default_factory=set)
    lower_specific: set[str] = field(default_factory=set)
    lower_universal: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Initialize thread safety locks
        self._lock = threading.RLock()
        self._counter_lock = threading.Lock()  # Separate lock for counters

        # Initialize data with thread safety
        with self._lock:
            # Load additional lists
            self.xedit_list_universal = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.Universal") or []

            # Extend lists with VR versions
            fo4vr_list = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.XEdit_Lists.FO4VR") or []
            self.xedit_list_fallout4.extend(fo4vr_list)
            self.xedit_list_skyrimse.extend(self.skyrimvr_list)

            # Create combined specific list
            self.xedit_list_specific = (
                self.xedit_list_fallout3
                + self.xedit_list_newvegas
                + self.xedit_list_fallout4
                + self.xedit_list_skyrimse
            )

            # Create lowercase sets for fast lookups
            self.lower_fo3 = {item.lower() for item in self.xedit_list_fallout3}
            self.lower_fnv = {item.lower() for item in self.xedit_list_newvegas}
            self.lower_fo4 = {item.lower() for item in self.xedit_list_fallout4}
            self.lower_sse = {item.lower() for item in self.xedit_list_skyrimse}
            self.lower_specific = {item.lower() for item in self.xedit_list_specific}
            self.lower_universal = {item.lower() for item in self.xedit_list_universal}

            # Load skip lists
            self.FO3_skip_list = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Skip_Lists.FO3") or []
            self.FNV_skip_list = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Skip_Lists.FNV") or []
            self.FO4_skip_list = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Skip_Lists.FO4") or []
            self.SSE_skip_list = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Skip_Lists.SSE") or []
            self.VIP_skip_list = (
                (self.FO3_skip_list or [])
                + (self.FNV_skip_list or [])
                + (self.FO4_skip_list or [])
                + (self.SSE_skip_list or [])
            )

    def increment_processed(self) -> None:
        """Thread-safe increment of processed plugins counter."""
        with self._counter_lock:
            self.plugins_processed += 1

    def decrement_processed(self) -> None:
        """Thread-safe decrement of processed plugins counter."""
        with self._counter_lock:
            self.plugins_processed -= 1

    def increment_cleaned(self) -> None:
        """Thread-safe increment of cleaned plugins counter."""
        with self._counter_lock:
            self.plugins_cleaned += 1

    def add_to_failed_list(self, plugin_name: str) -> None:
        """Thread-safe addition to failed plugins list."""
        with self._lock:
            self.clean_failed_list.add(plugin_name)

    def add_to_skip_list(self, plugin_name: str) -> None:
        """Thread-safe addition to local skip list."""
        with self._lock:
            self.local_skip_list.append(plugin_name)

    def add_to_clean_results(self, plugin_name: str, result_type: str) -> None:
        """Thread-safe addition to cleaning results."""
        with self._lock:
            if result_type == "UDR":
                self.clean_results_UDR.add(plugin_name)
            elif result_type == "ITM":
                self.clean_results_ITM.add(plugin_name)
            elif result_type == "NVM":
                self.clean_results_NVM.add(plugin_name)
            elif result_type == "PARTIAL_FORMS":
                self.clean_results_PARTIAL_FORMS.add(plugin_name)

    clean_results_UDR: set[str] = field(default_factory=set)  # Undisabled References
    clean_results_ITM: set[str] = field(default_factory=set)  # Identical To Master
    clean_results_NVM: set[str] = field(default_factory=set)  # Deleted Navmeshes
    clean_results_PARTIAL_FORMS: set[str] = field(default_factory=set)  # Partial Forms
    clean_failed_list: set[str] = field(default_factory=set)  # Cleaning Failed
    plugins_processed: int = 0
    plugins_cleaned: int = 0

    local_skip_list: list[str] = field(default_factory=list)

    # HARD EXCLUDE PLUGINS PER GAME HERE
    FO3_skip_list: list[str] = field(default_factory=list)

    FNV_skip_list: list[str] = field(default_factory=list)

    FO4_skip_list: list[str] = field(default_factory=list)

    SSE_skip_list: list[str] = field(default_factory=list)

    VIP_skip_list: list[str] = field(default_factory=list)

    XEDIT_LOG_TXT: str = field(default_factory=str)
    XEDIT_EXC_LOG: str = field(default_factory=str)


def normalize_name(input_string: str) -> str:
    """
    Normalizes the provided input string by extracting the file name and converting it
    to lowercase. Useful for ensuring uniformity in file name handling.

    Args:
        input_string: The input string from which the file name is to be extracted
            and converted to lowercase.

    Returns:
        The extracted file name in lowercase format.
    """
    return Path(input_string).name.lower()


def matches_condition(compare_string: str, data: Info) -> bool:
    """
    Checks whether a normalized version of the compare_string matches any of the
    lowercase conditions in the provided data.

    This function ensures that the provided compare_string, once normalized, is
    checked for equality against the pre-defined lowercase specific or universal
    conditions stored in the `data` object.

    Args:
        compare_string: The string to be normalized and checked against the
            conditions in the data object.
        data: An instance of the Info class containing two sets of lowercase
            conditions—`lower_specific` and `lower_universal`.

    Returns:
        bool: True if the normalized string is found in either `lower_specific` or
            `lower_universal`, otherwise False.
    """
    normalized_name = normalize_name(compare_string)
    return normalized_name in data.lower_specific or normalized_name in data.lower_universal


if not PACT_IGNORE_PATH.exists():
    default_ignorefile = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.default_ignorefile")
    if default_ignorefile is not None:
        with PACT_IGNORE_PATH.open("w", encoding="utf-8") as file:
            file.write(default_ignorefile)
    else:
        print("❌ ERROR: Default ignore file could not be loaded.")


def pact_journal_expire() -> None:
    """
    Deletes the journal file if it is older than the configured expiration duration.

    This function checks the modification time of the journal file located in the
    current working directory. If the journal file exists and its age exceeds the
    configured expiration duration in days, the file is deleted.

    Raises:
        FileNotFoundError: If the specified journal file is not found during the operation.

    """
    # Delete journal if older than set amount of days.

    pact_folder = Path.cwd()
    journal_name = "PACT Journal.log"
    journal_path = pact_folder / journal_name
    if journal_path.is_file():
        journal_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(journal_path.stat().st_mtime)
        journal_age_days = journal_age.days
        if journal_age_days > info.Journal_Expiration:
            journal_path.unlink()


# Thread-safe logging with file locking
_log_lock = threading.Lock()


def pact_log_update(log_message: str) -> None:
    """
    Thread-safe method to append a log message to the "PACT Journal.log" file.

    Uses file locking to prevent concurrent write issues.

    Args:
        log_message: The message string to be written into the log file.
    """
    with _log_lock:
        try:
            with PACT_JOURNAL_PATH.open("a", encoding="utf-8", errors="ignore") as LOG_PACT:
                # Use file locking to prevent concurrent writes
                portalocker.lock(LOG_PACT, portalocker.LOCK_EX)
                try:
                    LOG_PACT.write(log_message)
                    LOG_PACT.flush()
                    os.fsync(LOG_PACT.fileno())  # Force write to disk
                finally:
                    portalocker.unlock(LOG_PACT)
        except OSError as oe:
            print(f"Warning: Could not write to log file: {oe}")


def pact_ignore_update(plugin: str, game: str) -> None:
    """
    Adds a plugin to the ignore list for the specified game. The ignore list is managed
    within a YAML configuration file. This function updates the configuration file
    with the provided plugin to ensure it is ignored for the given game.

    Args:
        plugin: The name of the plugin to be added to the ignore list.
        game: The name of the game for which the plugin should be ignored.
    """
    ignore_list = yaml_settings(str(PACT_IGNORE_PATH), f"PACT_Ignore_{game}") or []
    ignore_list.append(plugin)
    yaml_settings(str(PACT_IGNORE_PATH), f"PACT_Ignore_{game}", ignore_list)


# =================== WARNING MESSAGES ==================
# Can change first line to """\ to remove the spacing.

PAUSE_MESSAGE = "Press Enter to continue..."

# =================== UPDATE FUNCTION ===================


# Constants for messages and URLs
GITHUB_API_URL = "https://api.github.com/repos/evildarkarchon/XEdit-PACT/releases/latest"
PACT_VERSION_KEY = "PACT_Data.version"
OUTDATED_WARNING_KEY = "PACT_Data.Warnings.Outdated_PACT"
UPDATE_FAILED_WARNING_KEY = "PACT_Data.Warnings.PACT_Update_Failed"
SEPARATOR = "==============================================================================="


def pact_update_check() -> bool:
    """
    Checks for updates to the Plugin Auto Cleaning Tool (PACT).

    This function checks if a newer version of PACT is available by comparing
    the current version with the latest release on GitHub.

    Returns:
        bool: True if the currently installed PACT version is up-to-date, False otherwise.

    Raises:
        OSError: If there is an operating system-related issue during the request.
        requests.exceptions.RequestException: If there is an issue fetching data from GitHub.
    """
    if not pact_settings("Update Check"):  # type: ignore
        print("\n ❌ NOTICE: UPDATE CHECK IS DISABLED IN PACT INI SETTINGS \n")
        print(SEPARATOR)
        return False

    print("❓ CHECKING FOR ANY NEW PLUGIN AUTO CLEANING TOOL (PACT) UPDATES...")
    print("   (You can disable this check in the EXE or PACT Settings.toml) \n")

    try:
        return _check_version_and_report()
    except (requests.exceptions.RequestException, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        _show_update_check_failed_message()
        return False


def _check_version_and_report() -> bool:
    """Check the version against GitHub and report results."""
    response = requests.get(GITHUB_API_URL)
    latest_version = response.json()["name"]
    current_version = yaml_settings(PACT_YAML_PATH, PACT_VERSION_KEY)

    if latest_version == current_version:
        print("\n✔️ You have the latest version of PACT!")
        return True
    else:
        outdated_warning = yaml_settings(PACT_YAML_PATH, OUTDATED_WARNING_KEY)
        print(outdated_warning)
        print(SEPARATOR)
        return False


def _show_update_check_failed_message() -> None:
    """Display message when update check fails."""
    update_failed_warning = yaml_settings(PACT_YAML_PATH, UPDATE_FAILED_WARNING_KEY)
    print(update_failed_warning)
    print(SEPARATOR)


# =================== TERMINAL OUTPUT START ====================
print(
    f"Hello World! | Plugin Auto Cleaning Tool (PACT) | Version {yaml_settings(str(PACT_YAML_PATH), 'PACT_Data.version')!s} | FO3, FNV, FO4, SSE"
)
print("MAKE SURE TO SET THE CORRECT LOAD ORDER AND XEDIT PATHS BEFORE CLEANING PLUGINS")
print("===============================================================================")

# Create thread-safe global info instance
info = Info()


# Type aliases for better readability
PathLike: TypeAlias = str | Path
InfoObject: TypeAlias = "Info"  # Using string to handle forward reference

# Constants for validation
MIN_CLEANING_TIMEOUT = 30  # seconds
MIN_JOURNAL_EXPIRATION = 1  # days
ERROR_MESSAGES = {
    "invalid_cleaning_timeout": """❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Cleaning Timeout to a valid positive number.""",
    "small_cleaning_timeout": f"""❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS TOO SMALL.)
Cleaning Timeout must be set to at least {MIN_CLEANING_TIMEOUT} seconds or more.""",
    "invalid_journal_expiration": """❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Journal Expiration to a valid positive number.""",
    "small_journal_expiration": f"""❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS TOO SMALL.)
Journal Expiration must be set to at least {MIN_JOURNAL_EXPIRATION} day or more.""",
}


def update_path_and_executable(
    data: InfoObject, path_attr: str, exe_attr: str, path_value: PathLike | None, executable_finder=None
) -> None:
    """
    Generic function to update path and executable attributes in the data object.

    Args:
        data: The data object to update
        path_attr: Name of the path attribute to update
        exe_attr: Name of the executable attribute to update
        path_value: The new path value
        executable_finder: Optional function to find an executable in a directory
    """
    if path_value is None:
        setattr(data, path_attr, "")
        setattr(data, exe_attr, "")
        return

    path_value = Path(path_value)
    setattr(data, path_attr, path_value)

    if ".exe" in str(path_value):
        setattr(data, exe_attr, path_value.name)
    elif path_value.exists() and executable_finder:
        executable_path = executable_finder(data, path_value)
        if executable_path:
            setattr(data, path_attr, executable_path)
            setattr(data, exe_attr, executable_path.name)


def find_xedit_executable(data: InfoObject, directory: Path) -> Path | None:
    """Find an appropriate xEdit executable in the given directory."""
    for xedit_file in directory.iterdir():
        if xedit_file.suffix == ".exe" and matches_condition(xedit_file.name, data):
            return xedit_file
    return None


def find_mo2_executable(directory: Path) -> Path | None:
    """Find an appropriate MO2 executable in the given directory."""
    for mo2_file in directory.iterdir():
        if mo2_file.suffix == ".exe" and ("mod" in mo2_file.name.lower() or "mo2" in mo2_file.name.lower()):
            return mo2_file
    return None


def update_load_order_path(data: InfoObject, load_order_path: PathLike | None) -> None:
    """
    Updates the load order path for the given data object.

    Args:
        data: The data object with attributes to update.
        load_order_path: The new path to the load order file.
    """
    data.LOAD_ORDER_PATH = load_order_path
    data.LOAD_ORDER_TXT = Path(load_order_path).name if load_order_path is not None else ""


def update_xedit_path(data: InfoObject, xedit: PathLike | None) -> None:
    """
    Updates the xEdit path and executable attributes in the data object.

    Args:
        data: The data object to update.
        xedit: The path to the xEdit executable or directory.
    """
    update_path_and_executable(data, "XEDIT_PATH", "XEDIT_EXE", xedit, find_xedit_executable)


def update_mo2_path(data: InfoObject, mo2_path: PathLike | None) -> None:
    """
    Updates the MO2 path and executable attributes in the data object.

    Args:
        data: The data object to update.
        mo2_path: The path to the MO2 executable or directory.
    """
    update_path_and_executable(data, "MO2_PATH", "MO2_EXE", mo2_path, find_mo2_executable)


def validate_positive_integer(value: Any, min_value: int, error_invalid: str, error_too_small: str) -> None:
    """Validate that a value is a positive integer and not smaller than min_value."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(error_invalid)
    if value < min_value:
        raise ValueError(error_too_small)


def pact_update_settings(data: InfoObject) -> None:
    """
    Updates the provided Info data object with settings fetched from PACT configuration.

    Args:
        data: The Info instance to update with settings values.

    Raises:
        ValueError: If timeout or expiration values are invalid.
    """
    # Update paths
    load_order_path = pact_settings("LoadOrder TXT")
    if isinstance(load_order_path, (str, Path)):
        update_load_order_path(data, load_order_path)

    xedit_exe_setting = pact_settings("XEDIT EXE")
    if isinstance(xedit_exe_setting, (str, Path)):
        update_xedit_path(data, xedit_exe_setting)

    mo2_exe_setting = pact_settings("MO2 EXE")
    if isinstance(mo2_exe_setting, (str, Path)):
        update_mo2_path(data, mo2_exe_setting)

    # Update timeout and expiration values
    cleaning_timeout = pact_settings("Cleaning Timeout")
    if cleaning_timeout is not None and isinstance(cleaning_timeout, (str, int)):
        data.Cleaning_Timeout = int(cleaning_timeout)

    journal_expiration = pact_settings("Journal Expiration")
    if (
        journal_expiration is not None
        and isinstance(journal_expiration, (str, int))
        and not isinstance(journal_expiration, list)
    ):
        data.Journal_Expiration = int(journal_expiration)

    # Validate values
    validate_positive_integer(
        data.Cleaning_Timeout,
        MIN_CLEANING_TIMEOUT,
        ERROR_MESSAGES["invalid_cleaning_timeout"],
        ERROR_MESSAGES["small_cleaning_timeout"],
    )

    validate_positive_integer(
        data.Journal_Expiration,
        MIN_JOURNAL_EXPIRATION,
        ERROR_MESSAGES["invalid_journal_expiration"],
        ERROR_MESSAGES["small_journal_expiration"],
    )


# The original function call and post-processing logic
pact_update_settings(info)
try:
    if ".exe" in str(info.XEDIT_PATH) and info.XEDIT_EXE in info.xedit_list_specific:
        xedit_path = Path(info.XEDIT_PATH)
        info.XEDIT_LOG_TXT = str(xedit_path.with_name(xedit_path.stem.upper() + "_log.txt"))
        info.XEDIT_EXC_LOG = str(xedit_path.with_name(xedit_path.stem.upper() + "Exception.log"))
    elif info.XEDIT_PATH and ".exe" not in str(info.XEDIT_PATH):
        # During import, just log the issue without blocking
        error_msg = yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Errors.Invalid_XEDIT_File")
        if error_msg:
            print(f"⚠️  Configuration warning: {error_msg}")
        else:
            print("⚠️  Configuration warning: Invalid XEDIT file path")
        # Don't raise an error during import - let the GUI handle this
except (AttributeError, ValueError, KeyError, TypeError, FileNotFoundError) as e:
    print(f"⚠️  Configuration warning during import: {e}")
    # Continue with import, let the application handle configuration issues later


def check_process_mo2(progress_emitter: ProgressEmitter, settings: InfoObject) -> bool:
    """
    Checks if Mod Organizer 2 (MO2) is running and prevents the process from continuing if
    MO2 is detected. The function first updates the settings using the provided settings
    object. It then checks if the MO2 path exists and searches for any active MO2 processes.
    If any MO2 processes are found, an error message is displayed, a progress completion
    event is emitted, and the function returns True. Otherwise, it returns False.

    Args:
        progress_emitter: An instance of ProgressEmitter used to signal progress updates or
            completion events.
        settings: An InfoObject instance containing configuration and file path information
            including the path to MO2 and its executable name.

    Returns:
        bool: True if MO2 processes are found and an error is reported; False otherwise.
    """
    mo2_error_message = """❌ ERROR : CANNOT START PACT WHILE MOD ORGANIZER 2 IS ALREADY RUNNING!
PLEASE CLOSE MO2 AND RUN PACT AGAIN! (DO NOT RUN PACT THROUGH MO2)"""

    pact_update_settings(settings)

    # Only check for MO2 processes if the MO2 path exists
    if Path(settings.MO2_PATH).exists():
        mo2_exe_name = str(settings.MO2_EXE).lower()

        # Find all processes with a name containing the MO2 executable name
        mo2_processes = [
            proc for proc in psutil.process_iter(attrs=["pid", "name"]) if mo2_exe_name in proc.name().lower()
        ]

        # If any MO2 processes are found, report the error and return True
        if mo2_processes:
            print(mo2_error_message)
            progress_emitter.emit_done()
            return True

    return False


# Clear xedit log files to check them for each plugin separately.
def clear_xedit_logs() -> None:
    """
    Deletes XEdit log files if they exist. This function attempts to remove
    XEdit log files specified by the file paths `info.XEDIT_LOG_TXT` and
    `info.XEDIT_EXC_LOG`. If the files are not present, no action is taken. If any
    errors occur during the deletion process, the user is notified, and an
    exception is raised.

    Raises:
        PermissionError: Raised when the process lacks the permission to delete the log files.
        OSError: Raised when an operating system-related error occurs during file deletion.

    Returns:
        None
    """
    try:
        if Path(info.XEDIT_LOG_TXT).exists():
            Path(info.XEDIT_LOG_TXT).unlink()
        if Path(info.XEDIT_EXC_LOG).exists():
            Path(info.XEDIT_EXC_LOG).unlink()
    except (PermissionError, OSError):
        print("❌ ERROR : CANNOT CLEAR XEDIT LOGS. Try running PACT in Admin Mode.")
        print("   If problems continue, please report this to the PACT Nexus page.")
        raise


# Make sure right XEDIT is running for the right game.
def check_settings_integrity() -> None:
    """
    Validates the integrity of required settings, configuration files, and execution paths
    necessary for running the application. This function ensures that file paths exist and the
    settings specified in the configuration files align with the expected environment.

    Additionally, it checks the compatibility of executable files with associated data content.
    Validation ensures the environment is set up correctly before further operations proceed.

    Raises:
        ValueError: If any required path or setting is invalid or missing.

    """
    pact_update_settings(info)
    if Path(info.LOAD_ORDER_PATH).exists() and Path(info.XEDIT_PATH).exists():
        print("✔️ REQUIRED FILE PATHS FOUND! CHECKING IF INI SETTINGS ARE CORRECT...")
    else:
        print(yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Warnings.Invalid_INI_Path"))
        input(PAUSE_MESSAGE)
        raise ValueError

    if Path(info.MO2_PATH).exists():
        info.MO2Mode = True
    else:
        info.MO2Mode = False

    valid_xedit_executables = {
        "Fallout3.esm": info.lower_fo3,
        "FalloutNV.esm": info.lower_fnv,
        "Fallout4.esm": info.lower_fo4,
        "Skyrim.esm": info.lower_sse,
    }

    if str(info.XEDIT_EXE).lower() not in info.lower_universal:
        with Path(info.LOAD_ORDER_PATH).open(encoding="utf-8", errors="ignore") as LO_Check:
            lo_plugins = LO_Check.read()
            if not any(
                game in lo_plugins and str(info.XEDIT_EXE).lower() in executables
                for game, executables in valid_xedit_executables.items()
            ):
                print(yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Warnings.Invalid_INI_Setup"))
                input(PAUSE_MESSAGE)
                raise ValueError
    elif "loadorder" not in str(info.LOAD_ORDER_PATH) and str(info.XEDIT_EXE).lower() in info.lower_universal:
        print(yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Errors.Invalid_LO_File"))
        input(PAUSE_MESSAGE)
        raise ValueError


def update_log_paths(data: Info, game_mode: str | None = None) -> None:
    """
    Updates logging paths for a given game mode or defaults based on the original path.

    This function modifies the provided `data` object by updating its logging paths based
    on the given game mode. If a game mode is supplied, the logging paths are updated to
    include the game mode in their filenames. If no game mode is provided, the original
    path's stem is used to update the logging paths.

    Args:
        data: An object containing attributes `XEDIT_PATH`, `XEDIT_LOG_TXT`, and
            `XEDIT_EXC_LOG`. The `XEDIT_PATH` is used to determine the new paths,
            and the other two attributes are updated as a result.
        game_mode: An optional string specifying the game mode. Determines how the
            logging filenames are generated. If None, the original path's stem is
            used.
    """
    path = Path(data.XEDIT_PATH)
    if game_mode:
        data.XEDIT_LOG_TXT = str(path.with_name(f"{game_mode.upper()}Edit_log.txt"))
        data.XEDIT_EXC_LOG = str(path.with_name(f"{game_mode.upper()}EditException.log"))
    else:
        data.XEDIT_LOG_TXT = str(path.with_name(f"{path.stem.upper()}_log.txt"))
        data.XEDIT_EXC_LOG = str(path.with_name(f"{path.stem.upper()}Exception.log"))

    # Additional helper functions


def create_xedit_command(data: Info, plugin_name: str, universal: bool, game_mode: str | None = None) -> str | None:
    """
    Constructs and returns a command string to execute xEdit with specified parameters. This function
    handles different execution modes (MO2 Mode or direct execution) and adjusts the command string
    accordingly. It also supports the configuration of game modes and applies specific settings based
    on enabled features like Partial Forms. If the xEdit executable path is not specified, the function
    returns None.

    Args:
        data (Info): The information object containing necessary configurations and execution mode details, including
            paths to executables and mode flags.
        plugin_name (str): The name of the plugin to be processed by xEdit. This name will be escaped based on the
            execution mode.
        universal (bool): Flag indicating whether game mode should be added to the command string. If false,
            `game_mode` will be ignored.
        game_mode (str | None): The game mode to include in the command, represented as a string. This is
            optional and only included if `universal` is True.

    Returns:
        str | None: The constructed command string ready for execution in the appropriate mode. Returns
        None if the xEdit executable is not specified in `data`.

    """
    # Create base arguments that are common across all configurations
    base_args = "-QAC -autoexit -autoload"

    # Add game mode if needed
    game_mode_arg = f"-{game_mode} " if universal and game_mode else ""

    # Handle plugin name escaping based on execution mode
    plugin_arg = f'\\"{plugin_name}\\"' if data.MO2Mode else f'"{plugin_name}"'

    # Construct command based on execution mode
    if data.MO2Mode:
        commandline = f'"{data.MO2_PATH}" run "{data.XEDIT_PATH}" -a "{game_mode_arg}{base_args} {plugin_arg}"'
    elif data.XEDIT_PATH:
        commandline = f'"{data.XEDIT_PATH}" -a {game_mode_arg}{base_args} {plugin_arg}'
    else:
        print("Invalid xedit executable specified")
        return None

    # Apply partial forms settings if enabled
    if pact_settings("Partial Forms"):
        commandline = commandline.replace(base_args, "-iknowwhatimdoing -QAC -allowmakepartial -autoexit -autoload")

    return commandline


def get_game_mode(data: Info) -> str:
    """
    Determines the game mode by reading and analyzing the load order file.

    The function checks the content of the load order file specified in the
    data object to determine the game mode based on the presence of specific
    keywords representing different game types. The function returns the
    corresponding game mode string if a match is found.

    Args:
        data (Info): An instance containing the LOAD_ORDER_PATH attribute,
            which specifies the path to the load order file.

    Returns:
        str: A string representing the game mode ('sse' for Skyrim Special
            Edition, 'fo3' for Fallout 3, 'fnv' for Fallout New Vegas,
            or 'fo4' for Fallout 4).

    Raises:
        FileNotFoundError: If the load order file is not found at the
            specified path.
        Exception: If an error occurs while reading the load order file.
        ValueError: If no game mode can be determined from the file content.
    """
    # Read the load order file line by line to determine the game mode
    try:
        with Path(data.LOAD_ORDER_PATH).open(encoding="utf-8", errors="ignore") as LO_Check:
            for line in LO_Check:
                match line.strip():
                    case _ if "Skyrim.esm" in line:
                        return "sse"
                    case _ if "Fallout3.esm" in line:
                        return "fo3"
                    case _ if "FalloutNV.esm" in line:
                        return "fnv"
                    case _ if "Fallout4.esm" in line:
                        return "fo4"
    except FileNotFoundError:
        print(f"Load order file not found: {data.LOAD_ORDER_PATH}")
        raise
    except (UnicodeDecodeError, OSError, PermissionError) as ude:
        print(f"Error reading load order file: {data.LOAD_ORDER_PATH}, error: {ude!s}")
        raise
    else:
        raise ValueError("❌ ERROR: UNABLE TO DETERMINE GAME MODE!")


# Constants
CPU_USAGE_THRESHOLD = 1
PROCESS_TERMINAL_STATES = {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}
EXCEPTION_PHRASES = ["which can not be found", "which it does not have"]
PAUSE_MESSAGE = "Press Enter to continue..."
ERROR_START_MESSAGE = """❓ ERROR : UNABLE TO START THE CLEANING PROCESS! WRONG INI SETTINGS OR FILE PATHS?
    If you're seeing this, make sure that your load order / xedit paths are correct.
    If problems continue, try a different load order file or xedit executable.
    If nothing works, please report this error to the PACT Nexus page."""


def check_cpu_usage(proc: psutil.Process) -> bool | None:
    """
    Checks if a given process is currently running and whether its CPU usage is
    below a defined threshold or its status is in a specific terminal state.

    This function queries the process for its running status and CPU usage over
    a defined interval. It also compares the status of the process with a set
    of terminal states. If certain exceptions occur during the process checks,
    it will gracefully handle them and return False.

    Args:
        proc: A `psutil.Process` instance representing the process to be analyzed.

    Returns:
        bool | None: Returns True if the process is running, and its CPU usage is
        below the defined threshold or process status is among terminal states.
        Returns False if the process does not meet these criteria or if an exception
        related to process access or existence occurs.
    """
    try:
        return proc.is_running() and (
            proc.cpu_percent(interval=5) < CPU_USAGE_THRESHOLD or proc.status() in PROCESS_TERMINAL_STATES
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def check_process_timeout(proc: psutil.Process, data: "Info") -> bool:
    """
    Checks if a process has exceeded the allocated timeout duration.

    This function calculates the time elapsed since the process was created
    and compares it to a specified timeout value.

    Args:
        proc: The process object of type psutil.Process that needs to be
            checked.
        data: An instance of `Info` containing the timeout configuration as
            `Cleaning_Timeout`.

    Returns:
        bool: True if the process has exceeded the timeout, False otherwise.
    """
    create_time = proc.create_time()
    return (time.time() - create_time) > data.Cleaning_Timeout


def check_process_exceptions(data: "Info") -> bool:
    """
    Checks for exceptions in the provided log file path specified by the 'Info' object. It reads
    the log file using PowerShell, decodes its contents, and searches for predefined exception
    phrases. Returns a boolean indicating if any of the specified exception phrases are found.

    Args:
        data (Info): An object containing the path to the exception log file.

    Returns:
        bool: True if any of the specified exception phrases are found in the log file,
        False otherwise.
    """
    log_path = Path(data.XEDIT_EXC_LOG)
    if not log_path.exists():
        return False

    xedit_exc_out = subprocess.check_output(["powershell", "-command", f"Get-Content {data.XEDIT_EXC_LOG}"])
    exception_check = xedit_exc_out.decode()

    return any(phrase in exception_check for phrase in EXCEPTION_PHRASES)


def handle_error(
    proc: psutil.Process, plugin_name: str, data: "Info", error_message: str, add_ignore: bool = True
) -> None:
    """
    Handles errors during plugin processing by terminating the associated process, updating
    log and ignore list, and adjusting internal plugin tracking properties.

    Args:
        proc (psutil.Process): The process associated with the plugin being handled.
        plugin_name (str): The name of the plugin that caused the error.
        data (Info): An object containing tracking and state information related to
            the plugin processing.
        error_message (str): The error message to be logged and displayed.
        add_ignore (bool, optional): Whether to add the plugin to the ignore list.
            Defaults to True.
    """
    try:
        proc.kill()
    except (
        PermissionError,
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
    ):
        pass
    finally:
        time.sleep(1)
        if not pact_settings("Debug Mode"):
            clear_xedit_logs()

        data.decrement_processed()
        data.add_to_failed_list(plugin_name)
        print(error_message)

        if add_ignore:
            game_mode = get_game_mode(data).upper()
            pact_ignore_update(plugin_name, game_mode)


def create_bat_command(data: "Info", plugin_name: str) -> str | None:
    """
    Creates a batch command for executing xEdit based on provided data and plugin name.

    This function constructs and returns a properly formatted batch command string for
    running xEdit, depending on the type of xEdit executable and the validation of
    the load order file. It handles two scenarios:
    1. The use of a specific xEdit executable.
    2. The use of a universal xEdit executable with a valid load order file.

    If the specific xEdit executable is found in the provided data, the function updates
    the log paths and creates a corresponding command. Alternatively, if a universal xEdit
    executable is used, the function retrieves the game mode, ensures its validity,
    updates additional log paths, and constructs an appropriate batch command.

    In case of invalid data or errors, appropriate messages are displayed to the user
    before an exception is raised.

    Args:
        data (Info): The input data containing xEdit executables, paths, and other related
            configurations.
        plugin_name (str): The name of the plugin to be processed by xEdit.

    Returns:
        str | None: A string containing the batch command to run xEdit or None if no
        valid command could be created.

    Raises:
        ValueError: If the load order file provided in the data is invalid and cannot be
        processed.
        RuntimeError: If the function fails to construct a valid batch command for executing
        xEdit.
    """
    xedit_exe_lower = str(data.XEDIT_EXE).lower()

    # Check for specific xEdit executable
    if xedit_exe_lower in data.lower_specific:
        update_log_paths(data)
        bat_command = create_xedit_command(data, plugin_name, False)
        if bat_command:
            return bat_command

    # Check for universal xEdit with valid load order
    load_order_path = str(data.LOAD_ORDER_PATH).lower()
    if "loadorder" in load_order_path and xedit_exe_lower in data.lower_universal:
        game_mode = get_game_mode(data)
        if game_mode is None:
            print(yaml_settings(str(PACT_YAML_PATH), "PACT_Data.Errors.Invalid_LO_File"))
            input(PAUSE_MESSAGE)
            raise ValueError("Invalid load order file")

        update_log_paths(data, game_mode)
        bat_command = create_xedit_command(data, plugin_name, True, game_mode)
        if bat_command:
            return bat_command

    # If we reach here, something went wrong
    print(ERROR_START_MESSAGE)
    input(PAUSE_MESSAGE)
    raise RuntimeError("Unable to start the cleaning process")


def run_auto_cleaning(plugin_name: str) -> None:
    """
    Runs an automatic cleaning process for a given plugin.

    This function orchestrates the cleaning process for a plugin by creating and
    executing a batch command while monitoring the process in a separate thread.
    Logs are cleared if the "Debug Mode" setting is not enabled. The cleaning
    process also updates the count of processed plugins upon completion.

    Args:
        plugin_name: The name of the plugin to be cleaned.
    """
    # Create command to run in subprocess
    bat_command = create_bat_command(info, plugin_name)

    # Clear logs and start subprocess
    if not pact_settings("Debug Mode"):
        clear_xedit_logs()
    print(f"\nCURRENTLY CLEANING : {plugin_name}")
    if bat_command is None:
        raise ValueError("Invalid command for subprocess")
    bat_process = subprocess.Popen(bat_command, shell=True)

    # Create a separate thread for monitoring the process
    monitor_thread = threading.Thread(target=monitor_process, args=(bat_process, plugin_name))
    monitor_thread.start()

    # Wait for the cleaning process to finish
    bat_process.wait()

    # Thread-safe increment of processed plugins count
    info.increment_processed()


def monitor_process(proc: subprocess.Popen, plugin_name: str) -> None:
    """
    Monitors a subprocess for specific errors and manages its lifecycle. This function regularly checks the
    given subprocess for CPU usage, timeouts, and exceptions. On detecting specific conditions, it handles
    the errors by logging respective messages, terminating associated processes, and updating the log.
    The function ensures proper error handling for a subprocess while interacting with plugins.

    Args:
        proc: The subprocess.Popen instance representing the monitored process.
        plugin_name: The name of the plugin tied to the monitored subprocess.
    """
    error_messages = {
        "disabled_or_missing": "❌ ERROR : PLUGIN IS DISABLED OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...",
        "timeout": "❌ ERROR : XEDIT TIMED OUT (CLEANING PROCESS TOOK TOO LONG)! KILLING XEDIT...",
        "empty_or_missing": "❌ ERROR : PLUGIN IS EMPTY OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...",
    }

    def handle_process_error(xedit_process: psutil.Process, error_type: str, add_ignore: bool = True) -> None:
        """Handles xedit_process errors by logging and terminating."""
        handle_error(xedit_process, plugin_name, info, error_messages[error_type], add_ignore)
        pact_log_update(f"{plugin_name} -> {error_type.replace('_', ' ').capitalize()}")

    def check_errors(xedit_process: psutil.Process) -> bool:
        """Checks for various xedit_process-related errors and handles them."""
        if check_cpu_usage(xedit_process):
            handle_process_error(xedit_process, "disabled_or_missing")
            return True
        if check_process_timeout(xedit_process, info):
            handle_process_error(xedit_process, "timeout", add_ignore=False)
            return True
        if check_process_exceptions(info):
            handle_process_error(xedit_process, "empty_or_missing")
            return True
        return False

    while proc.poll() is None:
        relevant_procs = [
            p
            for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "create_time"])
            if matches_condition(p.name(), info) and p.name().lower() == str(info.XEDIT_EXE).lower()
        ]

        for process in relevant_procs:
            if check_errors(process):
                if proc:
                    proc.kill()
                    proc.wait()
                break  # Exit from the xedit_process loop on error
        time.sleep(3)


# Compile the patterns outside the function
udr_pattern = re.compile(r"Undeleting:\s*(.*)")
itm_pattern = re.compile(r"Removing:\s*(.*)")
nvm_pattern = re.compile(r"Skipping:\s*(.*)")
partial_form_pattern = re.compile(r"Making Partial Form:\s*(.*)")


# Constants
LOG_PATTERNS = {
    udr_pattern: ("Cleaned UDRs", info.clean_results_UDR),
    itm_pattern: ("Cleaned ITMs", info.clean_results_ITM),
    nvm_pattern: ("Found Deleted Navmeshes", info.clean_results_NVM),
    partial_form_pattern: ("Created Partial Forms", info.clean_results_PARTIAL_FORMS),
}


def process_log_line(line: str, plugin_name: str) -> bool:
    """
    Thread-safe processing of log lines with pattern matching.

    This function iterates through a dictionary of compiled regular expression patterns
    and their corresponding messages and result list mappings. If the log line matches
    a pattern, it performs a log update, adds the plugin name to the results list, and
    returns True. If no patterns match, it returns False.

    Args:
        line (str): A single line from the log to be processed.
        plugin_name (str): The name of the plugin associated with the log being processed.

    Returns:
        bool: True if the line matches any log pattern; False otherwise.
    """
    for pattern, (message, results_list) in LOG_PATTERNS.items():
        if pattern.search(line):
            pact_log_update(f"\n{plugin_name} -> {message}")
            # Thread-safe addition to results
            if results_list == info.clean_results_UDR:
                info.add_to_clean_results(plugin_name, "UDR")
            elif results_list == info.clean_results_ITM:
                info.add_to_clean_results(plugin_name, "ITM")
            elif results_list == info.clean_results_NVM:
                info.add_to_clean_results(plugin_name, "NVM")
            elif results_list == info.clean_results_PARTIAL_FORMS:
                info.add_to_clean_results(plugin_name, "PARTIAL_FORMS")
            return True
    return False


def check_cleaning_results(plugin_name: str) -> None:
    """
    Checks the cleaning results of a given plugin by analyzing the xEdit log file.

    This function ensures that xEdit logs are generated by waiting for a brief moment.
    It then verifies whether the log file exists and parses it to determine if cleaning
    has successfully occurred for the given plugin. Depending on the outcome, it updates
    related tracking information, moves plugins to an ignore list if necessary, and clears
    logs in non-debug mode.

    Args:
        plugin_name: The name of the plugin to check for cleaning results.
    """
    time.sleep(1)  # Ensure xEdit logs are generated.
    log_file_path = Path(info.XEDIT_LOG_TXT)
    if log_file_path.exists():
        did_clean = False
        with log_file_path.open(encoding="utf-8", errors="ignore") as log_file:
            for line in log_file:
                if process_log_line(line, plugin_name):
                    did_clean = True

        if did_clean:
            info.increment_cleaned()
        else:
            pact_log_update(f"\n{plugin_name} -> NOTHING TO CLEAN")
            print("NOTHING TO CLEAN! Adding plugin to PACT Ignore file...")
            pact_ignore_update(plugin_name, get_game_mode(info).upper())
            info.add_to_skip_list(plugin_name)

        if not pact_settings("Debug Mode"):
            clear_xedit_logs()


def get_plugin_list(load_order_path: str) -> list[str]:
    """
    Parses a file to extract a list of plugins based on specific formatting rules.

    This function reads a given file, ignores the first line, and processes subsequent lines
    to determine whether they represent plugins. The rules for identifying a plugin depend
    on whether the input file path includes "plugins.txt" in its name. Plugins are either
    extracted by detecting lines with specific markers or by excluding lines with unwanted
    extensions.

    Args:
        load_order_path (str): Path to the file containing plugin load order information.

    Returns:
        list[str]: A list of plugin names extracted from the file.
    """
    with Path(load_order_path).open(encoding="utf-8", errors="ignore") as lo_file:
        next(lo_file)  # Skip the first line
        if "plugins.txt" in load_order_path:
            plugin_list = [line.strip().replace("*", "") for line in lo_file if "*" in line.strip()]
        else:
            plugin_list = [line.strip() for line in lo_file if ".ghost" not in line]
    return plugin_list


def clean_plugin(plugin: str) -> None:
    """
    Performs the cleaning process for the specified plugin.

    This function automates the cleaning of a provided plugin by running an
    auto-cleaning process followed by a check to ensure the cleaning was
    completed successfully.

    Args:
        plugin (str): The name or identifier of the plugin to be cleaned.
    """
    run_auto_cleaning(plugin)
    check_cleaning_results(plugin)


def init_plugins_info() -> tuple[list[str], int, list[str]]:
    """
    Initializes and retrieves information about plugins, including their list, the count of active
    plugins, and a combined skip list of excluded plugins.

    Returns:
        tuple[list[str], int, list[str]]: A tuple containing:
            - A list of all detected plugins.
            - The count of active plugins after excluding skipped plugins.
            - A combined skip list of VIP and local skipped plugins.
    """
    all_skip_list = info.VIP_skip_list + info.local_skip_list
    plugin_list = get_plugin_list(str(info.LOAD_ORDER_PATH))
    count_plugins = len(set(plugin_list) - set(all_skip_list))
    return plugin_list, count_plugins, all_skip_list


PLUGIN_REGEX = r".+?\.(?:esl|esm|esp)+$"  # Extracted constant for plugin validation


def clean_plugins(progress_emitter: ProgressEmitter) -> None:
    """
    Cleans plugins in the system and reports progress.
    """
    initialize_clean_process(progress_emitter)
    plugins_to_clean, total_plugins, skip_lists = fetch_plugin_info()
    ignore_list = fetch_ignore_list()
    info.local_skip_list.extend(ignore_list)

    progress_emitter.emit_max_value()
    progress_emitter.emit_visibility()

    print(f"✔️ CLEANING STARTED... ( PLUGINS TO CLEAN: {total_plugins} )")
    start_time = time.perf_counter()

    cleaned_plugin_count = clean_all_plugins(plugins_to_clean, skip_lists, progress_emitter)

    report_cleaning_completion(start_time, cleaned_plugin_count, total_plugins)
    log_failed_plugins()
    progress_emitter.emit_done()


# Helper Functions
def initialize_clean_process(progress_emitter: ProgressEmitter) -> None:
    """Initializes the cleaning process by setting up configurations and mode."""
    progress_emitter.task_completed = False
    print(f"❓ LOAD ORDER TXT is set to: {info.LOAD_ORDER_PATH}")
    print(f"❓ XEDIT EXE is set to: {info.XEDIT_PATH}")
    print(f"❓ MO2 EXE is set to: {info.MO2_PATH}")

    if info.MO2Mode:
        print("✔️ MO2 FOUND! SWITCHING TO MOD ORGANIZER 2 MODE...")
    else:
        print("❌ MO2 NOT FOUND. SWITCHING TO VORTEX MODE...")


def fetch_ignore_list() -> list[str]:
    """Fetches the list of plugins to ignore from settings."""
    return yaml_settings(str(PACT_IGNORE_PATH), f"PACT_Ignore_{get_game_mode(info).upper()}")


def fetch_plugin_info() -> tuple[list[str], int, list[str]]:
    """Initializes and fetches plugin-related information."""
    return init_plugins_info()


def clean_all_plugins(plugins: list[str], skip_lists: list[str], progress_emitter: ProgressEmitter) -> int:
    """Cleans all plugins and returns the count of cleaned plugins."""
    cleaned_count = 0
    for plugin in plugins:
        if should_clean(plugin, skip_lists):
            progress_emitter.emit_plugin_info(plugin)
            clean_plugin(plugin)
            cleaned_count += 1
            print(f"Finished cleaning: {plugin} ({cleaned_count})")
            progress_emitter.emit_progress(cleaned_count)
    return cleaned_count


def should_clean(plugin: str, skip_lists: list[str]) -> bool:
    """Checks whether a plugin should be cleaned."""
    return (
            not any(plugin in skip for skip in skip_lists)
            and re.search(PLUGIN_REGEX, plugin, re.IGNORECASE)
    )


def report_cleaning_completion(start_time: float, cleaned_count: int, total_count: int) -> None:
    """Reports and logs the results of the cleaning process."""
    elapsed_time = round(time.perf_counter() - start_time, 2)
    pact_log_update(f"\n✔️ CLEANING COMPLETE! Processed all plugins in {elapsed_time} seconds.")
    print(f"\n✔️ CLEANING COMPLETE! Processed {cleaned_count}/{total_count} plugins in {elapsed_time} seconds.")


def log_failed_plugins() -> None:
    """Logs any plugins that failed during cleaning."""
    categories = [
        (info.clean_failed_list, "❌ Plugins that failed cleaning:"),
        (info.clean_results_UDR, "✔️ Plugins with Undisabled Records cleaned:"),
        (info.clean_results_ITM, "✔️ Plugins with Identical To Master Records cleaned:"),
        (info.clean_results_NVM, "❌ Caution: Plugins with Deleted Navmeshes."),
        (info.clean_results_PARTIAL_FORMS, "✔️ Plugins with ITMs converted to Partial Forms:"),
    ]
    for plugins, message in categories:
        if plugins:
            print(f"\n{message}")
            for plugin in plugins:
                print(plugin)


if __name__ == "__main__":
    input("This is not the main file. Press Enter to exit...")
    raise SystemExit  # This is basically what sys.exit() does, but without having to import sys
