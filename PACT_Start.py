import datetime
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import psutil
import requests
import ruamel.yaml
from PySide6.QtCore import QObject, Signal

"""AUTHOR NOTES (POET)
- Comments marked as RESERVED in all scripts are intended for future updates or tests, do not edit / move / remove.
- (..., encoding="utf-8", errors="ignore") needs to go with every opened file because unicode errors are a bitch.
"""


class ProgressEmitter(QObject):  # type: ignore
    """
    Manages and emits progress-related signals for a plugin cleaning process.

    This class is responsible for handling and reporting progress updates, including
    the maximum value, current progress, and plugin-specific messages, as well as
    emitting signals to indicate task completion and visibility updates. It provides
    a structured way to track and communicate the status of a plugin cleaning operation.

    :ivar PROGRESS_MESSAGE_TEMPLATE: Template used for formatting progress messages for plugins.
    :type PROGRESS_MESSAGE_TEMPLATE: str
    :ivar progress: Signal emitted with the current progress value as an integer.
    :type progress: Signal
    :ivar max_value: Signal emitted with the maximum progress value as an integer.
    :type max_value: Signal
    :ivar plugin_value: Signal emitted with plugin-specific progress details as a string.
    :type plugin_value: Signal
    :ivar done: Signal emitted when the progress is completed.
    :type done: Signal
    :ivar visible: Signal emitted to control the visibility of progress tracking (e.g., UI visibility).
    :type visible: Signal
    :ivar task_completed: A boolean indicating whether the cleaning task is completed.
    :type task_completed: bool
    """
    PROGRESS_MESSAGE_TEMPLATE = "Cleaning {plugin} %v/%m - %p%"  # Extract constant for plugin message format

    progress = Signal(int)
    max_value = Signal(int)
    plugin_value = Signal(str)
    done = Signal()
    visible = Signal(bool)
    task_completed = False  # Renamed from `is_done` for clarity

    @staticmethod
    def _initialize_plugin_info() -> int:
        """
        Initializes plugin information and retrieves the maximum plugin count.
        :return: The maximum plugin count.
        """
        return init_plugins_info()[1]

    def emit_max_value(self) -> None:  # Renamed from `report_max_value`
        """
        Emits the maximum value processed by the plugin.

        This method calculates the maximum count of data being processed using an
        internal initialization function. It then emits this calculated maximum count
        via the `max_value` signal.

        :return: None
        """
        max_count = self._initialize_plugin_info()
        self.max_value.emit(max_count)

    def report_progress(self, count: int) -> None:
        """
        Emits the current progress value.
        :param count: The current progress value.
        """
        self.progress.emit(count)

    def report_plugin(self, plugin: str) -> None:
        """
        Emits a formatted description string about the current plugin process.
        :param plugin: The name of the current plugin.
        """
        self.plugin_value.emit(self.PROGRESS_MESSAGE_TEMPLATE.format(plugin=plugin))

    def report_done(self) -> None:
        """
        Marks the process as complete by emitting the `done` signal,
        and updating the task completion status.
        """
        self.done.emit()
        self.task_completed = True

    def emit_visibility(self, value = True) -> None:  # Renamed from `set_visible`
        """
        Emits a signal to set visibility to true.
        """
        self.visible.emit(value)
# =================== PACT TOML FILE ===================

yaml_cache = {}  # Cache for YAML files to prevent multiple reads.


def yaml_settings(yaml_path: str, key_path: str | list[str], new_value: Any = None) -> Any:
    """
    Access or modify values in a YAML file. This function allows traversing the YAML structure
    using a dot-separated key path or a list of keys. If a new value is provided, it updates the
    YAML file accordingly. If no new value is provided, it retrieves the current value at the
    specified key path. The function also maintains a cache of YAML data for efficient repeated access.

    :param yaml_path: The file path to the YAML file to be accessed or modified.
    :type yaml_path: str
    :param key_path: Dot-separated string or list of strings representing the path to the
        key in the YAML structure.
    :type key_path: str | list[str]
    :param new_value: Optional, the new value to set at the specified key path. If not provided,
        the function will return the value located at that key.
    :type new_value: Any, optional
    :return: The value at the specified key path in the YAML file. Returns None if the key
        is not found during retrieval, or if there is an error in grabbing the value.
    :rtype: Any
    """
    yaml = ruamel.yaml.YAML()
    yaml.indent(offset=2)
    yaml.width = 300

    if yaml_path not in yaml_cache:
        with Path(yaml_path).open(encoding="utf-8") as yaml_file:
            yaml_cache[yaml_path] = yaml.load(yaml_file)

    data = yaml_cache[yaml_path]

    keys = key_path.split(".") if isinstance(key_path, str) else key_path
    value = data
    # If new_value is provided, update the value.
    if new_value is not None:
        for key in keys[:-1]:
            value = value[key]

        value[keys[-1]] = new_value
        with Path(yaml_path).open("w", encoding="utf-8") as yaml_file:
            yaml.dump(data, yaml_file)
    # Otherwise, traverse YAML structure to get value.
    else:
        for key in keys:
            if key in value:
                value = value[key]
            else:
                return None  # Key not found.
        if value is None and "Path" not in key_path:  # Error me if I mistype or screw up the value grab.
            print(f"❌ ERROR (yaml_settings) : Trying to grab a None value for : '{key_path}'")

    yaml_cache[yaml_path] = data  # Update the cache with the modified data
    return value


