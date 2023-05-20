# PLUGIN AUTO CLEANING TOOL (PACT) | By Poet (The Sound Of Snow)
import configparser
import datetime
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import psutil
import requests
import tomlkit

'''AUTHOR NOTES (POET)
- Comments marked as RESERVED in all scripts are intended for future updates or tests, do not edit / move / remove.
- (..., encoding="utf-8", errors="ignore") needs to go with every opened file because unicode errors are a bitch.
'''


# =================== PACT INI FILE ===================
def pact_ini_create():
    if not os.path.exists("PACT Settings.toml"):
        INI_Settings = """[MAIN]
# This file contains settings for both source scripts and Plugin Auto Cleaning Tool.exe 
# Set to true if you want PACT to check that you have the latest version of PACT. 
Update_Check = true

# Set to true if you want PACT to show extra stats about cleaned plugins in the command line window. 
Stat_Logging = true

# In seconds, set below how long should PACT wait for xedit to clean any plugin. 
# If it takes longer than the set amount, the plugin will be immediately skipped. 
Cleaning_Timeout = 300

# In days, set below how long should PACT wait until the logging journal is cleared. 
# If PACT Journal.txt is older than the set amount, it is immediately deleted. 
Journal_Expiration = 7

# Set or copy-paste your load order (loadorder.txt / plugins.txt) file path below. 
# See the PACT Nexus Page for instructions on where you can find these files. 
LoadOrder_TXT = ""

# Set or copy-paste your XEdit (FNVEdit.exe / FO4Edit.exe / SSEEdit.exe) executable file path below. 
# xEdit.exe is also supported, but requires that you set LoadOrder TXT path to loadorder.txt only. 
XEDIT_EXE = ""

# Set or copy-paste your MO2 (ModOrganizer.exe) executable file path below. 
# Required if MO2 is your main mod manager. Otherwise, leave this blank. 
MO2_EXE = ""
"""
        with open("PACT Settings.toml", "w", encoding="utf-8", errors="ignore") as INI_PACT:
            INI_PACT.write(INI_Settings)


pact_ini_create()
# Use optionxform = str to preserve INI formatting. | Set comment_prefixes to unused char to keep INI comments.
"""PACT_config = configparser.ConfigParser(allow_no_value=True, comment_prefixes="$")
PACT_config.optionxform = str  # type: ignore
PACT_config.read("PACT Settings.ini")"""
with open("PACT Settings.toml", "r", encoding="utf-8", errors="ignore") as INI_PACT:
    PACT_config: tomlkit.TOMLDocument = tomlkit.parse(INI_PACT.read())  # type: ignore
PACT_Date = "140423"  # DDMMYY
PACT_Current = "PACT v1.80"
PACT_Updated = False


def pact_ini_update(section: str, value: Union[str, int, float, bool]):  # Convenience function for checking & writing to INI.
    if " " in section:
        raise ValueError
    
    PACT_config["MAIN"][section] = value # type: ignore

    with open("PACT Settings.toml", "w+", encoding="utf-8", errors="ignore") as INI_PACT:
        tomlkit.dump(PACT_config, INI_PACT)


def pact_log_update(log_message):
    with open("PACT Journal.log", "a", encoding="utf-8", errors="ignore") as LOG_PACT:
        LOG_PACT.write(log_message)

    # Delete journal if older than set amount of days.
    PACT_folder = os.getcwd()
    journal_name = "PACT Journal.log"
    journal_path = os.path.join(PACT_folder, journal_name)
    journal_age = time.time() - os.path.getmtime(journal_path)
    journal_age_days = journal_age / (24 * 3600)
    if journal_age_days > info.Journal_Expiration:
        os.remove(journal_path)


def pact_ignore_update(plugin, numnewlines=2):
    with open("PACT Ignore.txt", "a", encoding="utf-8", errors="ignore") as IGNORE_PACT:
        if numnewlines == 0:
            IGNORE_PACT.write(plugin)
        elif numnewlines == 1:
            IGNORE_PACT.write(plugin + "\n")
        elif numnewlines == 2:
            IGNORE_PACT.write("\n" + plugin + "\n")
        else:
            raise ValueError("Invalid number of newlines for PACT Ignore.txt")
# =================== WARNING MESSAGES ==================
# Can change first line to """\ to remove the spacing.


