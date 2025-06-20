"""Controller to mediate between GUI and business logic."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QWidget

from PactLib.cleaning_service import CleaningService
from PactLib.cleaning_worker import CleaningWorker
from PactLib.state_manager import StateManager

if TYPE_CHECKING:
    from config_manager import ConfigManager
    from state_manager import StateManager

logger = logging.getLogger(__name__)


class GuiController(QObject):
    """Mediates between GUI and business logic."""

    # Signals for GUI updates
    show_message = Signal(str, str)  # title, message
    show_error = Signal(str, str)  # title, message
    update_status = Signal(str)  # status message

    def __init__(
        self,
        state: StateManager,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the GUI controller."""
        super().__init__(parent)
        self.state: StateManager = state
        self.config: ConfigManager = config
        self.service: CleaningService = CleaningService(config, state)
        self.worker: CleaningWorker | None = None

        # Load initial configuration
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load configuration from file into state."""
        # Load paths
        paths = self.config.get_paths()
        self.state.update_configuration_paths(
            load_order_path=paths.get("load_order_file"),
            mo2_exe_path=paths.get("mod_organizer_binary"),
            mo2_install_path=paths.get("mod_organizer_install_path"),
            xedit_exe_path=paths.get("xedit_binary"),
            xedit_install_path=paths.get("xedit_install_path"),
        )

        # Load settings
        settings: dict[str, Any] = self.config.get_settings()
        self.state.update(**settings)

    def configure_load_order(self, parent_widget: QWidget) -> bool:
        """
        Configures the load order by allowing the user to select a file through a file dialog.
        The selected file must exist, and its path is then updated in the state and configuration.
        Provides user feedback via signals if the operation succeeds or fails.

        Args:
            parent_widget: Parent widget to attach the file dialog to.

        Returns:
            bool: True if the load order was successfully configured, False otherwise.
        """
        current_path = self.state.get("load_order_path")
        initial_dir: str | None = str(current_path.parent) if current_path else ""

        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select Load Order File",
            initial_dir,
            "Text Files (*.txt);;All Files (*.*)",
        )

        if file_path:
            path = Path(file_path)
            if path.exists():
                # Update state
                self.state.update_configuration_paths(load_order_path=path)

                # Save to config
                self.config.set("PACT_Settings.Load_Order.File", str(path))

                self.update_status.emit(f"Load order configured: {path.name}")
                return True
            self.show_error.emit("Error", "Selected file does not exist")
            return False
        return False

    def configure_mo2(self, parent_widget: QWidget) -> bool:
        """
        Configures the application to use Mod Organizer 2 by prompting the user to select
        the ModOrganizer.exe executable file. Validates the selected file and updates the
        application state and configuration accordingly.

        Args:
            parent_widget (QWidget): The parent widget that owns the file dialog.

        Returns:
            bool: True if the configuration was successful, False otherwise.
        """
        current_path = self.state.get("mo2_exe_path")
        initial_dir: str | None = str(current_path.parent) if current_path else ""

        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select ModOrganizer.exe",
            initial_dir,
            "Executable Files (*.exe);;All Files (*.*)",
        )

        if file_path:
            path = Path(file_path)
            if path.exists() and path.name.lower() == "modorganizer.exe":
                # Update state
                install_path: Path = path.parent
                self.state.update_configuration_paths(
                    mo2_exe_path=path,
                    mo2_install_path=install_path,
                )

                # Save to config
                self.config.update_multiple(
                    {
                        "PACT_Settings.Mod_Organizer.Binary": str(path),
                        "PACT_Settings.Mod_Organizer.Install_Path": str(install_path),
                    }
                )

                self.update_status.emit("Mod Organizer 2 configured")
                return True
            self.show_error.emit("Error", "Please select ModOrganizer.exe")
            return False
        return False

    def configure_xedit(self, parent_widget: QWidget) -> bool:
        """
        Configures the xEdit executable by allowing the user to select the appropriate file
        via a file dialog. Verifies the selected file as a valid xEdit executable, updates
        the internal state, and saves the configuration settings.

        Args:
            parent_widget (QWidget): The parent widget used as the parent for the open file
                dialog.

        Returns:
            bool: True if the configuration was successfully updated with a valid xEdit
                executable; False otherwise.
        """
        current_path = self.state.get("xedit_exe_path")
        initial_dir: str | None = str(current_path.parent) if current_path else ""

        file_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Select xEdit Executable",
            initial_dir,
            "Executable Files (*.exe);;All Files (*.*)",
        )

        if file_path:
            path = Path(file_path)
            if path.exists():
                # Validate it's an xEdit executable
                valid_names: list[str] = ["fo3edit", "fnvedit", "fo4edit", "sseedit", "tes5edit"]
                if not any(name in path.name.lower() for name in valid_names):
                    self.show_error.emit(
                        "Error",
                        "Selected file does not appear to be an xEdit executable",
                    )
                    return False

                # Update state
                install_path = path.parent
                self.state.update_configuration_paths(
                    xedit_exe_path=path,
                    xedit_install_path=install_path,
                )

                # Save to config
                self.config.update_multiple(
                    {
                        "PACT_Settings.xEdit.Binary": str(path),
                        "PACT_Settings.xEdit.Install_Path": str(install_path),
                    }
                )

                self.update_status.emit(f"xEdit configured: {path.name}")
                return True
            self.show_error.emit("Error", "Selected file does not exist")
            return False
        return False

    def toggle_mo2_mode(self, enabled: bool) -> None:
        """
        Toggle the MO2 mode on or off.

        This method updates the internal state and configuration to enable or disable
        MO2 mode based on the specified value. It also emits a status update signal
        indicating the current state of MO2 mode.

        Args:
            enabled (bool): Indicates whether MO2 mode should be enabled (True) or
                disabled (False).
        """
        self.state.update(mo2_mode=enabled)
        self.config.set("PACT_Settings.MO2Mode", enabled)
        self.update_status.emit(f"MO2 Mode {'enabled' if enabled else 'disabled'}")

    def get_plugins_to_clean(self) -> list[str]:
        """
        Reads the specified load order file and extracts the list of plugins to be cleaned.
        This method processes the file by identifying valid plugin entries with specific
        extensions (.esp, .esm, .esl), ignoring commented or empty lines, and removing any
        prefix characters such as *, +, or - from the plugin names. If successful, it returns
        the list of plugins; otherwise, it handles errors and returns an empty list.

        Returns:
            list[str]: A list of plugin names extracted from the load order file, or an
            empty list if the file cannot be read or processed.
        """
        state_snapshot = self.state.state

        if not state_snapshot.load_order_path or not state_snapshot.load_order_path.exists():
            logger.error("Load order file not found")
            return []

        try:
            # Read load order file
            plugins = []
            with state_snapshot.load_order_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Remove any prefix characters (*, +, etc.)
                        if line[0] in ["*", "+", "-"]:
                            line = line[1:].strip()
                        if line.lower().endswith((".esp", ".esm", ".esl")):
                            plugins.append(line)

            logger.info(f"Found {len(plugins)} plugins in load order")
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error reading load order: {e}")
            return []
        else:
            return plugins

    def start_cleaning(self) -> None:
        """
        Initiates and manages the cleaning process.

        This method is responsible for initiating a detailed cleaning process by
        validating configurations, retrieving plugins to clean, resetting the
        cleaning state, and setting up a worker for executing the cleaning tasks.
        It also handles signals for updating the cleaning status, signaling progress,
        and handling errors.

        Raises:
            Emits signals to present relevant errors during the execution.

        Signals:
            update_status (Signal): Emits status updates during the cleaning
                process.
        """
        if self.state.get("is_cleaning"):
            logger.warning("Cleaning already in progress")
            return

        # Validate configuration
        if not self.state.state.is_fully_configured:
            self.show_error.emit(
                "Configuration Required",
                "Please configure all paths before starting",
            )
            return

        # Get plugins to clean
        plugins: list[str] | None = self.get_plugins_to_clean()
        if not plugins:
            self.show_error.emit("No Plugins", "No plugins found in load order")
            return

        # Reset previous results
        self.state.reset_cleaning_state()

        # Create and start worker
        self.worker = CleaningWorker(self.service, self.state, plugins)

        # Connect signals
        self.worker.plugin_started.connect(
            lambda p: self.update_status.emit(f"Cleaning: {p}")
        )
        self.worker.plugin_completed.connect(self._on_plugin_completed)
        self.worker.finished.connect(self._on_cleaning_finished)
        self.worker.error.connect(
            lambda e: self.show_error.emit("Cleaning Error", e)
        )

        # Start cleaning
        self.worker.start()
        self.update_status.emit("Starting cleaning process...")

    def stop_cleaning(self) -> None:
        """
        Stops the ongoing cleaning process if it is currently running.

        The method ensures that the cleaning process is interrupted gracefully by
        checking the status of the worker. If the worker is running, it stops the
        process and emits a status update to notify that the cleaning process
        is being stopped.

        Raises:
            None
        """
        if self.worker and self.worker.isRunning():
            logger.info("Stopping cleaning process")
            self.worker.stop()
            self.update_status.emit("Stopping cleaning...")

    def _on_plugin_completed(self, plugin: str, success: bool, message: str) -> None:
        """Handle plugin completion."""
        logger.info(f"Plugin {plugin}: {'Success' if success else 'Failed'} - {message}")

    def _on_cleaning_finished(self) -> None:
        """Handle cleaning completion."""
        if self.worker:
            summary = self.worker.get_summary()
            self.show_message.emit("Cleaning Complete", summary)
            self.update_status.emit("Cleaning complete")
            self.worker = None

    def refresh_configuration(self) -> None:
        """
        Refreshes the application's configuration.

        This method is responsible for reloading the application's configuration
        by invoking a private method `_load_configuration` and subsequently emitting
        a signal to update the application's status indicating that the configuration
        has been refreshed.

        Raises:
            None

        Returns:
            None
        """
        self._load_configuration()
        self.update_status.emit("Configuration refreshed")

    def get_state_summary(self) -> str:
        """
        Generates a detailed configuration status summary based on the current state.

        This method consolidates various aspects of the application's configuration
        status, such as the status of load order, MO2, xEdit, and other relevant
        parameters. The summary is formatted as a multi-line string and indicates
        whether specific configurations have been completed or are pending.

        Returns:
            str: A formatted string summarizing the state of the application's
            configuration.
        """
        state = self.state.state
        return (
            f"Configuration Status:\n"
            f"  Load Order: {'✓' if state.is_load_order_configured else '✗'}\n"
            f"  MO2: {'✓' if state.is_mo2_configured else '✗'}\n"
            f"  xEdit: {'✓' if state.is_xedit_configured else '✗'}\n"
            f"  MO2 Mode: {'Enabled' if state.mo2_mode else 'Disabled'}\n"
            f"  Game Type: {state.game_type or 'Not detected'}"
        )