def pact_settings(setting: str | None = None) -> str | bool | int | list[str] | None:
    """
    Retrieves or initializes the "PACT Settings.yaml" configuration file. If the
    file does not exist, it will create the YAML file based on default settings
    provided in "PACT Data/PACT Main.yaml". This function allows fetching specific
    settings by their keys. If a key is provided but its value is `None` and does
    not reference a file path, an error message will be printed to notify about
    the invalid key.

    :param setting: The specific configuration key to retrieve from "PACT
        Settings.yaml". If no key is provided, the function does not fetch any
        value. Defaults to None.

    :return: The value associated with the provided key. If the key is not
        specified or does not exist in the configuration file, it returns None.
        The type of the value can be `str`, `bool`, `int`, `list[str]`, or `None`.
    """
    if not Path("PACT Settings.yaml").exists():
        default_settings = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.default_settings")
        if default_settings is not None:
            with Path("PACT Settings.yaml").open("w", encoding="utf-8") as settings_file:
                settings_file.write(default_settings)
        else:
            print("❌ ERROR: Default settings could not be loaded.")
    if setting:
        get_setting = yaml_settings("PACT Settings.yaml", f"PACT_Settings.{setting}")
        if get_setting is None and "Path" not in setting:  # Error me if I make a stupid mistype.
            print(f"❌ ERROR (pact_settings)! Trying to grab a None value for : '{setting}'")
        return get_setting
    return None