Warn_PACT_Update_Failed = """
❌  WARNING : PACT WAS UNABLE TO CHECK FOR UPDATES, BUT WILL CONTINUE RUNNING
    CHECK FOR ANY PACT UPDATES HERE: https://www.nexusmods.com/fallout4/mods/69413
"""
Warn_Outdated_PACT = """
❌  WARNING : YOUR PACT VERSION IS OUT OF DATE!
    Please download the latest version from here:
    https://www.nexusmods.com/fallout4/mods/69413
"""
Warn_Invalid_INI_Path = """
❌  WARNING : YOUR PACT INI PATHS ARE INCORRECT!
    Please run the PACT program or open PACT Settings.ini
    And make sure that file / folder paths are correctly set!
"""
Warn_Invalid_INI_Setup = """
❌  WARNING : YOUR PACT INI SETUP IS INCORRECT!
    You likely set the wrong XEdit version for your game.
    Check your EXE or PACT Settings.ini settings and try again.
"""
Err_Invalid_LO_File = """
❌ ERROR : CANNOT PROCESS LOAD ORDER FILE FOR XEDIT IN THIS SITUATION!
   You have to set your load order file path to loadorder.txt and NOT plugins.txt
   This is so PACT can detect the right game. Change the load order file path and try again.
"""
Err_Invalid_XEDIT_File = """
❌ ERROR : CANNOT DETERMINE THE SET XEDIT EXECUTABLE FROM PACT SETTINGS!
   Make sure that you have set XEDIT EXE path to a valid .exe file!
   OR try changing XEDIT EXE path to a different XEdit version.
"""


# =================== UPDATE FUNCTION ===================
def pact_update_check():
    if PACT_config["MAIN"]["Update_Check"] is True: # type: ignore
        print("❓ CHECKING FOR ANY NEW PLUGIN AUTO CLEANING TOOL (PACT) UPDATES...")
        print("   (You can disable this check in the EXE or PACT Settings.ini) \n")
        try:
            response = requests.get("https://api.github.com/repos/GuidanceOfGrace/XEdit-PACT/releases/latest")  # type: ignore
            PACT_Received = response.json()["name"]
            if PACT_Received == PACT_Current:
                print("\n✔️ You have the latest version of PACT!")
                return True
            else:
                print(Warn_Outdated_PACT)
                print("===============================================================================")
        except (OSError, requests.exceptions.RequestException):
            print(Warn_PACT_Update_Failed)
            print("===============================================================================")
    else:
        print("\n ❌ NOTICE: UPDATE CHECK IS DISABLED IN PACT INI SETTINGS \n")
        print("===============================================================================")
    return False


# =================== TERMINAL OUTPUT START ====================
print("Hello World! | Plugin Auto Cleaning Tool (PACT) | Version", PACT_Current[-4:], "| FNV, FO4, SSE")
print("MAKE SURE TO SET THE CORRECT LOAD ORDER AND XEDIT PATHS BEFORE CLEANING PLUGINS")
print("===============================================================================")


