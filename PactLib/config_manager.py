"""Configuration management for XEdit-PACT."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ruamel import yaml

from PactLib.utils import yaml_settings, yaml_settings_write

logger = logging.getLogger(__name__)


class ConfigManager:
    """Single source for all configuration."""

    def __init__(self, config_path: Path) -> None:
        """Initialize the configuration manager."""
        self._path: Path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Ensure the configuration file and directory exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            logger.info(f"Creating configuration file: {self._path}")
            self._path.touch()
            yaml_settings_write(str(self._path), {})

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        try:
            value = yaml_settings(str(self._path), key)  
        except (yaml.YAMLError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading config key '{key}': {e}")
            return default
        else:
            return value if value is not None else default
    def set(self, key: str, value: Any) -> bool:
        """Set configuration value using dot notation."""
        try:
            yaml_settings_write(str(self._path), value, key)
        except (yaml.YAMLError, FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error writing config key '{key}': {e}")
            return False
        else:
            return True

    def get_all(self) -> dict[str, Any]:
        """Get all configuration as a dictionary."""
        try:
            with self._path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error reading configuration file: {e}")
            return {}

    def update_multiple(self, updates: dict[str, Any]) -> bool:
        """Update multiple configuration values at once."""
        success = True
        for key, value in updates.items():
            if not self.set(key, value):
                success = False
        return success

    def get_game_config(self, game_type: str) -> dict[str, Any]:
        """Get game-specific configuration."""
        return {
            "xedit_list": self.get(f"PACT_Data.XEdit_Lists.{game_type}", []),
            "skip_list": self.get(f"PACT_Data.Skip_Lists.{game_type}", []),
            "quickautoclean_list": self.get(f"PACT_Data.QAC_Lists.{game_type}", []),
        }

    def get_paths(self) -> dict[str, Path | None]:
        """Get all configured paths."""
        paths: dict[str, Path | None] = {}
        path_keys: list[str] = [
            "Load_Order.File",
            "Mod_Organizer.Binary",
            "Mod_Organizer.Install_Path",
            "xEdit.Binary",
            "xEdit.Install_Path",
        ]

        for key in path_keys:
            value = self.get(f"PACT_Settings.{key}")
            if value:
                paths[key.lower().replace(".", "_")] = Path(value)
            else:
                paths[key.lower().replace(".", "_")] = None

        return paths

    def get_settings(self) -> dict[str, Any]:
        """Get application settings."""
        return {
            "journal_expiration": self.get("PACT_Settings.Journal_Expiration", 7),
            "cleaning_timeout": self.get("PACT_Settings.Cleaning_Timeout", 300),
            "cpu_threshold": self.get("PACT_Settings.CPU_Threshold", 5),
            "mo2_mode": self.get("PACT_Settings.MO2Mode", False),
        }

    def validate_paths(self) -> dict[str, bool]:
        """Validate all configured paths exist."""
        paths: dict[str, Path | None] = self.get_paths()
        return {
            name: path.exists() if path else False
            for name, path in paths.items()
        }