@dataclass
class Info:
    """
    Represents configuration and state information related to Mod Organizer 2 (MO2),
    XEdit tools, and mod cleaning processes.

    This class stores and manages paths, expiration times, mode states, lists
    containing specific skip or usage configurations for different games, and logs.
    It also processes settings using external YAML data and provides central
    management for tool configurations. The purpose is to serve as a structured
    container for data essential to managing mod cleaning and related operations,
    ensuring efficient handling of paths, lists, processed plugins, and results.

    :ivar MO2_EXE: Path to the MO2 executable.
    :type MO2_EXE: str | Path
    :ivar MO2_PATH: Directory path of the MO2 installation.
    :type MO2_PATH: str | Path
    :ivar XEDIT_EXE: Path to the XEdit executable.
    :type XEDIT_EXE: str | Path
    :ivar XEDIT_PATH: Directory path of the XEdit installation.
    :type XEDIT_PATH: str | Path
    :ivar LOAD_ORDER_TXT: Path to the text file containing the load order.
    :type LOAD_ORDER_TXT: str | Path
    :ivar LOAD_ORDER_PATH: Directory path for load order-related files.
    :type LOAD_ORDER_PATH: str | Path
    :ivar Journal_Expiration: Expiration time for journal entries in days.
    :type Journal_Expiration: int
    :ivar Cleaning_Timeout: Timeout duration for cleaning processes in seconds.
    :type Cleaning_Timeout: int
    :ivar MO2Mode: Indicates whether the system is operating in MO2 mode.
    :type MO2Mode: bool
    :ivar xedit_list_fallout3: List of XEdit-related configurations specific to Fallout 3.
    :type xedit_list_fallout3: list[str]
    :ivar lower_fo3: Lowercase set representation of xedit_list_fallout3.
    :type lower_fo3: set[str]
    :ivar xedit_list_newvegas: List of XEdit-related configurations specific to Fallout New Vegas.
    :type xedit_list_newvegas: list[str]
    :ivar lower_fnv: Lowercase set representation of xedit_list_newvegas.
    :type lower_fnv: set[str]
    :ivar xedit_list_fallout4: Combined list for Fallout 4 and Fallout 4 VR XEdit configurations.
    :type xedit_list_fallout4: list[str]
    :ivar lower_fo4: Lowercase set representation of xedit_list_fallout4.
    :type lower_fo4: set[str]
    :ivar xedit_list_skyrimse: Combined list for Skyrim Special Edition and Skyrim VR XEdit configurations.
    :type xedit_list_skyrimse: list[str]
    :ivar lower_sse: Lowercase set representation of xedit_list_skyrimse.
    :type lower_sse: set[str]
    :ivar skyrimvr_list: XEdit configurations specific to Skyrim VR.
    :type skyrimvr_list: list[str]
    :ivar xedit_list_universal: List of XEdit configurations that apply universally across games.
    :type xedit_list_universal: list[str]
    :ivar xedit_list_specific: Aggregated list of XEdit configurations from multiple games.
    :type xedit_list_specific: list[str]
    :ivar lower_specific: Lowercase set representation of xedit_list_specific.
    :type lower_specific: set[str]
    :ivar lower_universal: Lowercase set representation of xedit_list_universal.
    :type lower_universal: set[str]
    :ivar clean_results_UDR: Set of plugins with "Undisabled References" results.
    :type clean_results_UDR: set[str]
    :ivar clean_results_ITM: Set of plugins with "Identical To Master" results.
    :type clean_results_ITM: set[str]
    :ivar clean_results_NVM: Set of plugins with "Deleted Navmeshes" results.
    :type clean_results_NVM: set[str]
    :ivar clean_results_PARTIAL_FORMS: Set of plugins with "Partial Forms."
    :type clean_results_PARTIAL_FORMS: set[str]
    :ivar clean_failed_list: Set of plugins that failed the cleaning process.
    :type clean_failed_list: set[str]
    :ivar plugins_processed: Number of plugins that have been processed.
    :type plugins_processed: int
    :ivar plugins_cleaned: Number of plugins successfully cleaned.
    :type plugins_cleaned: int
    :ivar local_skip_list: Localized skip list at runtime.
    :type local_skip_list: list[str]
    :ivar FO3_skip_list: Specific skip list for Fallout 3 plugins.
    :type FO3_skip_list: list[str]
    :ivar FNV_skip_list: Specific skip list for Fallout New Vegas plugins.
    :type FNV_skip_list: list[str]
    :ivar FO4_skip_list: Specific skip list for Fallout 4 plugins.
    :type FO4_skip_list: list[str]
    :ivar SSE_skip_list: Specific skip list for Skyrim Special Edition plugins.
    :type SSE_skip_list: list[str]
    :ivar VIP_skip_list: Combined skip list for all key plugins across games.
    :type VIP_skip_list: list[str]
    :ivar XEDIT_LOG_TXT: Path to the main XEdit log file.
    :type XEDIT_LOG_TXT: str
    :ivar XEDIT_EXC_LOG: Path to the XEdit exception log file.
    :type XEDIT_EXC_LOG: str
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
    xedit_list_fallout3: list[str] = field(default_factory=lambda: yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO3") or [])
    lower_fo3: ClassVar[set[str]] = {item.lower() for item in xedit_list_fallout3} or set()
    xedit_list_newvegas: list[str] = field(default_factory=lambda: yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FNV") or [])
    lower_fnv: ClassVar[set[str]] = {item.lower() for item in xedit_list_newvegas} or set()
    xedit_list_fallout4: list[str] = field(default_factory=lambda: yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO4") or [])
    xedit_list_fallout4.extend(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO4VR") or [])
    lower_fo4: ClassVar[set[str]] = {item.lower() for item in xedit_list_fallout4} or set()
    xedit_list_skyrimse: list[str] = field(default_factory=lambda: yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.SSE") or [])
    skyrimvr_list: list[str] = field(default_factory=lambda: yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.SkyrimVR") or [])
    xedit_list_skyrimse.extend(skyrimvr_list)
    lower_sse: ClassVar[set[str]] = {item.lower() for item in xedit_list_skyrimse} or set()
    xedit_list_universal: list[str] = field(default_factory=list)
    xedit_list_specific: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.xedit_list_universal = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.Universal") or []
        self.FO3_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO3") or []
        self.FNV_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FNV") or []
        self.FO4_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO4") or []
        self.SSE_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.SSE") or []
        self.VIP_skip_list = (
            (self.FO3_skip_list or [])
            + (self.FNV_skip_list or [])
            + (self.FO4_skip_list or [])
            + (self.SSE_skip_list or [])
        )
        self.xedit_list_specific = (
            self.xedit_list_fallout3
            + self.xedit_list_newvegas
            + self.xedit_list_fallout4
            + self.xedit_list_skyrimse
        )

    lower_specific: ClassVar[set[str]] = {item.lower() for item in xedit_list_specific} or set()
    lower_universal: ClassVar[set[str]] = {item.lower() for item in xedit_list_universal} or set()

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

    # noinspection PyRedeclaration
    def __post_init__(self) -> None:
        self.xedit_list_universal = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.Universal") or []
        self.FO3_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO3") or []
        self.FNV_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FNV") or []
        self.FO4_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO4") or []
        self.SSE_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.SSE") or []
        self.VIP_skip_list = (
            (self.FO3_skip_list or [])
            + (self.FNV_skip_list or [])
            + (self.FO4_skip_list or [])
            + (self.SSE_skip_list or [])
        )

def normalize_name(input_string: str) -> str:
    """
    Normalize the input string by extracting the name portion of the path
    and converting it to lowercase.

    :param input_string: The input string representing a file or directory
        path.
    :type input_string: str
    :return: The lowercase name extracted from the input path.
    :rtype: str
    """
    return Path(input_string).name.lower()


def matches_condition(compare_string: str, data: Info) -> bool:
    """
    Checks if the normalized form of a given comparison string matches any of the
    lowercase specific or universal entries in the provided data object.

    The function uses the `normalize_name` method to preprocess the `compare_string`,
    and then checks for its membership in two lowercase collections (`lower_specific`
    and `lower_universal`) in the `data` object.

    :param compare_string: The string to be compared after normalization.
    :type compare_string: str
    :param data: The information object containing lowercase collections to compare against.
    :type data: Info
    :return: A boolean value indicating if the normalized `compare_string`
             matches any entry in the `lower_specific` or `lower_universal` properties of `data`.
    :rtype: bool
    """
    normalized_name = normalize_name(compare_string)
    return normalized_name in data.lower_specific or normalized_name in data.lower_universal


if not Path("PACT Ignore.yaml").exists():
    default_ignorefile = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.default_ignorefile")
    if default_ignorefile is not None:
        with Path("PACT Ignore.yaml").open("w", encoding="utf-8") as file:
            file.write(default_ignorefile)
    else:
        print("❌ ERROR: Default ignore file could not be loaded.")


def pact_journal_expire() -> None:
    """
    Delete the journal log file if it is older than the predefined expiration time.

    The function checks a journal file stored in the current working directory with a
    specific name. If the file exists, it calculates its age in days based on its last
    modified timestamp. If the file's age exceeds the expiration time defined in
    `info.Journal_Expiration`, the file gets deleted from the system.

    :return: None
    """
    # Delete journal if older than set amount of days.

    PACT_folder = Path.cwd()
    journal_name = "PACT Journal.log"
    journal_path = PACT_folder / journal_name
    if journal_path.is_file():
        journal_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(journal_path.stat().st_mtime)
        journal_age_days = journal_age.days
        if journal_age_days > info.Journal_Expiration:
            journal_path.unlink()


def pact_log_update(log_message: str) -> None:
    """
    Logs a message to a file named "PACT Journal.log". The function appends the
    provided log message to the log file, ensuring the message is written using
    UTF-8 encoding and ignoring any encoding-related errors.

    :param log_message: The message to be logged. Must be a string.
    :type log_message: str
    :return: This function does not return a value.
    :rtype: None
    """
    with Path("PACT Journal.log").open("a", encoding="utf-8", errors="ignore") as LOG_PACT:
        LOG_PACT.write(log_message)


def pact_ignore_update(plugin: str, game: str) -> None:
    """
    Adds the specified plugin to the ignore list for updates for a given game. This function utilizes
    a YAML settings file to maintain an ignore list for each game, updating it by appending the plugin
    name to the corresponding list.

    :param plugin: The name of the plugin to be ignored in updates.
    :type plugin: str
    :param game: The name of the game for which the plugin should be ignored.
    :type game: str
    :return: No return value (None).
    :rtype: None
    """
    ignore_list = yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{game}") or []
    ignore_list.append(plugin)
    yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{game}", ignore_list)


# =================== WARNING MESSAGES ==================
# Can change first line to """\ to remove the spacing.