@dataclass
class Info:
    MO2_EXE: Union[str, Path] = field(default_factory=Path)
    MO2_PATH: Union[str, Path] = field(default_factory=Path)
    XEDIT_EXE: Union[str, Path] = field(default_factory=Path)
    XEDIT_PATH: Union[str, Path] = field(default_factory=Path)
    LOAD_ORDER_TXT: Union[str, Path] = field(default_factory=Path)
    LOAD_ORDER_PATH: Union[str, Path] = field(default_factory=Path)
    Journal_Expiration = 7
    Cleaning_Timeout = 300

    MO2Mode = False
    xedit_list_newvegas = ("fnvedit.exe", "fnvedit64.exe")
    xedit_list_fallout4 = ("fo4edit.exe", "fo4edit64.exe", "fo4vredit.exe")
    xedit_list_skyrimse = ("sseedit.exe", "sseedit64.exe", "tes5vredit.exe")
    xedit_list_universal = ("xedit.exe", "xedit64.exe", "xfoedit.exe", "xfoedit64.exe")
    xedit_list_specific = xedit_list_newvegas + xedit_list_fallout4 + xedit_list_skyrimse

    clean_results_UDR = []  # Undisabled References
    clean_results_ITM = []  # Identical To Master
    clean_results_NVM = []  # Deleted Navmeshes
    clean_failed_list = []  # Cleaning Failed
    plugins_processed = 0
    plugins_cleaned = 0

    LCL_skip_list = []
    if not os.path.exists("PACT Ignore.txt"):  # Local plugin skip / ignore list.
        pact_ignore_update("Write plugin names you want PACT to ignore here. (ONE PLUGIN PER LINE)", numnewlines=1)
    else:
        with open("PACT Ignore.txt", "r", encoding="utf-8", errors="ignore") as PACT_Ignore:
            LCL_skip_list = [line.strip() for line in PACT_Ignore.readlines()[1:]]

    # HARD EXCLUDE PLUGINS PER GAME HERE
    FNV_skip_list = ["", "FalloutNV.esm", "DeadMoney.esm", "OldWorldBlues.esm", "HonestHearts.esm", "LonesomeRoad.esm", "TribalPack.esm", "MercenaryPack.esm",
                     "ClassicPack.esm", "CaravanPack.esm", "GunRunnersArsenal.esm", "Unofficial Patch NVSE Plus.esp"]

    FO4_skip_list = ["", "Fallout4.esm", "DLCCoast.esm", "DLCNukaWorld.esm", "DLCRobot.esm", "DLCworkshop01.esm", "DLCworkshop02.esm", "DLCworkshop03.esm",
                     "Unofficial Fallout 4 Patch.esp", "PPF.esm", "PRP.esp", "PRP-Compat", "SS2.esm", "SS2_XPAC_Chapter2.esm"]

    SSE_skip_list = ["", "Skyrim.esm", "Update.esm", "HearthFires.esm", "Dragonborn.esm", "Dawnguard.esm", "Unofficial Skyrim Special Edition Patch.esp"]

    VIP_skip_list = FNV_skip_list + FO4_skip_list + SSE_skip_list

    XEDIT_LOG_TXT: str = field(default_factory=str)
    XEDIT_EXC_LOG: str = field(default_factory=str)


info = Info()


def pact_update_settings():
    info.LOAD_ORDER_PATH = PACT_config["MAIN"]["LoadOrder_TXT"]  # type: ignore
    info.LOAD_ORDER_TXT = os.path.basename(info.LOAD_ORDER_PATH) # type: ignore
    info.XEDIT_PATH = PACT_config["MAIN"]["XEDIT_EXE"]  # type: ignore
    info.MO2_PATH = PACT_config["MAIN"]["MO2_EXE"]  # type: ignore
    info.Cleaning_Timeout = int(PACT_config["MAIN"]["Cleaning_Timeout"])  # type: ignore
    info.Journal_Expiration = int(PACT_config["MAIN"]["Journal_Expiration"])  # type: ignore

    if info.XEDIT_PATH and ".exe" in info.XEDIT_PATH: # type: ignore
        info.XEDIT_EXE = os.path.basename(info.XEDIT_PATH) # type: ignore
    elif info.XEDIT_PATH and os.path.exists(info.XEDIT_PATH): # type: ignore
        for file in os.listdir(info.XEDIT_PATH): # type: ignore
            if file.endswith(".exe") and "edit" in str(file).lower():
                info.XEDIT_PATH = os.path.join(info.XEDIT_PATH, file) # type: ignore
                info.XEDIT_EXE = os.path.basename(info.XEDIT_PATH)

    if ".exe" in info.MO2_PATH: # type: ignore
        info.MO2_EXE = os.path.basename(info.MO2_PATH) # type: ignore
    elif os.path.exists(info.MO2_PATH): # type: ignore
        for file in os.listdir(info.MO2_PATH): # type: ignore
            if file.endswith(".exe") and ("mod" in str(file).lower() or "mo2" in str(file).lower()):
                info.MO2_PATH = os.path.join(info.MO2_PATH, file) # type: ignore
                info.MO2_EXE = os.path.basename(info.MO2_PATH)

    if not isinstance(info.Cleaning_Timeout, int):
        print("❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS NOT VALID.")
        print("   Please change Cleaning Timeout to a valid positive number.")
        os.system("pause")
        sys.exit()
    elif info.Cleaning_Timeout < 30:
        print("❌ ERROR : CLEANING TIMEOUT VALUE IN PACT SETTINGS IS TOO SMALL.")
        print("   Cleaning Timeout must be set to at least 30 seconds or more.")
        os.system("pause")
        sys.exit()

    if not isinstance(info.Journal_Expiration, int):
        print("❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS NOT VALID.")
        print("   Please change Journal Expiration to a valid positive number.")
        os.system("pause")
        sys.exit()
    elif info.Journal_Expiration < 1:
        print("❌ ERROR : JOURNAL EXPIRATION VALUE IN PACT SETTINGS IS TOO SMALL.")
        print("   Journal Expiration must be set to at least 1 day or more.")
        os.system("pause")
        sys.exit()


