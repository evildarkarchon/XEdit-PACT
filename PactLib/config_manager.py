"""Configuration management for XEdit-PACT."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ruamel import yaml

from PactLib.utils import yaml_settings, yaml_settings_write

logger: logging.Logger = logging.getLogger(__name__)


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
        else:
            # Check if file is empty and initialize it
            try:
                with self._path.open(encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        logger.info(f"Initializing empty configuration file: {self._path}")
                        yaml_settings_write(str(self._path), {})
            except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError) as e:
                logger.error(f"Error checking configuration file: {e}")
                # Recreate the file if there's an issue
                self._path.unlink(missing_ok=True)
                self._path.touch()
                yaml_settings_write(str(self._path), {})

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves the value associated with a given key from a YAML configuration
        file. If the key is not found or an error occurs during the retrieval
        process, a default value is returned.

        This method attempts to access the specified configuration key within
        a YAML file. In case of a parsing error, missing file, or permission
        issue, it logs an appropriate error message and returns the provided
        default value.

        Args:
            key (str): The configuration key to look up within the YAML file.
            default (Any): The value to return if the key is not found or an
                error occurs during the retrieval process.

        Returns:
            Any: The value associated with the specified key if successfully
            retrieved and exists; otherwise, the provided default value.
        """
        try:
            value = yaml_settings(str(self._path), key)
        except (yaml.YAMLError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading config key '{key}': {e}")
            return default
        else:
            return value if value is not None else default

    def set(self, key: str, value: Any) -> bool:
        """
        Writes a given key-value pair to a YAML configuration file. Any errors encountered
        during the operation, such as file not found or permission issues, are logged,
        and the function returns a failure status.

        Args:
            key: The configuration key to set in the YAML file.
            value: The value to assign to the specified key in the configuration.

        Returns:
            bool: True if the key-value pair was successfully written, False otherwise.
        """
        try:
            # Use the thread-safe YAML manager directly instead of creating a separate thread
            yaml_settings_write(str(self._path), value, key)
        except (yaml.YAMLError, FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error writing config key '{key}': {e}")
            return False
        else:
            return True

    def get_all(self) -> dict[str, Any]:
        """
        Retrieves all key-value pairs from a YAML configuration file.

        This method attempts to read and parse a configuration file located at the
        path stored in the `_path` attribute. It returns the parsed content as a
        dictionary. If the file does not exist, lacks sufficient permissions, or
        encounters any YAML-specific parsing issues, an empty dictionary is returned
        and an error is logged.

        Returns:
            dict[str, Any]: The parsed contents of the configuration file as a
            dictionary. Returns an empty dictionary if the file is not readable or an
            error occurs.
        """
        try:
            with self._path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, FileNotFoundError, PermissionError, OSError) as e:
            logger.error(f"Error reading configuration file: {e}")
            return {}

    def update_multiple(self, updates: dict[str, Any]) -> bool:
        """
        Updates multiple key-value pairs in the underlying system. The method iterates through
        the provided updates dictionary, applying each key-value update using the `set` method.
        If any update fails, the method sets the success flag to `False`. The method returns
        a boolean indicating whether all updates were successfully applied.

        Args:
            updates (dict[str, Any]): A dictionary containing key-value pairs to update.

        Returns:
            bool: True if all updates were successfully applied, False otherwise.
        """
        try:
            success = True
            for key, value in updates.items():
                if not self.set(key, value):
                    success = False
                    logger.error(f"Failed to update config key: {key}")
        except (yaml.YAMLError, FileNotFoundError, PermissionError, OSError, ValueError) as e:
            logger.error(f"Error in update_multiple: {e}")
            return False
        else:
            return success

    def get_game_config(self, game_type: str) -> dict[str, Any]:
        """
        Retrieves the game configuration based on the specified game type.

        The function fetches configurations for xedit_list, skip_list, and
        quickautoclean_list categories corresponding to the provided game type
        from the internal data structure.

        Args:
            game_type: The type of the game for which the configuration is
                retrieved.

        Returns:
            A dictionary containing the configuration data. Keys include:
                - xedit_list: List of xedit configuration items for the specified
                  game type.
                - skip_list: List of skip configuration items for the specified
                  game type.
                - quickautoclean_list: List of quickautoclean configuration items
                  for the specified game type.
        """
        return {
            "xedit_list": self.get(f"PACT_Data.XEdit_Lists.{game_type}", []),
            "skip_list": self.get(f"PACT_Data.Skip_Lists.{game_type}", []),
            "quickautoclean_list": self.get(f"PACT_Data.QAC_Lists.{game_type}", []),
        }

    def get_paths(self) -> dict[str, Path | None]:
        """
        Retrieves and returns a dictionary of paths for various configuration keys.

        This method extracts specific configuration keys related to file paths
        and retrieves their corresponding values. The keys and their values are processed
        and formatted into a dictionary. If a key does not have an associated value
        in the configuration, a `None` value will be associated with the key in the
        resulting dictionary. The keys in the returned dictionary are lowercase
        with periods replaced by underscores.

        Returns:
            dict[str, Path | None]: A dictionary where each key is a modified version
            of the configuration key, and the value is a `Path` object if the configuration
            value exists, or `None` if it does not.

        Raises:
            None
        """
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
        """
        Retrieves application settings from the configuration source.

        This method fetches multiple configuration settings related to journal
        expiration, cleaning timeout, CPU threshold, and MO2 mode. The settings are
        obtained via the `get` method and returned as a dictionary.

        Returns:
            dict[str, Any]: A dictionary containing the following keys and their
            corresponding values:
                - journal_expiration (int): The expiration time for the journal in
                  days. Default value is 7.
                - cleaning_timeout (int): The timeout setting for cleaning operations in
                  seconds. Default value is 300.
                - cpu_threshold (int): The threshold value for CPU usage in percentage.
                  Default value is 5.
                - mo2_mode (bool): A boolean flag indicating whether MO2 Mode is
                  enabled. Default value is False.
        """
        return {
            "journal_expiration": self.get("PACT_Settings.Journal_Expiration", 7),
            "cleaning_timeout": self.get("PACT_Settings.Cleaning_Timeout", 300),
            "cpu_threshold": self.get("PACT_Settings.CPU_Threshold", 5),
            "mo2_mode": self.get("PACT_Settings.MO2Mode", False),
        }

    def validate_paths(self) -> dict[str, bool]:
        """
        Validates the existence of file paths retrieved by the `get_paths` method
        and returns a dictionary indicating whether each path exists or not.
        This method handles cases where a path might be `None` and evaluates its
        existence accordingly.

        Returns:
            dict[str, bool]: A dictionary where the keys are path names (as
            strings) and the values are booleans indicating whether each path exists
            (True) or does not exist (False).
        """
        paths: dict[str, Path | None] = self.get_paths()
        return {name: path.exists() if path else False for name, path in paths.items()}