PAUSE_MESSAGE = "Press Enter to continue..."

# =================== UPDATE FUNCTION ===================


def pact_update_check() -> bool:
    """
    Checks for updates to the Plugin Auto Cleaning Tool (PACT).

    This function performs an update check to determine if a newer version of PACT is
    available. It fetches the latest release information from the PACT GitHub repository
    and compares it with the currently installed version. The comparison result determines
    if an update is available or if the user already has the latest version. The function
    handles network-related errors as well as the case when update checks are disabled
    in the settings.

    :raises OSError: If there is an operating system-related issue during the request.
    :raises requests.exceptions.RequestException: If there is an issue fetching data
        from the GitHub repository API.

    :return: True if the currently installed PACT version is up-to-date, False otherwise.
    :rtype: bool
    """
    if pact_settings("Update Check"):  # type: ignore
        print("❓ CHECKING FOR ANY NEW PLUGIN AUTO CLEANING TOOL (PACT) UPDATES...")
        print("   (You can disable this check in the EXE or PACT Settings.toml) \n")
        try:
            response = requests.get("https://api.github.com/repos/evildarkarchon/XEdit-PACT/releases/latest")
            PACT_Received = response.json()["name"]
            if PACT_Received == yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.version"):
                print("\n✔️ You have the latest version of PACT!")
                return True
            else:  # noqa: RET505
                print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Warnings.Outdated_PACT"))
                print("===============================================================================")
        except (OSError, requests.exceptions.RequestException):
            print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Warnings.PACT_Update_Failed"))
            print("===============================================================================")
    else:
        print("\n ❌ NOTICE: UPDATE CHECK IS DISABLED IN PACT INI SETTINGS \n")
        print("===============================================================================")
    return False


# =================== TERMINAL OUTPUT START ====================
print(
    f"Hello World! | Plugin Auto Cleaning Tool (PACT) | Version {yaml_settings('PACT Data/PACT Main.yaml', 'PACT_Data.version')!s} | FO3, FNV, FO4, SSE"
)
print("MAKE SURE TO SET THE CORRECT LOAD ORDER AND XEDIT PATHS BEFORE CLEANING PLUGINS")
print("===============================================================================")

info = Info()


def update_load_order_path(
        data: Info, load_order_path: str | Path) -> None:
    """
    Updates the load order path for the given data object. This function updates the
    LOAD_ORDER_PATH attribute with the specified path and sets the LOAD_ORDER_TXT
    attribute to the file name of the path if the path is provided. If the path is
    None, the LOAD_ORDER_TXT attribute is set to an empty string.

    :param data: The data object with attributes to update.
    :type data: Info
    :param load_order_path: The new path to the load order file.
                           Can be a string or a Path object.
    :type load_order_path: str | Path
    :return: None
    """
    data.LOAD_ORDER_PATH = load_order_path
    if load_order_path is not None:
        data.LOAD_ORDER_TXT = Path(load_order_path).name
    else:
        data.LOAD_ORDER_TXT = ""


def update_xedit_path(data: Info, xedit: str | Path) -> None:
    """
    Updates the `XEDIT_PATH` and `XEDIT_EXE` attributes in the provided `data` object
    based on the provided `xedit` value. If `xedit` is a valid executable file path,
    it assigns the path and file name accordingly. If `xedit` is a directory path,
    it searches for an appropriate `.exe` file and assigns it to the `data` object.
    If the `xedit` is not provided or invalid, it resets these attributes to empty
    strings.

    :param data: An Info object that contains `XEDIT_PATH` and `XEDIT_EXE` attributes
        which are updated based on the provided `xedit` value.
        Expected to act as a writable configuration holder.
    :type data: Info
    :param xedit: The path to the xEdit executable file or a directory containing
        the xEdit executable file. Can be provided as a string or a pathlib.Path
        object.
    :type xedit: str | Path
    :return: Nothing is returned. The provided `data` object is updated directly.
    :rtype: None
    """
    data.XEDIT_PATH = xedit
    if xedit is not None:
        if ".exe" in str(xedit):
            data.XEDIT_EXE = Path(xedit).name
        elif Path(xedit).exists():
            for xedit_file in os.listdir(xedit):
                if xedit_file.endswith(".exe") and matches_condition(str(xedit_file), data):
                    data.XEDIT_PATH = Path(xedit) / xedit_file
                    data.XEDIT_EXE = Path(data.XEDIT_PATH).name
    else:
        data.XEDIT_EXE = ""
        data.XEDIT_PATH = ""


