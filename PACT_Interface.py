#!/usr/bin/env python3
"""XEdit-PACT Main Interface - Refactored with centralized state management."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from PactLib.config_manager import ConfigManager
from PactLib.gui_controller import GuiController
from PactLib.logging_config import get_logger, log_startup_info, setup_logging
from PactLib.state_manager import AppState, StateManager

if TYPE_CHECKING:
    from logging import Logger

# Constants
PACT_DATA_PATH: Path = Path("PACT Data")
PACT_YAML_PATH: Path = PACT_DATA_PATH / "PACT Main.yaml"
PACT_CONFIG_PATH: Path = PACT_DATA_PATH / "PACT Config.yaml"  # New config file

# Setup logging
setup_logging()
logger: Logger = get_logger(__name__)
log_startup_info(logger)


class CleaningProgressDialog(QDialog):
    """Dialog that shows cleaning progress and statistics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the cleaning progress dialog."""
        super().__init__(parent)
        self._current_plugin_name: str | None = None
        self.setWindowTitle("Cleaning Progress")
        self.setMinimumSize(450, 300)
        self.setModal(False)  # Non-modal so user can interact with main window

        # Track if cleaning is in progress
        self._cleaning_in_progress: bool = True

        # Create UI elements
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout: QVBoxLayout = QVBoxLayout(self)

        # Progress section
        progress_group: QGroupBox = QGroupBox("Progress")
        progress_layout: QVBoxLayout = QVBoxLayout()

        # Current plugin label
        self.current_plugin_label: QLabel = QLabel("Waiting to start...")
        self.current_plugin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font: QFont = self.current_plugin_label.font()
        font.setPointSize(font.pointSize() + 2)
        self.current_plugin_label.setFont(font)
        progress_layout.addWidget(self.current_plugin_label)

        # Progress bar
        self.progress_bar: QProgressBar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        progress_layout.addWidget(self.progress_bar)

        # Progress text
        self.progress_label: QLabel = QLabel("0 / 0 plugins")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Statistics section
        stats_group: QGroupBox = QGroupBox("Statistics")
        stats_layout: QVBoxLayout = QVBoxLayout()

        # Create statistics labels
        self.stats_labels: dict[str, QLabel] = {}
        stats_items: list[tuple[str, str]] = [
            ("cleaned", "✓ Cleaned:"),
            ("failed", "✗ Failed:"),
            ("skipped", "⊘ Skipped:"),
            ("total", "Total:"),
        ]

        for key, label_text in stats_items:
            row_layout: QHBoxLayout = QHBoxLayout()
            label: QLabel = QLabel(label_text)
            label.setMinimumWidth(150)
            row_layout.addWidget(label)

            value_label: QLabel = QLabel("0")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.stats_labels[key] = value_label
            row_layout.addWidget(value_label)
            row_layout.addStretch()

            stats_layout.addLayout(row_layout)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        layout.addStretch()

        # Button box
        self.button_box: QDialogButtonBox = QDialogButtonBox()

        # Stop button (only shown during cleaning)
        self.stop_button: QPushButton = QPushButton("Stop Cleaning")
        self.stop_button.setStyleSheet("QPushButton { background-color: #ff4444; color: white; }")
        self.button_box.addButton(self.stop_button, QDialogButtonBox.ButtonRole.ActionRole)

        # Close button (only enabled after cleaning)
        self.close_button: QPushButton = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)
        self.close_button.setEnabled(False)

        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def update_progress(self, current: int, total: int) -> None:
        """
        Updates the progress of a progress bar and its associated label based on the current and total values.

        This method calculates the progress percentage, updates the progress bar's value, and sets the text of
        the progress label to indicate the current and total progress. If a `_current_plugin_name` attribute
        is present and non-empty, it incorporates the plugin name into the progress bar's displayed format.
        If the total is zero, it resets the progress bar and label to their initial states.

        Args:
            current (int): The current progress count of the operation.
            total (int): The total progress count for the operation.
        """
        if total > 0:
            percentage: int = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_label.setText(f"{current} / {total} plugins")

            # Update progress bar format to show current plugin and percentage
            if hasattr(self, "_current_plugin_name") and self._current_plugin_name:
                self.progress_bar.setFormat(f"{self._current_plugin_name} / {percentage}%")
            else:
                self.progress_bar.setFormat("%p%")
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText("0 / 0 plugins")
            self.progress_bar.setFormat("%p%")

    def update_current_plugin(self, plugin_name: str) -> None:
        """
        Updates the current plugin label and manages the progress bar display.

        This function sets the label text to reflect the name of the currently processing
        plugin. It additionally formats and updates the progress bar display if a progress
        value greater than zero is present.

        Args:
            plugin_name: The name of the plugin to be set as the current processing plugin.
        """
        self.current_plugin_label.setText(f"Processing: {plugin_name}")
        self._current_plugin_name = plugin_name

        # Update progress bar format
        if self.progress_bar.value() > 0:
            self.progress_bar.setFormat(f"{plugin_name} / {self.progress_bar.value()}%")

    def update_statistics(self, stats: dict[str, int]) -> None:
        """
        Updates the statistics display for the user interface.

        This method iterates through the provided statistics dictionary and updates the
        associated labels in the user interface with the corresponding values. The keys
        in the given `stats` dictionary must match the keys defined in `self.stats_labels`
        for the display to be updated.

        Args:
            stats: A dictionary where the keys are strings representing statistical
                categories, and the values are integers representing the statistics
                to be displayed.
        """
        for key, label in self.stats_labels.items():
            if key in stats:
                label.setText(str(stats[key]))

    def set_cleaning_finished(self) -> None:
        """
        Marks the completion of the cleaning process and updates the UI components accordingly.

        This method ensures the cleaning process is visually finalized by changing the UI elements.
        It updates the text displayed on a label, hides the stop button, enables the close button,
        and adjusts the progress bar format depending on the state of completion.

        Returns:
            None
        """
        self._cleaning_in_progress = False
        self.current_plugin_label.setText("Cleaning completed!")
        self.stop_button.setVisible(False)
        self.close_button.setEnabled(True)

        # Update progress bar format to show completion
        if self.progress_bar.value() == 100:
            self.progress_bar.setFormat("Completed - 100%")
        else:
            self.progress_bar.setFormat(f"Stopped - {self.progress_bar.value()}%")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle close event."""
        if self._cleaning_in_progress:
            reply: QMessageBox.StandardButton = QMessageBox.question(
                self,
                "Cleaning in Progress",
                "Cleaning is still in progress. Are you sure you want to close this dialog?\n\n"
                "Note: Closing this dialog will not stop the cleaning process.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()


class MainWindow(QMainWindow):
    """Main application window with refactored state management."""

    def __init__(self, state: StateManager, controller: GuiController) -> None:
        """Initialize the main window."""
        super().__init__()
        self.state: StateManager = state
        self.controller: GuiController = controller
        self._updating_ui: bool = False  # Flag to prevent recursive updates
        self._update_timer: QTimer = QTimer()  # Timer for debouncing UI updates
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)  # 50ms delay
        self._update_timer.timeout.connect(self._perform_ui_update)

        # UI elements
        self.progress_dialog: CleaningProgressDialog | None = None
        self.load_order_button: QPushButton | None = None
        self.mo2_button: QPushButton | None = None
        self.mo2_mode_button: QPushButton | None = None
        self.partial_forms_button: QPushButton | None = None
        self.xedit_button: QPushButton | None = None
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
        self.setMinimumSize(650, 450)

        # Create central widget
        central_widget: QWidget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout: QVBoxLayout = QVBoxLayout(central_widget)

        # Configuration section
        config_group: QGroupBox = self._create_configuration_group()
        main_layout.addWidget(config_group)

        # Control section
        control_group: QGroupBox = self._create_control_group()
        main_layout.addWidget(control_group)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Menu bar
        self._create_menu_bar()

    def _create_configuration_group(self) -> QGroupBox:
        """Create the configuration section."""
        group: QGroupBox = QGroupBox("Configuration")
        layout: QVBoxLayout = QVBoxLayout()

        # Load Order
        lo_layout: QHBoxLayout = QHBoxLayout()
        self.load_order_button = QPushButton("Configure Load Order")
        self.load_order_button.clicked.connect(self._configure_load_order)
        lo_layout.addWidget(self.load_order_button)
        lo_layout.addStretch()
        layout.addLayout(lo_layout)

        # MO2
        mo2_layout: QHBoxLayout = QHBoxLayout()
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
        xedit_layout: QHBoxLayout = QHBoxLayout()
        self.xedit_button = QPushButton("Configure xEdit")
        self.xedit_button.clicked.connect(self._configure_xedit)
        xedit_layout.addWidget(self.xedit_button)
        xedit_layout.addStretch()
        layout.addLayout(xedit_layout)

        # Partial Forms (Experimental Feature)
        partial_forms_layout: QHBoxLayout = QHBoxLayout()
        self.partial_forms_button = QPushButton("Partial Forms: OFF")
        self.partial_forms_button.setCheckable(True)
        self.partial_forms_button.setToolTip("Enable experimental Partial Forms feature (requires XEdit >= 4.1.5b)")
        self.partial_forms_button.clicked.connect(self._toggle_partial_forms)
        partial_forms_layout.addWidget(self.partial_forms_button)
        partial_forms_layout.addStretch()
        layout.addLayout(partial_forms_layout)

        group.setLayout(layout)
        return group

    def _create_control_group(self) -> QGroupBox:
        """Create the control section."""
        group: QGroupBox = QGroupBox("Controls")
        layout: QHBoxLayout = QHBoxLayout()

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
        menubar: QMenuBar = self.menuBar()

        # File menu
        file_menu: QMenu = menubar.addMenu("&File")

        refresh_action: QAction = QAction("&Refresh Configuration", self)
        refresh_action.triggered.connect(self.controller.refresh_configuration)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        exit_action: QAction = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu: QMenu = menubar.addMenu("&Help")

        about_action: QAction = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _update_ui_from_state(self) -> None:
        """Update UI elements based on current state."""
        # Use timer to debounce rapid updates
        if self._update_timer.isActive():
            self._update_timer.stop()
        self._update_timer.start()

    def _perform_ui_update(self) -> None:
        """Perform the actual UI update with debouncing."""
        if self._updating_ui:
            return  # Prevent recursive updates

        self._updating_ui = True
        try:
            state_snapshot: AppState = self.state.state

            # Update configuration buttons efficiently
            if self.load_order_button:
                new_text = "Load Order ✓" if state_snapshot.is_load_order_configured else "Configure Load Order"
                if self.load_order_button.text() != new_text:
                    self._update_button_state(
                        self.load_order_button,
                        state_snapshot.is_load_order_configured,
                        new_text,
                    )

            if self.mo2_button:
                new_text = "MO2 ✓" if state_snapshot.is_mo2_configured else "Configure MO2"
                if self.mo2_button.text() != new_text:
                    self._update_button_state(
                        self.mo2_button,
                        state_snapshot.is_mo2_configured,
                        new_text,
                    )

            if self.xedit_button:
                new_text = "xEdit ✓" if state_snapshot.is_xedit_configured else "Configure xEdit"
                if self.xedit_button.text() != new_text:
                    self._update_button_state(
                        self.xedit_button,
                        state_snapshot.is_xedit_configured,
                        new_text,
                    )

            # Update MO2 mode button efficiently
            if self.mo2_mode_button:
                new_checked = state_snapshot.mo2_mode
                if self.mo2_mode_button.isChecked() != new_checked:
                    self.mo2_mode_button.setChecked(new_checked)

                new_text = f"MO2 Mode: {'ON' if state_snapshot.mo2_mode else 'OFF'}"
                if self.mo2_mode_button.text() != new_text:
                    self.mo2_mode_button.setText(new_text)

            # Update Partial Forms button efficiently
            if self.partial_forms_button:
                new_checked = state_snapshot.partial_forms_enabled
                if self.partial_forms_button.isChecked() != new_checked:
                    self.partial_forms_button.setChecked(new_checked)

                new_text = f"Partial Forms: {'ON' if state_snapshot.partial_forms_enabled else 'OFF'}"
                if self.partial_forms_button.text() != new_text:
                    self.partial_forms_button.setText(new_text)

            # Update control buttons efficiently
            if self.start_button:
                new_enabled = state_snapshot.is_fully_configured and not state_snapshot.is_cleaning
                if self.start_button.isEnabled() != new_enabled:
                    self.start_button.setEnabled(new_enabled)

            if self.stop_button:
                new_enabled = state_snapshot.is_cleaning
                if self.stop_button.isEnabled() != new_enabled:
                    self.stop_button.setEnabled(new_enabled)
        finally:
            self._updating_ui = False

    @staticmethod
    def _update_button_state(button: QPushButton, configured: bool, text: str) -> None:
        """Update button appearance based on configuration state."""
        button.setText(text)
        if configured:
            button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
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
        enabled: bool = self.mo2_mode_button.isChecked()
        self.controller.toggle_mo2_mode(enabled)

    @Slot()
    def _toggle_partial_forms(self) -> None:
        """Toggle Partial Forms feature with confirmation dialog."""
        if self.partial_forms_button is None:
            return
        enabled: bool = self.partial_forms_button.isChecked()
        if enabled:
            # Show warning dialog if enabling
            from PACT_Interface import show_partial_forms_warning  # noqa: PLC0415

            confirmed: bool = show_partial_forms_warning(self)
            if not confirmed:
                # User cancelled or closed dialog, revert button
                self.partial_forms_button.setChecked(False)
                return
        self.controller.toggle_partial_forms(enabled)

    @Slot()
    def _start_cleaning(self) -> None:
        """Start the cleaning process."""
        try:
            logger.info("Starting cleaning process...")
            self.controller.start_cleaning()
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Error starting cleaning: {e}")
            self._show_error("Error", f"Failed to start cleaning: {e}")

    @Slot()
    def _stop_cleaning(self) -> None:
        """Stop the cleaning process."""
        self.controller.stop_cleaning()

    @Slot(bool)
    def _on_configuration_changed(self, is_fully_configured: bool) -> None:
        """Handle configuration changes."""
        if self.start_button is None:
            return
        self.start_button.setEnabled(is_fully_configured and not self.state.get("is_cleaning"))
        if is_fully_configured:
            self._log("All paths configured ✓")

    @Slot(int, int)
    def _on_progress_changed(self, current: int, total: int) -> None:
        """Handle progress updates."""
        if total > 0:
            percentage: float = (current / total) * 100
            self._update_status(f"Progress: {current}/{total} ({percentage:.1f}%)")

        # Update progress dialog
        if self.progress_dialog and self.progress_dialog.isVisible():
            self.progress_dialog.update_progress(current, total)
            # Update statistics
            stats: dict[str, int] = self.state.state.cleaning_stats
            self.progress_dialog.update_statistics(stats)

    @Slot()
    def _on_cleaning_started(self) -> None:
        """Handle cleaning start."""
        if self.start_button is None or self.stop_button is None:
            return

        # Create and show progress dialog
        self.progress_dialog = CleaningProgressDialog(self)
        self.progress_dialog.stop_button.clicked.connect(self._stop_cleaning)

        # Update progress with current state
        stats: dict[str, int] = self.state.state.cleaning_stats
        self.progress_dialog.update_statistics(stats)
        self.progress_dialog.update_progress(self.state.get("progress", 0), self.state.get("total_plugins", 0))

        self.progress_dialog.show()
        self._log("Cleaning started...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    @Slot()
    def _on_cleaning_finished(self) -> None:
        """Handle cleaning completion."""
        if self.start_button is None or self.stop_button is None:
            return

        self._log("Cleaning finished!")

        # Update progress dialog
        if self.progress_dialog:
            self.progress_dialog.set_cleaning_finished()
            # Update final statistics
            stats: dict[str, int] = self.state.state.cleaning_stats
            self.progress_dialog.update_statistics(stats)

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    @Slot(str, str, str)
    def _on_plugin_processed(self, plugin: str, status: str, message: str) -> None:
        """Handle plugin processing completion."""
        icon: str = {
            "cleaned": "✓",
            "failed": "✗",
            "skipped": "⊘",
        }.get(status, "?")

        self._log(f"{icon} {plugin}: {message}")

        # Update current plugin in progress dialog
        if self.progress_dialog and self.progress_dialog.isVisible():
            current_plugin: str | None = self.state.get("current_plugin")
            if current_plugin:
                self.progress_dialog.update_current_plugin(current_plugin)

    @Slot(str, object)
    def _on_state_changed(self, property_name: str, value: object) -> None:
        """Handle individual state property changes."""
        # Update specific UI elements based on property
        if property_name in [
            "is_load_order_configured",
            "is_mo2_configured",
            "is_xedit_configured",
            "mo2_mode",
            "partial_forms_enabled",
            "is_cleaning",
        ]:
            self._update_ui_from_state()
        elif (
            property_name == "current_plugin"
            and self.progress_dialog
            and self.progress_dialog.isVisible()
            and isinstance(value, str)
        ):
            # Update current plugin in progress dialog
            self.progress_dialog.update_current_plugin(value)

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
        # Log messages are now only shown in status bar during cleaning
        if self.state.get("is_cleaning"):
            self._update_status(message)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event with proper cleanup."""
        # If cleaning is in progress, ask user for confirmation
        if self.state.get("is_cleaning"):
            reply: QMessageBox.StandardButton = QMessageBox.question(
                self,
                "Cleaning in Progress",
                "Cleaning is currently in progress. Are you sure you want to close the application?\n\n"
                "This will stop the cleaning process.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        # Stop any running cleaning process
        if self.state.get("is_cleaning"):
            self.controller.stop_cleaning()

        # Close progress dialog if open
        if self.progress_dialog and self.progress_dialog.isVisible():
            self.progress_dialog.close()

        event.accept()


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
    main_config: ConfigManager = ConfigManager(PACT_YAML_PATH)  # For skip lists and game configs
    user_config: ConfigManager = ConfigManager(PACT_CONFIG_PATH)  # For user settings
    state: StateManager = StateManager()
    controller: GuiController = GuiController(state, main_config, user_config)

    # Create GUI
    instance: QCoreApplication | None = QApplication.instance()
    if instance is None:
        app: QApplication = QApplication(sys.argv)
    else:
        app = instance if isinstance(instance, QApplication) else QApplication(sys.argv)
    app.setApplicationName("XEdit-PACT")
    window: MainWindow = MainWindow(state, controller)

    return app, window


def main() -> None:
    """
    Main entry point for the application.

    This function initializes the application, displays the main window, and handles any
    fatal errors that may occur during execution. If an error is encountered, it logs the
    error details and terminates the application with a non-zero exit code.

    Raises:
        OSError: If an operating system-related error is encountered.
        RuntimeError: If a runtime error occurs during application execution.
        ValueError: If an invalid value is encountered, causing the application to fail.

    Returns:
        None
    """
    try:
        app, window = create_application()
        window.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except (OSError, RuntimeError, ValueError) as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    except (TypeError, AttributeError, ImportError) as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


def show_partial_forms_warning(parent: QWidget) -> bool:
    """
    Show a custom warning dialog for the Partial Forms experimental feature.
    Returns True if the user confirms, False if cancelled or closed.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Experimental Feature Warning")
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    label = QLabel(
        "<b>⚠️ EXPERIMENTAL FEATURE WARNING ⚠️</b><br><br>"
        "Partial Forms is an extremely experimental feature that may cause issues.<br>"
        "It requires an XEdit version &gt;= 4.1.5b.<br><br>"
        "Because of the experimental nature of this feature:<br>"
        "&bull; No support will be provided for issues related to this feature<br>"
        "&bull; Use at your own risk<br>"
        "&bull; It may cause data corruption or other problems<br><br>"
        "Are you sure you want to enable Partial Forms?"
    )
    label.setWordWrap(True)
    layout.addWidget(label)

    button_box = QDialogButtonBox()
    enable_btn = QPushButton("Enable")
    cancel_btn = QPushButton("Cancel")
    button_box.addButton(enable_btn, QDialogButtonBox.ButtonRole.AcceptRole)
    button_box.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
    layout.addWidget(button_box)

    result = {"confirmed": False}

    def on_enable() -> None:
        result["confirmed"] = True
        dialog.accept()

    def on_cancel() -> None:
        dialog.reject()

    enable_btn.clicked.connect(on_enable)
    cancel_btn.clicked.connect(on_cancel)

    # If closed via window close, treat as cancel
    dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

    return bool(dialog.exec() == QDialog.DialogCode.Accepted and result["confirmed"])