pact_update_settings()
if ".exe" in info.XEDIT_PATH:  # type: ignore
    info.XEDIT_LOG_TXT = str(info.XEDIT_PATH).replace('.exe', '_log.txt')
    info.XEDIT_EXC_LOG = str(info.XEDIT_PATH).replace('.exe', 'Exception.log')
elif info.XEDIT_PATH and not ".exe" in info.XEDIT_PATH:  # type: ignore
    print(Err_Invalid_XEDIT_File)
    os.system("pause")
    sys.exit()


# Make sure Mod Organizer 2 is not already running.
def check_process_mo2():
    pact_update_settings()
    if os.path.exists(info.MO2_PATH):
        mo2_procs = [proc for proc in psutil.process_iter(attrs=['pid', 'name']) if str(info.MO2_EXE).lower() in proc.info['name'].lower()]  # type: ignore
        for proc in mo2_procs:
            if str(info.MO2_EXE).lower() in proc.info['name'].lower():  # type: ignore
                print("\n❌ ERROR : CANNOT START PACT WHILE MOD ORGANIZER 2 IS ALREADY RUNNING!")
                print("   PLEASE CLOSE MO2 AND RUN PACT AGAIN! (DO NOT RUN PACT THROUGH MO2)")
                os.system("pause")
                sys.exit()


# Clear xedit log files to check them for each plugin separately.
def clear_xedit_logs():
    try:
        if os.path.exists(info.XEDIT_LOG_TXT):
            os.remove(info.XEDIT_LOG_TXT)
        if os.path.exists(info.XEDIT_EXC_LOG):
            os.remove(info.XEDIT_EXC_LOG)
    except (PermissionError, OSError):
        print("❌ ERROR : CANNOT CLEAR XEDIT LOGS. Try running PACT in Admin Mode.")
        print("   If problems continue, please report this to the PACT Nexus page.")
        os.system("pause")
        sys.exit()


# Make sure right XEDIT is running for the right game.
def check_settings_integrity():
    pact_update_settings()
    if os.path.exists(info.LOAD_ORDER_PATH) and os.path.exists(info.XEDIT_PATH):
        print("✔️ REQUIRED FILE PATHS FOUND! CHECKING IF INI SETTINGS ARE CORRECT...")
    else:
        print(Warn_Invalid_INI_Path)
        os.system("pause")
        sys.exit()

    if os.path.exists(info.MO2_PATH):
        info.MO2Mode = True
    else:
        info.MO2Mode = False

    if str(info.XEDIT_EXE).lower() not in info.xedit_list_universal:
        with open(info.LOAD_ORDER_PATH, "r", encoding="utf-8", errors="ignore") as LO_Check:
            LO_Plugins = LO_Check.read()
            if "FalloutNV.esm" in LO_Plugins and str(info.XEDIT_EXE).lower() not in info.xedit_list_newvegas:
                print(Warn_Invalid_INI_Setup)
                os.system("pause")
                sys.exit()

            elif "Fallout4.esm" in LO_Plugins and str(info.XEDIT_EXE).lower() not in info.xedit_list_fallout4:
                print(Warn_Invalid_INI_Setup)
                os.system("pause")
                sys.exit()

            elif "Skyrim.esm" in LO_Plugins and str(info.XEDIT_EXE).lower() not in info.xedit_list_skyrimse:
                print(Warn_Invalid_INI_Setup)
                os.system("pause")
                sys.exit()
    elif "loadorder" not in str(info.LOAD_ORDER_PATH) and str(info.XEDIT_EXE).lower() in info.xedit_list_universal:
        print(Err_Invalid_LO_File)
        os.system("pause")
        sys.exit()