def update_mo2_path(data: Info, mo2_path: str | Path) -> None:
    """
    Updates the MO2 path in the provided Info object based on the given path or executable. If the path
    provided is an executable, assigns that as the MO2 executable path. Otherwise, if it's a directory
    that contains executable files matching a specific naming pattern, it assigns the matching executable
    file as the MO2 executable. If no path is provided, it resets the MO2 path and executable values
    within the Info object.

    :param data: The Info object on which the MO2 path and executable values need to be updated.
    :type data: Info
    :param mo2_path: The path or file to analyze and assign as the new MO2 path or executable.
    :type mo2_path: str | Path
    :return: This function does not return any value.
    :rtype: None
    """
    if mo2_path is not None:
        data.MO2_PATH = mo2_path
        if ".exe" in str(mo2_path):
            data.MO2_EXE = Path(mo2_path).name
        elif Path(mo2_path).exists():
            for mo2_file in os.listdir(mo2_path):
                if mo2_file.endswith(".exe") and ("mod" in str(mo2_file).lower() or "mo2" in str(mo2_file).lower()):
                    data.MO2_PATH = Path(mo2_path) / mo2_file
                    data.MO2_EXE = Path(data.MO2_PATH).name
    else:
        data.MO2_EXE = ""
        data.MO2_PATH = ""


def pact_update_settings(data: Info) -> None:
    """
    Updates the provided `Info` data object with settings fetched from PACT configuration.
    The function retrieves various settings, validates them, and applies them to the
    appropriate attributes of the given `Info` instance. This includes settings for
    load order paths, executable paths, cleaning timeouts, and journal expiration periods.

    :param data: The `Info` instance to be updated with settings values.
    :type data: Info
    :raises ValueError: If the Cleaning Timeout value from PACT settings is not a
        valid positive integer or is below the minimum required value of 30 seconds.
    :raises ValueError: If the Journal Expiration value from PACT settings is not a
        valid positive integer or is less than the minimum required value of 1 day.
    :return: This function does not return a value. It updates the `data` object in place.
    :rtype: None
    """
    load_order_path = pact_settings("LoadOrder TXT")
    if isinstance(load_order_path, (str, Path)):
        update_load_order_path(data, load_order_path)
    xedit_exe_setting = pact_settings("XEDIT EXE")
    if isinstance(xedit_exe_setting, (str, Path)):
        update_xedit_path(data, xedit_exe_setting)
    mo2_exe_setting = pact_settings("MO2 EXE")
    if isinstance(mo2_exe_setting, (str, Path)):
        update_mo2_path(data, mo2_exe_setting)
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

    if not isinstance(data.Cleaning_Timeout, int) or data.Cleaning_Timeout <= 0:
        raise ValueError("""❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Cleaning Timeout to a valid positive number.""")
    elif data.Cleaning_Timeout < 30:  # noqa: RET506
        raise ValueError("""❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS TOO SMALL.)
Cleaning Timeout must be set to at least 30 seconds or more.""")

    if not isinstance(data.Journal_Expiration, int) or data.Journal_Expiration <= 0:
        raise ValueError("""❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Journal Expiration to a valid positive number.""")
    elif data.Journal_Expiration < 1:  # noqa: RET506
        raise ValueError("""❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS TOO SMALL.)
Journal Expiration must be set to at least 1 day or more.""")


pact_update_settings(info)
if ".exe" in str(info.XEDIT_PATH) and info.XEDIT_EXE in info.xedit_list_specific:
    xedit_path = Path(info.XEDIT_PATH)
    info.XEDIT_LOG_TXT = str(xedit_path.with_name(xedit_path.stem.upper() + "_log.txt"))
    info.XEDIT_EXC_LOG = str(xedit_path.with_name(xedit_path.stem.upper() + "Exception.log"))
elif info.XEDIT_PATH and ".exe" not in str(info.XEDIT_PATH):
    print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_XEDIT_File"))
    input(PAUSE_MESSAGE)
    raise ValueError


# Make sure Mod Organizer 2 is not already running.
def check_process_mo2(progress_emitter: ProgressEmitter) -> bool:
    """
    Checks if Mod Organizer 2 (MO2) is currently running and reports an error if it
    is detected. The function verifies the existence of the MO2 path and searches
    for any running processes with a name matching the MO2 executable. If found,
    an error message is printed, `progress_emitter` is used to indicate completion,
    and the function returns True. Otherwise, it returns False.

    :param progress_emitter: Emits signals to report progress or completion of the
        operation.
    :type progress_emitter: ProgressEmitter
    :return: True if MO2 is found running; otherwise, False.
    :rtype: bool
    """
    pact_update_settings(info)
    if Path(info.MO2_PATH).exists():
        mo2_procs = [
            proc
            for proc in psutil.process_iter(attrs=["pid", "name"])
            if str(info.MO2_EXE).lower() in proc.name().lower()
        ]
        for proc in mo2_procs:
            if str(info.MO2_EXE).lower() in proc.name().lower():
                print("""❌ ERROR : CANNOT START PACT WHILE MOD ORGANIZER 2 IS ALREADY RUNNING!
PLEASE CLOSE MO2 AND RUN PACT AGAIN! (DO NOT RUN PACT THROUGH MO2)""")
                progress_emitter.report_done()
                return True
    return False


