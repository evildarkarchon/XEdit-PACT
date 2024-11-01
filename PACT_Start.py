# PLUGIN AUTO CLEANING TOOL (PACT) | By Poet (The Sound Of Snow)
from __future__ import annotations

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

'''AUTHOR NOTES (POET)
- Comments marked as RESERVED in all scripts are intended for future updates or tests, do not edit / move / remove.
- (..., encoding="utf-8", errors="ignore") needs to go with every opened file because unicode errors are a bitch.
'''

# =================== PACT TOML FILE ===================

yaml_cache = {} # Cache for YAML files to prevent multiple reads.

def yaml_settings(yaml_path: str, key_path: str | list[str], new_value: Any = None) -> Any:
    yaml = ruamel.yaml.YAML()
    yaml.indent(offset=2)
    yaml.width = 300

    if yaml_path not in yaml_cache:
        with Path(yaml_path).open(encoding='utf-8') as yaml_file:
            yaml_cache[yaml_path] = yaml.load(yaml_file)

    data = yaml_cache[yaml_path]

    keys = key_path.split('.') if isinstance(key_path, str) else key_path
    value = data
    # If new_value is provided, update the value.
    if new_value is not None:
        for key in keys[:-1]:
            value = value[key]

        value[keys[-1]] = new_value
        with Path(yaml_path).open('w', encoding='utf-8') as yaml_file:
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

def pact_settings(setting: str | None = None) -> Any:
    if not Path("PACT Settings.yaml").exists():
        default_settings = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.default_settings")
        if default_settings is not None:
            with Path('PACT Settings.yaml').open('w', encoding='utf-8') as file:
                file.write(default_settings)
        else:
            print("❌ ERROR: Default settings could not be loaded.")
    if setting:
        get_setting = yaml_settings("PACT Settings.yaml", f"PACT_Settings.{setting}")
        if get_setting is None and "Path" not in setting:  # Error me if I make a stupid mistype.
            print(f"❌ ERROR (pact_settings)! Trying to grab a None value for : '{setting}'")
        return get_setting
    return None

def is_it_xedit(compare_string: str, info: Info) -> bool:
    return bool(Path(compare_string).name.lower() in info.lower_specific or Path(compare_string).name.lower() in info.lower_universal)

if not Path("PACT Ignore.yaml").exists():
    default_ignorefile = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.default_ignorefile")
    if default_ignorefile is not None:
        with Path('PACT Ignore.yaml').open('w', encoding='utf-8') as file:
            file.write(default_ignorefile)
    else:
        print("❌ ERROR: Default ignore file could not be loaded.")

def pact_journal_expire() -> None:
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

    with Path("PACT Journal.log").open("a", encoding="utf-8", errors="ignore") as LOG_PACT:
        LOG_PACT.write(log_message)


def pact_ignore_update(plugin: str, game: str) -> None:
    ignore_list = yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{game}") or []
    ignore_list.append(plugin)
    yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{game}", ignore_list)
# =================== WARNING MESSAGES ==================
# Can change first line to """\ to remove the spacing.

PAUSE_MESSAGE = "Press Enter to continue..."

# =================== UPDATE FUNCTION ===================


def pact_update_check() -> bool:
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
print(f"Hello World! | Plugin Auto Cleaning Tool (PACT) | Version {yaml_settings('PACT Data/PACT Main.yaml', 'PACT_Data.version')!s} | FO3, FNV, FO4, SSE")
print("MAKE SURE TO SET THE CORRECT LOAD ORDER AND XEDIT PATHS BEFORE CLEANING PLUGINS")
print("===============================================================================")


