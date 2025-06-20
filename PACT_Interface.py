#!/usr/bin/env python3
"""XEdit-PACT Main Interface - Refactored with centralized state management."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Slot
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PactLib.config_manager import ConfigManager
from PactLib.gui_controller import GuiController
from PactLib.state_manager import StateManager

# Constants  
PACT_DATA_PATH = Path("PACT Data")
PACT_YAML_PATH = PACT_DATA_PATH / "PACT Main.yaml"
PACT_CONFIG_PATH = PACT_DATA_PATH / "PACT Config.yaml"  # New config file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger: logging.Logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with refactored state management."""

    def __init__(self, state: StateManager, controller: GuiController) -> None:
        """Initialize the main window."""
        super().__init__()
        self.state: StateManager = state
        self.controller: GuiController = controller

        # UI elements
        self.log_display: QTextEdit | None = None
        self.load_order_button: QPushButton | None = None
        self.mo2_button: QPushButton | None = None
        self.xedit_button: QPushButton | None = None
        self.mo2_mode_button: QPushButton | None = None
        self.start_button: QPushButton | None = None
        self.stop_button: QPushButton | None = None
        self.status_bar: QStatusBar | None = None

        # Connect controller signals
        self._connect_controller_signals()

        # Connect state signals
        self._connect_state_signals()

        # Setup UI
        self._setup_ui()

        # Update initial state
        self._update_ui_from_state()

    def _connect_controller_signals(self) -> None:
        """Connect controller signals to UI updates."""
        self.controller.show_message.connect(self._show_message)
        self.controller.show_error.connect(self._show_error)
        self.controller.update_status.connect(self._update_status)

    def _connect_state_signals(self) -> None:
        """Connect state signals to UI updates."""
        self.state.configuration_changed.connect(self._on_configuration_changed)
        self.state.progress_changed.connect(self._on_progress_changed)
        self.state.cleaning_started.connect(self._on_cleaning_started)
        self.state.cleaning_finished.connect(self._on_cleaning_finished)
        self.state.plugin_processed.connect(self._on_plugin_processed)
        self.state.state_changed.connect(self._on_state_changed)

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        self.setWindowTitle("XEdit-PACT - Refactored")
        self.setMinimumSize(800, 600)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Configuration section
        config_group = self._create_configuration_group()
        main_layout.addWidget(config_group)

        # Control section
        control_group = self._create_control_group()
        main_layout.addWidget(control_group)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        main_layout.addWidget(self.log_display)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Menu bar
        self._create_menu_bar()

    def _create_configuration_group(self) -> QGroupBox:
        """Create the configuration section."""
        group = QGroupBox("Configuration")
        layout = QVBoxLayout()

        # Load Order
        lo_layout = QHBoxLayout()
        self.load_order_button = QPushButton("Configure Load Order")
        self.load_order_button.clicked.connect(self._configure_load_order)
        lo_layout.addWidget(self.load_order_button)
        lo_layout.addStretch()
        layout.addLayout(lo_layout)

        # MO2
        mo2_layout = QHBoxLayout()
        self.mo2_button = QPushButton("Configure MO2")
        self.mo2_button.clicked.connect(self._configure_mo2)
        mo2_layout.addWidget(self.mo2_button)

        self.mo2_mode_button = QPushButton("MO2 Mode: OFF")
        self.mo2_mode_button.setCheckable(True)
        self.mo2_mode_button.clicked.connect(self._toggle_mo2_mode)
        mo2_layout.addWidget(self.mo2_mode_button)
        mo2_layout.addStretch()
        layout.addLayout(mo2_layout)

        # xEdit
        xedit_layout = QHBoxLayout()
        self.xedit_button = QPushButton("Configure xEdit")
        self.xedit_button.clicked.connect(self._configure_xedit)
        xedit_layout.addWidget(self.xedit_button)
        xedit_layout.addStretch()
        layout.addLayout(xedit_layout)

        group.setLayout(layout)
        return group

    def _create_control_group(self) -> QGroupBox:
        """Create the control section."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout()

        self.start_button = QPushButton("Start Cleaning")
        self.start_button.clicked.connect(self._start_cleaning)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_cleaning)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        layout.addStretch()

        group.setLayout(layout)
        return group

    def _create_menu_bar(self) -> None:
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu: QMenu = menubar.addMenu("&File")

        refresh_action = QAction("&Refresh Configuration", self)
        refresh_action.triggered.connect(self.controller.refresh_configuration)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu: QMenu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _update_ui_from_state(self) -> None:
        """Update UI elements based on current state."""
        state_snapshot = self.state.state

        # Update configuration buttons
        if self.load_order_button:
            self._update_button_state(
                self.load_order_button,
                state_snapshot.is_load_order_configured,
                "Load Order ✓" if state_snapshot.is_load_order_configured else "Configure Load Order",
            )

        if self.mo2_button:
            self._update_button_state(
                self.mo2_button,
                state_snapshot.is_mo2_configured,
                "MO2 ✓" if state_snapshot.is_mo2_configured else "Configure MO2",
            )

        if self.xedit_button:
            self._update_button_state(
                self.xedit_button,
                state_snapshot.is_xedit_configured,
                "xEdit ✓" if state_snapshot.is_xedit_configured else "Configure xEdit",
            )

        # Update MO2 mode button
        if self.mo2_mode_button:
            self.mo2_mode_button.setChecked(state_snapshot.mo2_mode)
            self.mo2_mode_button.setText(
                f"MO2 Mode: {'ON' if state_snapshot.mo2_mode else 'OFF'}"
            )

        # Update control buttons
        if self.start_button:
            self.start_button.setEnabled(
                state_snapshot.is_fully_configured and not state_snapshot.is_cleaning
            )
        if self.stop_button:
            self.stop_button.setEnabled(state_snapshot.is_cleaning)

    def _update_button_state(
        self, button: QPushButton, configured: bool, text: str
    ) -> None:
        """Update button appearance based on configuration state."""
        button.setText(text)
        if configured:
            button.setStyleSheet(
                "QPushButton { background-color: #4CAF50; color: white; }"
            )
        else:
            button.setStyleSheet("")

    @Slot()
    def _configure_load_order(self) -> None:
        """Configure load order file."""
        self.controller.configure_load_order(self)

    @Slot()
    def _configure_mo2(self) -> None:
        """Configure MO2."""
        self.controller.configure_mo2(self)

    @Slot()
    def _configure_xedit(self) -> None:
        """Configure xEdit."""
        self.controller.configure_xedit(self)

    @Slot()
    def _toggle_mo2_mode(self) -> None:
        """Toggle MO2 mode."""
        if self.mo2_mode_button is None:
            return
        enabled = self.mo2_mode_button.isChecked()
        self.controller.toggle_mo2_mode(enabled)

    @Slot()
    def _start_cleaning(self) -> None:
        """Start the cleaning process."""
        self.controller.start_cleaning()

    @Slot()
    def _stop_cleaning(self) -> None:
        """Stop the cleaning process."""
        self.controller.stop_cleaning()

    @Slot(bool)
    def _on_configuration_changed(self, is_fully_configured: bool) -> None:
        """Handle configuration changes."""
        if self.start_button is None:
            return
        self.start_button.setEnabled(
            is_fully_configured and not self.state.get("is_cleaning")
        )
        if is_fully_configured:
            self._log("All paths configured ✓")

    @Slot(int, int)
    def _on_progress_changed(self, current: int, total: int) -> None:
        """Handle progress updates."""
        if total > 0:
            percentage = (current / total) * 100
            self._update_status(f"Progress: {current}/{total} ({percentage:.1f}%)")

    @Slot()
    def _on_cleaning_started(self) -> None:
        """Handle cleaning start."""
        if self.start_button is None or self.stop_button is None:
            return
        self._log("Cleaning started...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    @Slot()
    def _on_cleaning_finished(self) -> None:
        """Handle cleaning completion."""
        if self.start_button is None or self.stop_button is None:
            return
        self._log("Cleaning finished!")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    @Slot(str, str, str)
    def _on_plugin_processed(self, plugin: str, status: str, message: str) -> None:
        """Handle plugin processing completion."""
        icon = {
            "cleaned": "✓",
            "failed": "✗",
            "skipped": "⊘",
            "quickautoclean": "⚡",
        }.get(status, "?")

        self._log(f"{icon} {plugin}: {message}")

    @Slot(str, object)
    def _on_state_changed(self, property_name: str, _value: object) -> None:
        """Handle individual state property changes."""
        # Update specific UI elements based on property
        if property_name in [
            "is_load_order_configured",
            "is_mo2_configured",
            "is_xedit_configured",
            "mo2_mode",
            "is_cleaning",
        ]:
            self._update_ui_from_state()

    @Slot(str, str)
    def _show_message(self, title: str, message: str) -> None:
        """Show an information message."""
        QMessageBox.information(self, title, message)

    @Slot(str, str)
    def _show_error(self, title: str, message: str) -> None:
        """Show an error message."""
        QMessageBox.critical(self, title, message)

    @Slot(str)
    def _update_status(self, message: str) -> None:
        """Update the status bar."""
        if self.status_bar is None:
            return
        self.status_bar.showMessage(message)

    def _log(self, message: str) -> None:
        """Add a message to the log display."""
        if self.log_display:
            self.log_display.append(message)

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About XEdit-PACT",
            "XEdit-PACT (Refactored)\n\n"
            "Plugin Auto Cleaning Tool\n"
            "Version: 2.0.0\n\n"
            "A tool for automating plugin cleaning with xEdit",
        )


def create_application() -> tuple[QApplication, MainWindow]:
    """
    Creates and initializes the main application and its components.

    This function sets up the necessary components for the graphical user interface,
    including configuration management, state management, and the GUI controller.
    It also ensures that the application instance is properly created, with appropriate
    configuration for integration into the Qt application framework. Finally, it prepares
    and returns the QApplication instance and the main window for further handling or execution.

    Returns:
        tuple[QApplication, MainWindow]: A tuple containing the QApplication instance and the
        main window object.
    """
    # Create instances
    config = ConfigManager(PACT_CONFIG_PATH)
    state = StateManager()
    controller = GuiController(state, config)

    # Create GUI
    instance: QCoreApplication | None = QApplication.instance()
    if instance is None:
        app = QApplication(sys.argv)
    else:
        app: QApplication = instance if isinstance(instance, QApplication) else QApplication(sys.argv)
    app.setApplicationName("XEdit-PACT")
    window = MainWindow(state, controller)

    return app, window


def main() -> None:
    """Main entry point."""
    try:
        app, window = create_application()
        window.show()
        sys.exit(app.exec())
    except (OSError, RuntimeError, ValueError) as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()