# Clear xedit log files to check them for each plugin separately.
def clear_xedit_logs() -> None:
    """
    Clears the xEdit log files if they exist in the specified paths. This function
    attempts to delete specific log files related to xEdit, ensuring they are
    removed from the system. It handles file existence before attempting
    removal and manages exceptions that might arise during the process.

    :raises PermissionError: Raised if the program does not have sufficient
        permissions to delete the files.
    :raises OSError: Raised for errors such as the file being locked or other
        OS-related issues while attempting deletion.
    :return: None
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
    Validates the integrity of specific settings to ensure required file paths and INI
    settings are correctly defined and functional. The function performs a series of
    checks, including the existence of necessary file paths and the compatibility between
    load order configurations and the selected xEdit executable. It raises a ValueError
    if critical requirements are found to be invalid or missing.

    :raises ValueError: If the required file paths are missing, INI settings are
        incorrect, or the load order file or xEdit executable does not meet the
        validation criteria.
    """
    pact_update_settings(info)
    if Path(info.LOAD_ORDER_PATH).exists() and Path(info.XEDIT_PATH).exists():
        print("✔️ REQUIRED FILE PATHS FOUND! CHECKING IF INI SETTINGS ARE CORRECT...")
    else:
        print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Warnings.Invalid_INI_Path"))
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
            LO_Plugins = LO_Check.read()
            if not any(
                game in LO_Plugins and str(info.XEDIT_EXE).lower() in executables
                for game, executables in valid_xedit_executables.items()
            ):
                print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Warnings.Invalid_INI_Setup"))
                input(PAUSE_MESSAGE)
                raise ValueError
    elif "loadorder" not in str(info.LOAD_ORDER_PATH) and str(info.XEDIT_EXE).lower() in info.lower_universal:
        print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_LO_File"))
        input(PAUSE_MESSAGE)
        raise ValueError


def update_log_paths(data: Info, game_mode: str | None = None) -> None:
    """
    Updates the paths for log files associated with xEdit. The function dynamically configures
    the file names of log and exception logs based on the provided game mode. If no game mode is
    specified, the log paths are constructed using the stem of the existing xEdit path.

    :param data: An instance of the `Info` class containing the path to xEdit and pre-defined
        attributes for the log file paths.
    :type data: Info
    :param game_mode: The optional game mode that determines the prefix or naming convention for
        the log files.
    :type game_mode: str | None
    :return: This function does not return any value; it updates the given `data` object with
        new log paths.
    :rtype: None
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
    Generates a command-line string for executing xEdit, a utility tool
    used in modding Bethesda games, based on provided configuration data.
    This function supports execution through Mod Organizer 2 (MO2) as well
    as standalone execution, allowing customization through parameters such
    as game mode and whether partial forms functionality is enabled.

    :param data: Represents the configuration and paths required for execution.
    :param plugin_name: The name of the plugin file to be loaded by xEdit.
    :param universal: Flag to determine whether the command is for universal game
        mode compatibility.
    :param game_mode: Specifies the game mode to be targeted (optional).
    :return: A string representing the xEdit command-line, or None if an invalid
        configuration is provided.
    """
    commandline = ""
    match data.MO2Mode, universal:
        case True, True:
            commandline = f'"{data.MO2_PATH}" run "{data.XEDIT_PATH}" -a "-{game_mode} -QAC -autoexit -autoload \\"{plugin_name}\\""'
        case True, False:
            commandline = f'"{data.MO2_PATH}" run "{data.XEDIT_PATH}" -a "-QAC -autoexit -autoload \\"{plugin_name}\\""'
        case False, True:
            commandline = f'"{data.XEDIT_PATH}" -a -{game_mode} -QAC -autoexit -autoload "{plugin_name}"'
        case False, False:
            commandline = f'"{data.XEDIT_PATH}" -a -QAC -autoexit -autoload "{plugin_name}"'
        case _:
            print("Invalid xedit executable specified")

    if commandline:
        return (
            commandline.replace("-QAC", "-iknowwhatimdoing -QAC -allowmakepartial")
            if pact_settings("Partial Forms")
            else commandline
        )
    else:  # noqa: RET505
        print("Invalid xedit executable specified")
        return None