@dataclass
class Info:
    MO2_EXE: str | Path = field(default_factory=Path)
    MO2_PATH: str | Path = field(default_factory=Path)
    XEDIT_EXE: str | Path = field(default_factory=Path)
    XEDIT_PATH: str | Path = field(default_factory=Path)
    LOAD_ORDER_TXT: str | Path = field(default_factory=Path)
    LOAD_ORDER_PATH: str | Path = field(default_factory=Path)
    Journal_Expiration = 7
    Cleaning_Timeout = 300

    MO2Mode = False
    xedit_list_fallout3 = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO3") or []
    lower_fo3 = set(map(str.lower, xedit_list_fallout3)) or set()
    xedit_list_newvegas = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FNV") or []
    lower_fnv = set(map(str.lower, xedit_list_newvegas)) or set()
    xedit_list_fallout4 = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO4") or []
    xedit_list_fallout4.extend(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.FO4VR") or [])
    lower_fo4: ClassVar[set[str]] = set(map(str.lower, xedit_list_fallout4))
    xedit_list_skyrimse = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.SSE") or []
    skyrimvr_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.SkyrimVR") or []
    xedit_list_skyrimse.extend(skyrimvr_list)
    lower_sse: ClassVar[set[str]] = set(map(str.lower, xedit_list_skyrimse))
    xedit_list_universal = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.XEdit_Lists.Universal")
    xedit_list_specific = xedit_list_fallout3 + xedit_list_newvegas + xedit_list_fallout4 + xedit_list_skyrimse

    lower_specific: ClassVar[set[str]] = set(map(str.lower, xedit_list_specific))
    lower_universal: ClassVar[set[str]] = set(map(str.lower, xedit_list_universal or []))

    clean_results_UDR: set[str] = field(default_factory=set)  # Undisabled References
    clean_results_ITM: set[str] = field(default_factory=set)  # Identical To Master
    clean_results_NVM: set[str] = field(default_factory=set)  # Deleted Navmeshes
    clean_results_PARTIAL_FORMS: set[str] = field(default_factory=set)  # Partial Forms
    clean_failed_list: set[str] = field(default_factory=set)  # Cleaning Failed
    plugins_processed = 0
    plugins_cleaned = 0

    LCL_skip_list: list[str] = field(default_factory=list)

    # HARD EXCLUDE PLUGINS PER GAME HERE
    FO3_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO3")

    FNV_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FNV")

    FO4_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.FO4")

    SSE_skip_list = yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Skip_Lists.SSE")

    VIP_skip_list = (FO3_skip_list or []) + (FNV_skip_list or []) + (FO4_skip_list or []) + (SSE_skip_list or [])

    XEDIT_LOG_TXT: str = field(default_factory=str)
    XEDIT_EXC_LOG: str = field(default_factory=str)


info = Info()


def update_load_order_path(info: Info, load_order_path: str | Path) -> None:
    info.LOAD_ORDER_PATH = load_order_path
    if load_order_path is not None:
        info.LOAD_ORDER_TXT = Path(load_order_path).name
    else:
        info.LOAD_ORDER_TXT = ""


def update_xedit_path(info: Info, xedit_path: str | Path) -> None:
    info.XEDIT_PATH = xedit_path
    if xedit_path is not None:
        if ".exe" in str(xedit_path):
            info.XEDIT_EXE = Path(xedit_path).name
        elif Path(xedit_path).exists():
            for file in os.listdir(xedit_path):
                if file.endswith(".exe") and is_it_xedit(str(file).lower(), info):
                    info.XEDIT_PATH = Path(xedit_path) / file
                    info.XEDIT_EXE = Path(info.XEDIT_PATH).name
    else:
        info.XEDIT_EXE = ""
        info.XEDIT_PATH = ""


def update_mo2_path(info: Info, mo2_path: str | Path) -> None:
    if mo2_path is not None:
        info.MO2_PATH = mo2_path
        if ".exe" in str(mo2_path):
            info.MO2_EXE = Path(mo2_path).name
        elif Path(mo2_path).exists():
            for file in os.listdir(mo2_path):
                if file.endswith(".exe") and ("mod" in str(file).lower() or "mo2" in str(file).lower()):
                    info.MO2_PATH = Path(mo2_path) / file
                    info.MO2_EXE = Path(info.MO2_PATH).name
    else:
        info.MO2_EXE = ""
        info.MO2_PATH = ""


def pact_update_settings(info: Info) -> None:
    update_load_order_path(info, pact_settings("LoadOrder TXT"))
    update_xedit_path(info, pact_settings("XEDIT EXE"))
    update_mo2_path(info, pact_settings("MO2 EXE"))
    cleaning_timeout = pact_settings("Cleaning Timeout")
    if cleaning_timeout is not None:
        info.Cleaning_Timeout = int(cleaning_timeout)
    else:
        raise ValueError("❌ ERROR: Cleaning Timeout setting is missing or invalid.")
    journal_expiration = pact_settings("Journal Expiration")
    if journal_expiration is not None:
        info.Journal_Expiration = int(journal_expiration)
    else:
        raise ValueError("❌ ERROR: Journal Expiration setting is missing or invalid.")

    if not isinstance(info.Cleaning_Timeout, int) or info.Cleaning_Timeout <= 0:
        raise ValueError("""❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Cleaning Timeout to a valid positive number.""")
    elif info.Cleaning_Timeout < 30:  # noqa: RET506
        raise ValueError("""❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS TOO SMALL.)
Cleaning Timeout must be set to at least 30 seconds or more.""")

    if not isinstance(info.Journal_Expiration, int) or info.Journal_Expiration <= 0:
        raise ValueError("""❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS NOT VALID.)
Please change Journal Expiration to a valid positive number.""")
    elif info.Journal_Expiration < 1:  # noqa: RET506
        raise ValueError("""❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS TOO SMALL.)
Journal Expiration must be set to at least 1 day or more.""")


pact_update_settings(info)
if ".exe" in str(info.XEDIT_PATH) and info.XEDIT_EXE in info.xedit_list_specific:
    xedit_path = Path(info.XEDIT_PATH)
    info.XEDIT_LOG_TXT = str(xedit_path.with_name(xedit_path.stem.upper() + '_log.txt'))
    info.XEDIT_EXC_LOG = str(xedit_path.with_name(xedit_path.stem.upper() + 'Exception.log'))
elif info.XEDIT_PATH and ".exe" not in str(info.XEDIT_PATH):
    print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_XEDIT_File"))
    input(PAUSE_MESSAGE)
    raise ValueError


# Make sure Mod Organizer 2 is not already running.
def check_process_mo2(progress_emitter: ProgressEmitter) -> bool:
    pact_update_settings(info)
    if Path(info.MO2_PATH).exists():
        mo2_procs = [proc for proc in psutil.process_iter(attrs=['pid', 'name']) if str(info.MO2_EXE).lower() in proc.name().lower()]
        for proc in mo2_procs:
            if str(info.MO2_EXE).lower() in proc.name().lower():
                print("""❌ ERROR : CANNOT START PACT WHILE MOD ORGANIZER 2 IS ALREADY RUNNING!
PLEASE CLOSE MO2 AND RUN PACT AGAIN! (DO NOT RUN PACT THROUGH MO2)""")
                progress_emitter.report_done()
                return True
    return False


# Clear xedit log files to check them for each plugin separately.
def clear_xedit_logs() -> None:
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
        "Skyrim.esm": info.lower_sse
    }

    if str(info.XEDIT_EXE).lower() not in info.lower_universal:
        with Path(info.LOAD_ORDER_PATH).open(encoding="utf-8", errors="ignore") as LO_Check:
            LO_Plugins = LO_Check.read()
            if not any(game in LO_Plugins and str(info.XEDIT_EXE).lower() in executables for game, executables in valid_xedit_executables.items()):
                print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Warnings.Invalid_INI_Setup"))
                input(PAUSE_MESSAGE)
                raise ValueError
    elif "loadorder" not in str(info.LOAD_ORDER_PATH) and str(info.XEDIT_EXE).lower() in info.lower_universal:
        print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_LO_File"))
        input(PAUSE_MESSAGE)
        raise ValueError