def create_bat_command(info, plugin_name):
    bat_command = ""
    if str(info.XEDIT_EXE).lower() in info.xedit_list_specific:
        info.XEDIT_LOG_TXT = str(info.XEDIT_PATH).replace('.exe', '_log.txt')
        info.XEDIT_EXC_LOG = str(info.XEDIT_PATH).replace('.exe', 'Exception.log')
    # If specific xedit (fnvedit, fo4edit, sseedit) executable is set.
    if info.MO2Mode and str(info.XEDIT_EXE).lower() in info.xedit_list_specific:
        bat_command = f'"{info.MO2_PATH}" run "{info.XEDIT_PATH}" -a "-QAC -autoexit -autoload \\"{plugin_name}\\""'

    elif not info.MO2Mode and str(info.XEDIT_EXE).lower() in info.xedit_list_specific:
        bat_command = f'"{info.XEDIT_PATH}" -a -QAC -autoexit -autoload "{plugin_name}"'

    # If universal xedit (xedit.exe) executable is set.
    if "loadorder" in str(info.LOAD_ORDER_PATH) and str(info.XEDIT_EXE).lower() in info.xedit_list_universal:
        game_mode = ""
        with open(info.LOAD_ORDER_PATH, "r", encoding="utf-8", errors="ignore") as LO_Check:
            mode_check = LO_Check.read()
            if "Skyrim.esm" in mode_check:
                game_mode = "-sse"
                info.XEDIT_LOG_TXT = str(Path(info.XEDIT_PATH).with_name("SSEEdit_log.txt"))
                info.XEDIT_EXC_LOG = str(Path(info.XEDIT_PATH).with_name("SSEEditException.log"))
            elif "FalloutNV.esm" in mode_check:
                game_mode = "-fnv"
                info.XEDIT_LOG_TXT = str(Path(info.XEDIT_PATH).with_name("FNVEdit_log.txt"))
                info.XEDIT_EXC_LOG = str(Path(info.XEDIT_PATH).with_name("FNVEditException.log"))
            elif "Fallout4.esm" in mode_check:
                game_mode = "-fo4"
                info.XEDIT_LOG_TXT = str(Path(info.XEDIT_PATH).with_name("FO4Edit_log.txt"))
                info.XEDIT_EXC_LOG = str(Path(info.XEDIT_PATH).with_name("FO4EditException.log"))

        if info.MO2Mode:
            bat_command = f'"{info.MO2_PATH}" run "{info.XEDIT_PATH}" -a "{game_mode} -QAC -autoexit -autoload \\"{plugin_name}\\""'
        else:
            bat_command = f'"{info.XEDIT_PATH}" -a {game_mode} -QAC -autoexit -autoload "{plugin_name}"'

    elif "loadorder" not in str(info.LOAD_ORDER_PATH).lower() and str(info.XEDIT_EXE).lower() in info.xedit_list_universal:
        print(Err_Invalid_LO_File)
        os.system("pause")
        sys.exit()

    if not bat_command:
        print("\n❓ ERROR : UNABLE TO START THE CLEANING PROCESS! WRONG INI SETTINGS OR FILE PATHS?")
        print("   If you're seeing this, make sure that your load order / xedit paths are correct.")
        print("   If problems continue, try a different load order file or xedit executable.")
        print("   If nothing works, please report this error to the PACT Nexus page.")
        os.system("pause")
        sys.exit()

    return bat_command


def check_cpu_usage(proc):
    """
    Checks the CPU usage of a process.

    If CPU usage is below 1% for 10 seconds, returns True, indicating a likely error. 

    Args:
        proc (psutil.Process): The process to check.

    Returns:
        bool: True if CPU usage is low, False otherwise.
    """
    time.sleep(5)
    try:
        if proc.is_running() and proc.cpu_percent() < 1:
            time.sleep(5)
            if proc.cpu_percent() < 1:
                return True
    except (PermissionError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, subprocess.CalledProcessError):
        pass
    return False


def check_process_timeout(proc, info):
    """
    Checks if a process has run longer than a specified timeout.

    Args:
        proc (psutil.Process): The process to check.
        info (Info): An object containing the timeout value.

    Returns:
        bool: True if the process has run longer than the timeout, False otherwise.
    """
    create_time = proc.info['create_time']
    if (time.time() - create_time) > info.Cleaning_Timeout:
        return True
    return False