def get_game_mode(data: Info) -> str:
    """
    Reads the load order file to determine the game mode. The function inspects each
    line of the specified load order file to find the presence of specific markers
    corresponding to different games such as Skyrim, Fallout 3, Fallout NV, or
    Fallout 4. Based on the content, it returns a string identifying the game mode.
    If the file cannot be found or accessed, it raises an appropriate exception. If
    none of the expected markers are found in the file, a ValueError is raised.

    :param data: An instance containing the attribute `LOAD_ORDER_PATH`, which
        points to the path of the load order file to inspect.
    :type data: Info
    :return: A string identifying the determined game mode. Expected values are
        "sse" for Skyrim, "fo3" for Fallout 3, "fnv" for Fallout NV, and "fo4"
        for Fallout 4.
    :rtype: str
    :raises FileNotFoundError: If the load order file does not exist at the
        specified path.
    :raises ValueError: If none of the game mode markers are detected in the file.
    :raises Exception: For any other errors encountered while accessing or reading
        the file.
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
    except Exception as e:
        print(f"Error reading load order file: {data.LOAD_ORDER_PATH}, error: {e!s}")
        raise
    else:
        raise ValueError("❌ ERROR: UNABLE TO DETERMINE GAME MODE!")


def check_cpu_usage(proc: psutil.Process) -> bool | None:
    """
    Checks if the CPU usage of the given process is below a specified threshold,
    or if the process status is among certain terminal states. The function
    returns `False` if the process cannot be checked due to access permissions,
    nonexistence, or errors such as a zombie process.

    :param proc: The target process to check.
    :type proc: psutil.Process
    :return: Returns `True` if the process is running and meets the CPU usage
        threshold or has a terminal state (`psutil.STATUS_ZOMBIE` or
        `psutil.STATUS_DEAD`). Returns `False` if there is an error or the
        process does not satisfy the conditions. May return `None` if no
        conditions match.
    :rtype: bool | None
    :raises psutil.NoSuchProcess: If the specified process does not exist.
    :raises psutil.AccessDenied: If there is no permission to access the process.
    :raises psutil.ZombieProcess: If the process is a zombie.
    :raises subprocess.CalledProcessError: If a subprocess-related error occurs.
    """
    try:
        return proc.is_running() and (
            proc.cpu_percent(interval=5) < 1 or proc.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, subprocess.CalledProcessError):
        return False


def check_process_timeout(proc: psutil.Process, data: Info) -> bool:
    """
    Checks if a process has exceeded its timeout based on its creation time and a
    specified cleaning timeout.

    This function determines whether the elapsed time since the creation of a given
    process exceeds the provided cleaning timeout value. The comparison is based
    on the current system time and the process's creation timestamp.

    :param proc: The process to evaluate.
    :type proc: psutil.Process
    :param data: The object containing the Cleaning_Timeout used for comparison.
    :type data: Info
    :return: True if the process timeout has been exceeded, otherwise False.
    :rtype: bool
    """
    create_time = proc.create_time()
    return (time.time() - create_time) > data.Cleaning_Timeout


def check_process_exceptions(data: Info) -> bool:
    """
    Checks the content of the specified log file for specific exception phrases.

    This function checks if a log file specified in the `data` object exists. If
    the log file is present, the function reads its content and searches for
    specific exception phrases that indicate errors. If such phrases are found,
    it returns `True`, indicating that an exception matching the criteria is
    detected. Otherwise, it returns `False`.

    :param data: The `Info` object containing the path to the log file (`XEDIT_EXC_LOG`).
    :type data: Info
    :return: Returns `True` if specific exception phrases are found in the log
             content, otherwise `False`.
    :rtype: bool
    """
    if Path(data.XEDIT_EXC_LOG).exists():
        xedit_exc_out = subprocess.check_output(["powershell", "-command", f"Get-Content {data.XEDIT_EXC_LOG}"])
        Exception_Check = xedit_exc_out.decode()
        if "which can not be found" in Exception_Check or "which it does not have" in Exception_Check:
            return True
    return False


def handle_error(
    proc: psutil.Process, plugin_name: str, data: Info, error_message: str, add_ignore: bool = True
) -> None:
    """
    Handle errors that occur during a plugin processing, ensuring proper cleanup and error
    handling for the given process. This function terminates the process, adjusts plugin
    tracking states, updates failure lists, clears logs if debug mode is disabled, logs
    the error message, and optionally updates an ignore list for the game mode.

    :param proc: Process that is being handled, typically the plugin processing workflow.
    :type proc: psutil.Process
    :param plugin_name: Name of the plugin that caused the error.
    :type plugin_name: str
    :param data: Object that keeps track of processing states, error lists, and relevant
        information about plugins.
    :type data: Info
    :param error_message: Message describing the error, intended for logging or display.
    :type error_message: str
    :param add_ignore: Indicates whether to add the plugin to the ignore list. Default is True.
    :type add_ignore: bool
    :return: This function does not return a value; its operations are intended for side effects.
    :rtype: None
    """
    try:
        proc.kill()
    except (
        PermissionError,
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
        subprocess.CalledProcessError,
    ):
        pass
    finally:
        time.sleep(1)
        if not pact_settings("Debug Mode"):
            clear_xedit_logs()
        data.plugins_processed -= 1
        if isinstance(data.clean_failed_list, set):
            data.clean_failed_list.add(plugin_name)
        else:
            data.clean_failed_list.add(plugin_name)
        print(error_message)
        if add_ignore:
            pact_ignore_update(plugin_name, get_game_mode(data).upper())


def create_bat_command(data: Info, plugin_name: str) -> str | None:
    """
    Creates a batch command for xEdit operations based on the provided data and plugin name.
    The function determines the appropriate executable or load order file settings, generates
    a command, and performs necessary configuration updates. If configuration is incorrect,
    an appropriate error is raised, and the user is notified.

    :param data: Input information object encapsulating paths, filenames, and game-related details
    :type data: Info
    :param plugin_name: Name of the plugin that will be processed
    :type plugin_name: str
    :return: The generated batch command string if successful, or None if not applicable
    :rtype: str | None
    :raises ValueError: If the load order file or xEdit settings are invalid, causing the process to stop
    :raises RuntimeError: If unable to start the cleaning process due to misconfigured settings or invalid paths
    """
    xedit_exe_lower = str(data.XEDIT_EXE).lower()
    str(data.XEDIT_PATH)

    if xedit_exe_lower in data.lower_specific:
        update_log_paths(data)
        bat_command = create_xedit_command(data, plugin_name, False)
        if bat_command:
            return bat_command

    if "loadorder" in str(data.LOAD_ORDER_PATH).lower() and xedit_exe_lower in data.lower_universal:
        game_mode = get_game_mode(data)
        if game_mode is None:
            print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_LO_File"))
            input(PAUSE_MESSAGE)
            raise ValueError

        update_log_paths(data, game_mode)
        bat_command = create_xedit_command(data, plugin_name, True, game_mode)

        if bat_command:
            return bat_command

    print("""❓ ERROR : UNABLE TO START THE CLEANING PROCESS! WRONG INI SETTINGS OR FILE PATHS?
    If you're seeing this, make sure that your load order / xedit paths are correct.
    If problems continue, try a different load order file or xedit executable.
    If nothing works, please report this error to the PACT Nexus page.""")
    input(PAUSE_MESSAGE)
    raise RuntimeError("Unable to start the cleaning process")


def run_auto_cleaning(plugin_name: str) -> None:
    """
    Runs the automatic cleaning process for a specified plugin by creating and executing
    a batch command in a separate subprocess. Clears logs, initiates a monitoring thread,
    and increments the count of processed plugins upon completion.

    :param plugin_name: Name of the plugin that requires cleaning.
    :type plugin_name: str
    :raises ValueError: If the batch command to be run in the subprocess is invalid.
    :return: This function does not return any value.
    :rtype: None
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

    # Increment processed plugins count
    info.plugins_processed += 1