def update_log_paths(info: Info, game_mode: str | None = None) -> None:
    path = Path(info.XEDIT_PATH)
    if game_mode:
        info.XEDIT_LOG_TXT = str(path.with_name(f"{game_mode.upper()}Edit_log.txt"))
        info.XEDIT_EXC_LOG = str(path.with_name(f"{game_mode.upper()}EditException.log"))
    else:
        info.XEDIT_LOG_TXT = str(path.with_name(f"{path.stem.upper()}_log.txt"))
        info.XEDIT_EXC_LOG = str(path.with_name(f"{path.stem.upper()}Exception.log"))

    # Additional helper functions

def create_xedit_command(info: Info, plugin_name: str, universal: bool, game_mode: str | None = None) -> str | None:
    commandline=""
    match info.MO2Mode, universal:
        case True, True:
            commandline = f'"{info.MO2_PATH}" run "{info.XEDIT_PATH}" -a "-{game_mode} -QAC -autoexit -autoload \\"{plugin_name}\\""'
        case True, False:
            commandline = f'"{info.MO2_PATH}" run "{info.XEDIT_PATH}" -a "-QAC -autoexit -autoload \\"{plugin_name}\\""'
        case False, True:
            commandline = f'"{info.XEDIT_PATH}" -a -{game_mode} -QAC -autoexit -autoload "{plugin_name}"'
        case False, False:
            commandline = f'"{info.XEDIT_PATH}" -a -QAC -autoexit -autoload "{plugin_name}"'
        case _:
            print("Invalid xedit executable specified")

    if commandline:
        return commandline.replace("-QAC", "-iknowwhatimdoing -QAC -allowmakepartial") if pact_settings("Partial Forms") else commandline
    else:  # noqa: RET505
        print("Invalid xedit executable specified")
        return None


