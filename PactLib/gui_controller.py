"""Controller to mediate between GUI and business logic."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PactLib.state_manager import StateManager
from cleaning_service import CleaningService
from cleaning_worker import CleaningWorker
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QWidget

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
        """Configure load order file."""
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
        """Configure Mod Organizer 2."""
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
        """Configure xEdit."""
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
        """Toggle MO2 mode."""
        self.state.update(mo2_mode=enabled)
        self.config.set("PACT_Settings.MO2Mode", enabled)
        self.update_status.emit(f"MO2 Mode {'enabled' if enabled else 'disabled'}")

    def get_plugins_to_clean(self) -> list[str]:
        """Get list of plugins to clean from load order."""
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
        """Start the cleaning process."""
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
        """Stop the cleaning process."""
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
        """Refresh configuration from file."""
        self._load_configuration()
        self.update_status.emit("Configuration refreshed")

    def get_state_summary(self) -> str:
        """Get a summary of the current state."""
        state = self.state.state
        return (
            f"Configuration Status:\n"
            f"  Load Order: {'✓' if state.is_load_order_configured else '✗'}\n"
            f"  MO2: {'✓' if state.is_mo2_configured else '✗'}\n"
            f"  xEdit: {'✓' if state.is_xedit_configured else '✗'}\n"
            f"  MO2 Mode: {'Enabled' if state.mo2_mode else 'Disabled'}\n"
            f"  Game Type: {state.game_type or 'Not detected'}"
        )