def monitor_process(proc: subprocess.Popen, plugin_name: str) -> None:
    """
    Monitors the given subprocess, handling any runtime issues or errors related
    to the process, specifically monitoring its behavior and managing its lifecycle.

    This function continuously observes the provided subprocess for conditions
    that meet pre-defined error scenarios. Upon detecting such conditions,
    appropriate error-handling functions are invoked, and the process is
    managed or terminated accordingly.

    :param proc: The subprocess object representing the process to be monitored.
                 It should be a subprocess.Popen instance.
    :type proc: subprocess.Popen
    :param plugin_name: The string name of the plugin associated with the monitored process.
                        Helps in identifying and logging process-specific issues.
    :type plugin_name: str
    :return: This function does not return a value; it modifies application state
             and process lifecycle as necessary.
    :rtype: None
    """
    ERROR_MESSAGES = {
        "disabled_or_missing": "❌ ERROR : PLUGIN IS DISABLED OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...",
        "timeout": "❌ ERROR : XEDIT TIMED OUT (CLEANING PROCESS TOOK TOO LONG)! KILLING XEDIT...",
        "empty_or_missing": "❌ ERROR : PLUGIN IS EMPTY OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...",
    }

    def handle_process_error(xedit_process: psutil.Process, error_type: str, add_ignore: bool = True) -> None:
        """Handles xedit_process errors by logging and terminating."""
        handle_error(xedit_process, plugin_name, info, ERROR_MESSAGES[error_type], add_ignore)
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
            p for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "create_time"])
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
    Process a single log line to check for cleaning patterns and update results.

    :param line: The log line to process.
    :param plugin_name: Name of the plugin for which results are being checked.
    :return: True if a cleaning action was detected, False otherwise.
    """
    for pattern, (message, results_list) in LOG_PATTERNS.items():
        if pattern.search(line):
            pact_log_update(f"\n{plugin_name} -> {message}")
            results_list.add(plugin_name)
            return True
    return False


def check_cleaning_results(plugin_name: str) -> None:
    """
    Check cleaning results of a specific plugin by processing the log files generated by xEdit.

    :param plugin_name: Name of the plugin for which cleaning results are being checked.
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
            info.plugins_cleaned += 1
        else:
            pact_log_update(f"\n{plugin_name} -> NOTHING TO CLEAN")
            print("NOTHING TO CLEAN! Adding plugin to PACT Ignore file...")
            pact_ignore_update(plugin_name, get_game_mode(info).upper())
            info.local_skip_list.append(plugin_name)

        if not pact_settings("Debug Mode"):
            clear_xedit_logs()


def get_plugin_list(load_order_path: str) -> list[str]:
    """
    Extracts and returns a list of plugins from a given load order file. The method processes the
    load order file depending on whether its name contains "plugins.txt". For "plugins.txt" files,
    it filters lines containing an asterisk and removes the asterisk. For other files, it excludes
    lines with '.ghost' extensions.

    :param load_order_path: Path to the load order file that contains plugin details.
    :type load_order_path: str
    :return: A list of plugins extracted from the load order file.
    :rtype: list[str]
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
    Cleans the provided plugin by performing automatic cleaning and verifying
    the cleaning results.

    :param plugin: The name of the plugin to be cleaned.
    :type plugin: str
    :return: None
    """
    run_auto_cleaning(plugin)
    check_cleaning_results(plugin)


def init_plugins_info() -> tuple[list[str], int, list[str]]:
    """
    Initializes and retrieves information about plugins.

    This function collects information about plugins by loading the plugin list
    from a specific file path, filters out those plugins that are included in the
    combination of skip lists (`VIP_skip_list` and `local_skip_list`), and calculates
    the count of unique plugins that are not skipped.

    :return: A tuple containing the following:
             - A list of plugin names from the load order file.
             - The count of unique plugins after excluding skipped plugins.
             - The combined skip list of VIP and local skipped plugins.
    :rtype: tuple[list[str], int, list[str]]
    """
    ALL_skip_list = info.VIP_skip_list + info.local_skip_list
    plugin_list = get_plugin_list(str(info.LOAD_ORDER_PATH))
    count_plugins = len(set(plugin_list) - set(ALL_skip_list))
    return plugin_list, count_plugins, ALL_skip_list


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

    cleaned_plugin_count = clean_all_plugins(
        plugins_to_clean, skip_lists, progress_emitter
    )

    report_cleaning_completion(start_time, cleaned_plugin_count, total_plugins)
    log_failed_plugins()
    progress_emitter.report_done()


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
    return yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{get_game_mode(info).upper()}")


def fetch_plugin_info() -> tuple[list[str], int, list[str]]:
    """Initializes and fetches plugin-related information."""
    return init_plugins_info()


def clean_all_plugins(
        plugins: list[str], skip_lists: list[str], progress_emitter: ProgressEmitter
) -> int:
    """Cleans all plugins and returns the count of cleaned plugins."""
    cleaned_count = 0
    for plugin in plugins:
        if should_clean(plugin, skip_lists):
            progress_emitter.report_plugin(plugin)
            clean_plugin(plugin)
            cleaned_count += 1
            print(f"Finished cleaning: {plugin} ({cleaned_count})")
            progress_emitter.report_progress(cleaned_count)
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