def get_game_mode(info: Info) -> str:
    # Read the load order file line by line to determine the game mode
    try:
        with Path(info.LOAD_ORDER_PATH).open(encoding="utf-8", errors="ignore") as LO_Check:
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
        print(f"Load order file not found: {info.LOAD_ORDER_PATH}")
        raise
    except Exception as e:
        print(f"Error reading load order file: {info.LOAD_ORDER_PATH}, error: {e!s}")
        raise
    else:
        raise ValueError("❌ ERROR: UNABLE TO DETERMINE GAME MODE!")


def check_cpu_usage(proc: psutil.Process) -> bool | None:
    """
    Checks the CPU usage of a process.

    If CPU usage is below 1% after an interval of 5 seconds, returns True, indicating a likely error.

    Args:
        proc (psutil.Process): The process to check.

    Returns:
        bool: True if CPU usage is low, False otherwise.
    """
    """proc.is_running() and (proc.cpu_percent(interval=5) < 1 or proc.status() == psutil.STATUS_ZOMBIE or proc.status() == psutil.STATUS_DEAD):
        return True
    return False"""
    try:
        return proc.is_running() and (proc.cpu_percent(interval=5) < 1 or proc.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD})
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, subprocess.CalledProcessError):
        return False


def check_process_timeout(proc: psutil.Process, info: Info) -> bool:
    """
    Checks if a process has run longer than a specified timeout.

    Args:
        proc (psutil.Process): The process to check.
        info (Info): An object containing the timeout value.

    Returns:
        bool: True if the process has run longer than the timeout, False otherwise.
    """
    create_time = proc.create_time()
    return (time.time() - create_time) > info.Cleaning_Timeout


def check_process_exceptions(info: Info) -> bool:
    """
    Checks a process for exceptions.

    Args:
        info (Info): An object containing the path to the exception log.

    Returns:
        bool: True if exceptions were found, False otherwise.
    """
    if Path(info.XEDIT_EXC_LOG).exists():
        xedit_exc_out = subprocess.check_output(['powershell', '-command', f'Get-Content {info.XEDIT_EXC_LOG}'])
        Exception_Check = xedit_exc_out.decode()
        if "which can not be found" in Exception_Check or "which it does not have" in Exception_Check:
            return True
    return False


def handle_error(proc: psutil.Process, plugin_name: str, info: Info, error_message: str, add_ignore: bool = True) -> None:
    """
    Handles an error case.

    Kills the process, clears logs, and updates relevant info.

    Args:
        proc (psutil.Process): The process to kill.
        plugin_name (str): The name of the plugin being processed.
        info (Info): An object containing relevant information.
        error_message (str): The error message to print.
        add_ignore (bool, str): Whether or not to add the plugin to the ignore list. Defaults to True.
    """
    try:
        proc.kill()
    except (PermissionError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, subprocess.CalledProcessError):
        pass
    finally:
        time.sleep(1)
        if not pact_settings("Debug Mode"):
            clear_xedit_logs()
        info.plugins_processed -= 1
        if isinstance(info.clean_failed_list, set):
            info.clean_failed_list.add(plugin_name)
        else:
            info.clean_failed_list.append(plugin_name)
        print(error_message)
        if add_ignore:
            pact_ignore_update(plugin_name, get_game_mode(info).upper())