def check_process_exceptions(info):
    """
    Checks a process for exceptions.

    Args:
        info (Info): An object containing the path to the exception log.

    Returns:
        bool: True if exceptions were found, False otherwise.
    """
    if os.path.exists(info.XEDIT_EXC_LOG):
        try:
            xedit_exc_out = subprocess.check_output(['powershell', '-command', f'Get-Content {info.XEDIT_EXC_LOG}'])
            Exception_Check = xedit_exc_out.decode()
            if "which can not be found" in Exception_Check or "which it does not have" in Exception_Check:
                return True
        except (PermissionError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, subprocess.CalledProcessError):
            pass
    return False


def handle_error(proc, plugin_name, info, error_message, add_ignore=True):
    """
    Handles an error case.

    Kills the process, clears logs, and updates relevant info.

    Args:
        proc (psutil.Process): The process to kill.
        plugin_name (str): The name of the plugin being processed.
        info (Info): An object containing relevant information.
        error_message (str): The error message to print.
    """
    proc.kill()
    time.sleep(1)
    clear_xedit_logs()
    info.plugins_processed -= 1
    info.clean_failed_list.append(plugin_name)
    print(error_message)
    if add_ignore:
        pact_ignore_update(plugin_name)


def run_auto_cleaning(plugin_name):
    """
    Runs the automatic cleaning process.

    Args:
        plugin_name (str): The name of the plugin to clean.
    """
    # Create command to run in subprocess
    bat_command = create_bat_command(info, plugin_name)

    # Clear logs and start subprocess
    clear_xedit_logs()
    print(f"\nCURRENTLY RUNNING : {bat_command}")
    bat_process = subprocess.Popen(bat_command)
    time.sleep(1)

    # Check subprocess for errors until it finishes
    while bat_process.poll() is None:
        xedit_procs = [proc for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'create_time']) if 'edit.exe' in proc.info['name'].lower()]  # type: ignore
        for proc in xedit_procs:
            if proc.info['name'].lower() == str(info.XEDIT_EXE).lower():  # type: ignore
                # Check for low CPU usage (indicative of an error)
                if check_cpu_usage(proc):
                    handle_error(proc, plugin_name, info, "❌ ERROR : PLUGIN IS DISABLED OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...")
                    break
                # Check for process running longer than specified timeout
                if check_process_timeout(proc, info):
                    handle_error(proc, plugin_name, info, "❌ ERROR : XEDIT TIMED OUT (CLEANING PROCESS TOOK TOO LONG)! KILLING XEDIT...", add_ignore=False)
                    break
                # Check for exceptions in process
                if check_process_exceptions(info):
                    handle_error(proc, plugin_name, info, "❌ ERROR : PLUGIN IS EMPTY OR HAS MISSING REQUIREMENTS! KILLING XEDIT AND ADDING PLUGIN TO IGNORE LIST...")
                    break
        time.sleep(3)
    # Increment processed plugins count
    info.plugins_processed += 1


def check_cleaning_results(plugin_name):
    time.sleep(1)  # Wait to make sure xedit generates the logs.
    if os.path.exists(info.XEDIT_LOG_TXT):
        cleaned_something = False
        with open(info.XEDIT_LOG_TXT, "r", encoding="utf-8", errors="ignore") as XE_Check:
            Cleaning_Check = XE_Check.read()
            if "Undeleting:" in Cleaning_Check:
                pact_log_update(f"\n{plugin_name} -> Cleaned UDRs")
                info.clean_results_UDR.append(plugin_name)
                cleaned_something = True
            if "Removing:" in Cleaning_Check:
                pact_log_update(f"\n{plugin_name} -> Cleaned ITMs")
                info.clean_results_ITM.append(plugin_name)
                cleaned_something = True
            if "Skipping:" in Cleaning_Check:
                pact_log_update(f"\n{plugin_name} -> Found Deleted Navmeshes")
                info.clean_results_NVM.append(plugin_name)
            if cleaned_something is True:
                info.plugins_cleaned += 1
            else:
                pact_log_update(f"\n{plugin_name} -> NOTHING TO CLEAN")
                print("NOTHING TO CLEAN ! Adding plugin to PACT Ignore file...")
                pact_ignore_update(f"\n{plugin_name}", numnewlines=0)
                info.LCL_skip_list.append(plugin_name)
        clear_xedit_logs()


