#!/usr/bin/env python3
"""
AutoQAC Architecture Migration Tool

This script migrates configuration from the old PACT architecture to the new AutoQAC architecture.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from AutoQACLib.config_manager import ConfigManager
from AutoQACLib.logging_config import get_logger, setup_logging
from AutoQACLib.state_manager import StateManager
from AutoQACLib.utils import yaml_settings

if TYPE_CHECKING:
    from logging import Logger

# Setup logging for migration
setup_logging()
logger: Logger = get_logger(__name__)

# Paths
PACT_SETTINGS_PATH: Path = Path("PACT Settings.yaml")
BACKUP_PATH: Path = Path("PACT Settings.yaml.backup")
AUTOQAC_DATA_PATH: Path = Path("AutoQAC Data")
AUTOQAC_YAML_PATH: Path = AUTOQAC_DATA_PATH / "AutoQAC Main.yaml"
AUTOQAC_CONFIG_PATH: Path = AUTOQAC_DATA_PATH / "AutoQAC Config.yaml"  # New config location

# Constants for migration
PACT_DATA_PATH: Path = Path("PACT Data")
PACT_YAML_PATH: Path = PACT_DATA_PATH / "PACT Main.yaml"
PACT_CONFIG_PATH: Path = PACT_DATA_PATH / "PACT Config.yaml"  # New config location


def migrate_configuration() -> bool:
    """Migrate existing configuration to new structure."""
    print("Starting migration to refactored architecture...")

    # Create backup
    if PACT_SETTINGS_PATH.exists():
        shutil.copy2(PACT_SETTINGS_PATH, BACKUP_PATH)
        print(f"Created backup: {BACKUP_PATH}")
    elif AUTOQAC_YAML_PATH.exists():
        # Fallback to old config if settings file doesn't exist
        shutil.copy2(AUTOQAC_YAML_PATH, AUTOQAC_DATA_PATH / "AutoQAC Main.yaml.backup")
        print(f"Created backup of old config: {AUTOQAC_DATA_PATH / 'AutoQAC Main.yaml.backup'}")

    # Initialize new components
    config: ConfigManager = ConfigManager(AUTOQAC_CONFIG_PATH)
    state: StateManager = StateManager()

    # Load existing configuration
    print("Loading existing configuration...")

    # Migrate paths from PACT Settings.yaml
    settings_paths_mapping: dict[str, str] = {
        "PACT_Settings.LoadOrder TXT": "load_order_path",
        "PACT_Settings.MO2 EXE": "mo2_exe_path",
        "PACT_Settings.XEDIT EXE": "xedit_exe_path",
    }

    # Also check old PACT Main.yaml format for fallback
    yaml_paths_mapping: dict[str, str] = {
        "PACT_Settings.Load_Order.File": "load_order_path",
        "PACT_Settings.Mod_Organizer.Binary": "mo2_exe_path",
        "PACT_Settings.Mod_Organizer.Install_Path": "mo2_install_path",
        "PACT_Settings.xEdit.Binary": "xedit_exe_path",
        "PACT_Settings.xEdit.Install_Path": "xedit_install_path",
    }

    # First try to migrate from PACT Settings.yaml
    settings_found = False
    if PACT_SETTINGS_PATH.exists():
        for yaml_key, state_key in settings_paths_mapping.items():
            value = yaml_settings(str(PACT_SETTINGS_PATH), yaml_key)
            if value and value.strip():  # Check for non-empty strings
                print(f"  Migrating {yaml_key}: {value}")
                path: Path = Path(value)
                settings_found = True

                # Update state and save to new config format
                if state_key == "load_order_path":
                    state.update_configuration_paths(load_order_path=path)
                    config.set("PACT_Settings.Load_Order.File", str(path))
                elif state_key == "mo2_exe_path":
                    state.update_configuration_paths(
                        mo2_exe_path=path,
                        mo2_install_path=path.parent if path.exists() else None,
                    )
                    config.set("PACT_Settings.Mod_Organizer.Binary", str(path))
                    if path.exists():
                        config.set("PACT_Settings.Mod_Organizer.Install_Path", str(path.parent))
                elif state_key == "xedit_exe_path":
                    state.update_configuration_paths(
                        xedit_exe_path=path,
                        xedit_install_path=path.parent if path.exists() else None,
                    )
                    config.set("PACT_Settings.xEdit.Binary", str(path))
                    if path.exists():
                        config.set("PACT_Settings.xEdit.Install_Path", str(path.parent))

    # Fallback to old PACT Main.yaml format if settings file had no paths
    if not settings_found and AUTOQAC_YAML_PATH.exists():
        print("  No paths found in PACT Settings.yaml, checking AutoQAC Main.yaml...")
        for yaml_key, state_key in yaml_paths_mapping.items():
            value = yaml_settings(str(AUTOQAC_YAML_PATH), yaml_key)
            if value:
                print(f"  Migrating {yaml_key}: {value}")
                path = Path(value)
                if state_key == "load_order_path":
                    state.update_configuration_paths(load_order_path=path)
                    config.set("PACT_Settings.Load_Order.File", str(path))
                elif state_key == "mo2_exe_path":
                    state.update_configuration_paths(
                        mo2_exe_path=path,
                        mo2_install_path=path.parent if path.exists() else None,
                    )
                    config.set("PACT_Settings.Mod_Organizer.Binary", str(path))
                elif state_key == "xedit_exe_path":
                    state.update_configuration_paths(
                        xedit_exe_path=path,
                        xedit_install_path=path.parent if path.exists() else None,
                    )
                    config.set("PACT_Settings.xEdit.Binary", str(path))

    # Migrate settings from PACT Settings.yaml
    settings_mapping: dict[str, str] = {
        "PACT_Settings.Journal Expiration": "journal_expiration",
        "PACT_Settings.Cleaning Timeout": "cleaning_timeout",
    }

    if PACT_SETTINGS_PATH.exists():
        for yaml_key, state_key in settings_mapping.items():
            value = yaml_settings(str(PACT_SETTINGS_PATH), yaml_key)
            if value is not None:
                print(f"  Migrating {yaml_key}: {value}")
                state.update(**{state_key: value})
                config.set(f"PACT_Settings.{state_key.replace('_', ' ').title()}", value)

    # Also check for old format settings
    old_settings_mapping: dict[str, str] = {
        "PACT_Settings.Journal_Expiration": "journal_expiration",
        "PACT_Settings.Cleaning_Timeout": "cleaning_timeout",
        "PACT_Settings.CPU_Threshold": "cpu_threshold",
        "PACT_Settings.MO2Mode": "mo2_mode",
    }

    if AUTOQAC_YAML_PATH.exists():
        for yaml_key, state_key in old_settings_mapping.items():
            value = yaml_settings(str(AUTOQAC_YAML_PATH), yaml_key)
            if value is not None:
                print(f"  Migrating {yaml_key}: {value}")
                state.update(**{state_key: value})
                config.set(f"PACT_Settings.{state_key.replace('_', ' ').title().replace('Mo2', 'MO2')}", value)

    print("\nMigration complete!")
    print(f"Configuration backup saved to: {BACKUP_PATH}")
    print("\nCurrent state summary:")
    print(f"  Load Order configured: {state.state.is_load_order_configured}")
    print(f"  MO2 configured: {state.state.is_mo2_configured}")
    print(f"  xEdit configured: {state.state.is_xedit_configured}")
    print(f"  MO2 Mode: {'Enabled' if state.state.mo2_mode else 'Disabled'}")

    print("\nTo use the refactored version, run:")
    print("  python AutoQAC_Interface.py")

    return True


def verify_imports() -> bool:
    """Verify all required modules can be imported."""
    print("Verifying imports...")
    try:
        import importlib.util

        required_modules: list[str] = [
            "AutoQACLib.cleaning_service",
            "AutoQACLib.cleaning_worker",
            "AutoQACLib.config_manager",
            "AutoQACLib.gui_controller",
            "AutoQACLib.state_manager",
        ]

        for module_name in required_modules:
            if importlib.util.find_spec(module_name) is None:
                print(f"✗ Module not found: {module_name}")
                return False
            print(f"✓ Found module: {module_name}")

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except AttributeError as e:
        print(f"✗ Attribute error during import verification: {e}")
        return False
    else:
        print("✓ All modules found successfully")
        return True


def handle_migration_error(error: Exception, error_type: str) -> int:
    """Handle migration errors with appropriate logging and user messages."""
    logger.error(f"{error_type} during migration: {error}")
    print(f"\nMigration error: {error_type} - {error}")

    # Add specific guidance based on error type
    if error_type == "Permission denied":
        print("Please ensure you have write permissions to the current directory.")
    elif error_type == "Invalid configuration value":
        print("Please check your configuration files for invalid values.")
    elif error_type == "Missing configuration key":
        print("Your configuration file may be corrupted or incomplete.")
    elif error_type == "Unexpected error":
        print("This is an unexpected error. Please report this issue.")

    # Always offer backup restoration if available
    if BACKUP_PATH.exists():
        print(f"You can restore your configuration from: {BACKUP_PATH}")

    return 1


def main() -> int:
    """Run the migration."""
    print("AutoQAC Architecture Migration Tool\n")

    # Verify imports
    if not verify_imports():
        print("\nPlease ensure all new modules are present before migrating.")
        return 1

    # Check if any config exists
    if not PACT_SETTINGS_PATH.exists() and not AUTOQAC_YAML_PATH.exists():
        print("No existing configuration found. Nothing to migrate.")
        return 0

    # Run migration
    try:
        if migrate_configuration():
            print("\nMigration successful!")
            return 0
        print("\nMigration failed!")
        return 1  # noqa: TRY300
    except FileNotFoundError as e:
        return handle_migration_error(e, "Required file not found")
    except PermissionError as e:
        return handle_migration_error(e, "Permission denied")
    except OSError as e:
        return handle_migration_error(e, "System error")
    except ValueError as e:
        return handle_migration_error(e, "Invalid configuration value")
    except KeyError as e:
        return handle_migration_error(e, "Missing configuration key")
    except Exception as e:  # noqa: BLE001
        return handle_migration_error(e, "Unexpected error")


if __name__ == "__main__":
    sys.exit(main())