def create_bat_command(info: Info, plugin_name: str) -> str | None:
    xedit_exe_lower = str(info.XEDIT_EXE).lower()
    str(info.XEDIT_PATH)

    if xedit_exe_lower in info.lower_specific:
        update_log_paths(info)
        bat_command = create_xedit_command(info, plugin_name, False)
        if bat_command:
            return bat_command

    if "loadorder" in str(info.LOAD_ORDER_PATH).lower() and xedit_exe_lower in info.lower_universal:
        game_mode = get_game_mode(info)
        if game_mode is None:
            print(yaml_settings("PACT Data/PACT Main.yaml", "PACT_Data.Errors.Invalid_LO_File"))
            input(PAUSE_MESSAGE)
            raise ValueError

        update_log_paths(info, game_mode)
        bat_command = create_xedit_command(info, plugin_name, True, game_mode)

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
    Runs the automatic cleaning process.

    Args:
        plugin_name (str): The name of the plugin to clean.
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
    Monitors the cleaning process for errors.

    Args:
        proc (subprocess.Popen): The subprocess to monitor.
        plugin_name (str): The name of the plugin being cleaned.
    """
    while proc.poll() is None:
        xedit_procs = [p for p in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'create_time']) if is_it_xedit(p.name().lower(), info)]
        for p in xedit_procs:
            if p.name().lower() == str(info.XEDIT_EXE).lower():
                # Check for low CPU usage (indicative of an error)
                if check_cpu_usage(p):
                    handle_error(p, plugin_name, info, "❌ ERROR : PLUGIN IS DISABLED OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...")
                    pact_log_update(f"{plugin_name} -> Disabled or missing requirements")
                    break
                # Check for process running longer than specified timeout
                if check_process_timeout(p, info):
                    handle_error(p, plugin_name, info, "❌ ERROR : XEDIT TIMED OUT (CLEANING PROCESS TOOK TOO LONG)! KILLING XEDIT...", add_ignore=False)
                    pact_log_update(f"{plugin_name} -> XEdit timed out")
                    break
                # Check for exceptions in process
                if check_process_exceptions(info):
                    handle_error(p, plugin_name, info, "❌ ERROR : PLUGIN IS EMPTY OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...")
                    pact_log_update(f"{plugin_name} -> Empty or missing requirements")
                    break
        time.sleep(3)


# Compile the patterns outside the function
udr_pattern = re.compile(r"Undeleting:\s*(.*)")
itm_pattern = re.compile(r"Removing:\s*(.*)")
nvm_pattern = re.compile(r"Skipping:\s*(.*)")
partial_form_pattern = re.compile(r"Making Partial Form:\s*(.*)")

def check_cleaning_results(plugin_name: str) -> None:
    time.sleep(1)  # Wait to make sure xedit generates the logs.
    if Path(info.XEDIT_LOG_TXT).exists():
        cleaned_something = False
        with Path(info.XEDIT_LOG_TXT).open(encoding="utf-8", errors="ignore") as XE_Check:
            # Define the patterns and associated actions
            patterns = {
                udr_pattern: ("Cleaned UDRs", info.clean_results_UDR),
                itm_pattern: ("Cleaned ITMs", info.clean_results_ITM),
                nvm_pattern: ("Found Deleted Navmeshes", info.clean_results_NVM),
                partial_form_pattern: ("Created Partial Forms", info.clean_results_PARTIAL_FORMS)
            }
            for line in XE_Check:
                for pattern, (message, results_list) in patterns.items():
                    if pattern.search(line):
                        pact_log_update(f"\n{plugin_name} -> {message}")
                        results_list.add(plugin_name)
                        cleaned_something = True
            if cleaned_something:
                info.plugins_cleaned += 1
            else:
                pact_log_update(f"\n{plugin_name} -> NOTHING TO CLEAN")
                print("NOTHING TO CLEAN ! Adding plugin to PACT Ignore file...")
                pact_ignore_update(plugin_name, get_game_mode(info).upper())
                info.LCL_skip_list.append(plugin_name)
        if not pact_settings("Debug Mode"):
            clear_xedit_logs()


def get_plugin_list(load_order_path: str) -> list[str]:
    with Path(load_order_path).open(encoding="utf-8", errors="ignore") as lo_file:
        next(lo_file)  # Skip the first line
        if "plugins.txt" in load_order_path:
            plugin_list = [line.strip().replace("*", "") for line in lo_file if "*" in line.strip()]
        else:
            plugin_list = [line.strip() for line in lo_file if ".ghost" not in line]
    return plugin_list


def clean_plugin(plugin: str) -> None:
    run_auto_cleaning(plugin)
    check_cleaning_results(plugin)


def init_plugins_info() -> tuple[list[str], int, list[str]]:
    ALL_skip_list = info.VIP_skip_list + info.LCL_skip_list
    plugin_list = get_plugin_list(str(info.LOAD_ORDER_PATH))
    count_plugins = len(set(plugin_list) - set(ALL_skip_list))
    return plugin_list, count_plugins, ALL_skip_list


class ProgressEmitter(QObject):  # type: ignore
    progress = Signal(int)
    max_value = Signal(int)
    plugin_value = Signal(str)
    done = Signal()
    visible = Signal(bool)
    is_done = False

    def report_max_value(self) -> None:
        count = init_plugins_info()[1]
        self.max_value.emit(count)

    def report_progress(self, count: int) -> None:
        self.progress.emit(count)

    def report_plugin(self, plugin: str) -> None:
        self.plugin_value.emit(f"Cleaning {plugin} %v/%m - %p%")

    def report_done(self) -> None:
        self.done.emit()
        self.is_done = True

    def set_visible(self) -> None:
        self.visible.emit(True)


def clean_plugins(progress_emitter: ProgressEmitter) -> None:
    progress_emitter.is_done = False
    print(f"❓ LOAD ORDER TXT is set to : {info.LOAD_ORDER_PATH}")
    print(f"❓ XEDIT EXE is set to : {info.XEDIT_PATH}")
    print(f"❓ MO2 EXE is set to : {info.MO2_PATH}")

    if info.MO2Mode:
        print("✔️ MO2 EXECUTABLE WAS FOUND! SWITCHING TO MOD ORGANIZER 2 MODE...")
    else:
        print("❌ MO2 EXECUTABLE NOT SET OR FOUND. SWITCHING TO VORTEX MODE...")

    ignore_list = yaml_settings("PACT Ignore.yaml", f"PACT_Ignore_{get_game_mode(info).upper()}")
    if ignore_list:
        info.LCL_skip_list.extend(ignore_list)

    plugin_list, plugin_count, ALL_skip_list = init_plugins_info()
    progress_emitter.report_max_value()
    progress_emitter.set_visible()

    print(f"✔️ CLEANING STARTED... ( PLUGINS TO CLEAN: {plugin_count} )")
    log_start = time.perf_counter()
    log_time = datetime.datetime.now()
    pact_journal_expire()
    pact_log_update(f"\nSTARTED CLEANING PROCESS AT : {log_time}")
    count_cleaned = 0

    for plugin in plugin_list:
        if not any(plugin in elem for elem in ALL_skip_list) and re.search(r"(?:.+?)(?:\.(?:esl|esm|esp)+)$", plugin, re.IGNORECASE):
            progress_emitter.report_plugin(plugin)
            clean_plugin(plugin)
            count_cleaned += 1
            print(f"Finished cleaning : {plugin} ({count_cleaned} / {plugin_count})")
            progress_emitter.report_progress(count_cleaned)
    completion_time = (str(time.perf_counter() - log_start))[:3]
    pact_log_update(f"\n✔️ CLEANING COMPLETE! {info.XEDIT_EXE} processed all available plugins in {completion_time} seconds.")
    pact_log_update(f"\n   {info.XEDIT_EXE} successfully processed {info.plugins_processed} plugins and cleaned {info.plugins_cleaned} of them.\n")

    print(f"\n✔️ CLEANING COMPLETE! {info.XEDIT_EXE} processed all available plugins in {completion_time} seconds.")
    print(f"\n   {info.XEDIT_EXE} successfully processed {info.plugins_processed} plugins and cleaned {info.plugins_cleaned} of them.\n")

    for plugins, message in [(info.clean_failed_list, "❌ {0} WAS UNABLE TO CLEAN THESE PLUGINS: (Invalid Plugin Name or {0} Timed Out):"),
                             (info.clean_results_UDR, "✔️ The following plugins had Undisabled Records and {0} properly disabled them:"),
                             (info.clean_results_ITM, "✔️ The following plugins had Identical To Master Records and {0} successfully cleaned them:"),
                             (info.clean_results_NVM, "❌ CAUTION : The following plugins contain Deleted Navmeshes!\n   Such plugins may cause navmesh related problems or crashes."),
                             (info.clean_results_PARTIAL_FORMS, f"✔️ The following plugins had ITMs converted to Partial Forms {0}:")]:
        if len(plugins) > 0:
            print(f"\n{message.format(info.XEDIT_EXE)}")
            for plugin in plugins:
                print(plugin)

    progress_emitter.report_done()


if __name__ == "__main__":
    input("This is not the main file. Press Enter to exit...")
    raise SystemExit  # This is basically what sys.exit() does, but without having to import sys