def clean_plugins():
    ALL_skip_list = info.VIP_skip_list + info.LCL_skip_list

    print(f"❓ LOAD ORDER TXT is set to : {info.LOAD_ORDER_PATH}")
    print(f"❓ XEDIT EXE is set to : {info.XEDIT_PATH}")
    print(f"❓ MO2 EXE is set to : {info.MO2_PATH}")

    if info.MO2Mode:  # Change mod manager modes and check ignore list.
        print("✔️ MO2 EXECUTABLE WAS FOUND! SWITCHING TO MOD ORGANIZER 2 MODE...")
    else:
        print("❌ MO2 EXECUTABLE NOT SET OR FOUND. SWITCHING TO VORTEX MODE...")

    # Add plugins from loadorder or plugins file to separate plugin list.
    with open(info.LOAD_ORDER_PATH, "r", encoding="utf-8", errors="ignore") as LO_File:
        LO_File.seek(0)  # Return line pointer to first line.
        LO_Plugin_List = []
        LO_List = LO_File.readlines()[1:]
        if "plugins.txt" in info.LOAD_ORDER_PATH:  # type: ignore
            for line in LO_List:
                if "*" in line:
                    line = line.strip()
                    line = line.replace("*", "")
                    LO_Plugin_List.append(line)
        else:
            for line in LO_List:
                line = line.strip()
                if ".ghost" not in line:
                    LO_Plugin_List.append(line)

    # Start cleaning process if everything is OK.
    count_plugins = len(set(LO_Plugin_List) - set(ALL_skip_list))
    print(f"✔️ CLEANING STARTED... ( PLUGINS TO CLEAN: {count_plugins} )")
    log_start = time.perf_counter()
    log_time = datetime.datetime.now()
    pact_log_update(f"\nSTARTED CLEANING PROCESS AT : {log_time}")
    count_cleaned = 0
    for plugin in LO_Plugin_List:  # Run XEdit and log checks for each valid plugin in loadorder.txt file.
        if not any(plugin in elem for elem in ALL_skip_list) and any(ext in plugin.lower() for ext in ['.esl', '.esm', '.esp']):
            count_cleaned += 1
            run_auto_cleaning(plugin)
            check_cleaning_results(plugin)
            print(f"Finished cleaning : {plugin} ({count_cleaned} / {count_plugins})")

    # Show stats once cleaning is complete.
    pact_log_update(f"\n✔️ CLEANING COMPLETE! {info.XEDIT_EXE} processed all available plugins in {(str(time.perf_counter() - log_start)[:3])} seconds.")
    pact_log_update(f"\n   {info.XEDIT_EXE} successfully processed {info.plugins_processed} plugins and cleaned {info.plugins_cleaned} of them.\n")

    print(f"\n✔️ CLEANING COMPLETE! {info.XEDIT_EXE} processed all available plugins in", (str(time.perf_counter() - log_start)[:3]), "seconds.")
    print(f"\n   {info.XEDIT_EXE} successfully processed {info.plugins_processed} plugins and cleaned {info.plugins_cleaned} of them.\n")
    if len(info.clean_failed_list) > 1:
        print(f"\n❌ {str(info.XEDIT_EXE).upper()} WAS UNABLE TO CLEAN THESE PLUGINS: (Invalid Plugin Name or {info.XEDIT_EXE} Timed Out):")
        for elem in info.clean_failed_list:
            print(elem)
    if len(info.clean_results_UDR) > 1:
        print(f"\n✔️ The following plugins had Undisabled Records and {info.XEDIT_EXE} properly disabled them:")
        for elem in info.clean_results_UDR:
            print(elem)
    if len(info.clean_results_ITM) > 1:
        print(f"\n✔️ The following plugins had Identical To Master Records and {info.XEDIT_EXE} successfully cleaned them:")
        for elem in info.clean_results_ITM:
            print(elem)
    if len(info.clean_results_NVM) > 1:
        print("\n❌ CAUTION : The following plugins contain Deleted Navmeshes!")
        print("   Such plugins may cause navmesh related problems or crashes.")
        for elem in info.clean_results_NVM:
            print(elem)
    return True  # Required for running function check in PACT_Interface.


if __name__ == "__main__":  # AKA only autorun / do the following when NOT imported.
    pact_update_settings()
    check_process_mo2()
    check_settings_integrity()
    clean_plugins()
    os.system("pause")
