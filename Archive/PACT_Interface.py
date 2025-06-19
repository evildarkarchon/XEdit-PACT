from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import psutil
from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from PACT_Start import (
    ProgressEmitter,
    check_process_mo2,
    check_settings_integrity,
    clean_plugins,
    info,
    matches_condition,
    pact_settings,
    pact_update_check,
    pact_update_settings,
    yaml_settings,
)

"""TEMPLATES
QMessageBox.NoIcon | Question | Information | Warning | Critical
"""

progress_emitter = ProgressEmitter()


def remove_from_list(input_list: list, item: Any) -> list:
    return [value for value in input_list if value != item]


class UiPACTMainWin(QMainWindow):
    BUTTON_STYLE = "color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;"
    BACKUP_BUTTON_STYLE = """
        QPushButton {
            color: black;
            background-color: grey;
            border-radius: 5px;
            border: 1px solid gray;
        }
        QPushButton:hover {
            background-color: lightblue;
        }
    """

    def __init__(self) -> None:
        super().__init__()

        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        self.timer = QTimer()
        self.timer.timeout.connect(self.timed_states)
        self.timer.start(3000)
        self.pact_thread: PactThread | None = None
        self.cleaning_thread: PactThread | None = None  # Add this line to define self.cleaning_thread

        # Main window setup
        self.setObjectName("PACT_WINDOW")
        self.setWindowTitle(
            f"Plugin Auto Cleaning Tool {yaml_settings(str(Path('../PACT Data') / 'PACT Main.yaml'), 'PACT_Data.version')}"
        )
        self.setMinimumSize(QSize(640, 480))
        self.setMaximumSize(QSize(640, 480))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)

        # Top section - Update buttons
        self.top_layout = QHBoxLayout()
        self.RegBT_CHECK_UPDATES = self.create_button("CHECK FOR UPDATES", clicked=self.update_popup)
        self.RegBT_UPDATE_SETTINGS = self.create_button("UPDATE SETTINGS", clicked=self.update_settings)
        self.top_layout.addWidget(self.RegBT_CHECK_UPDATES)
        self.top_layout.addWidget(self.RegBT_UPDATE_SETTINGS)
        self.main_layout.addLayout(self.top_layout)

        # File selection buttons
        self.file_buttons_layout = QHBoxLayout()
        self.RegBT_BROWSE_LO = self.create_button(
            "SET LOAD ORDER FILE",
            stylesheet="color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;",
            clicked=self.select_file_lo,
        )
        self.RegBT_BROWSE_MO2 = self.create_button(
            "SET MO2 EXECUTABLE",
            stylesheet="color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;",
            clicked=self.select_file_mo2,
        )
        self.RegBT_BROWSE_XEDIT = self.create_button(
            "SET XEDIT EXECUTABLE",
            stylesheet="color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;",
            clicked=self.select_file_xedit,
        )

        self.file_buttons_layout.addWidget(self.RegBT_BROWSE_LO)
        self.file_buttons_layout.addWidget(self.RegBT_BROWSE_MO2)
        self.file_buttons_layout.addWidget(self.RegBT_BROWSE_XEDIT)
        self.main_layout.addLayout(self.file_buttons_layout)

        # Separator and labels
        self.main_layout.addWidget(self.create_horizontal_line())

        font_bold = QFont()
        font_bold.setPointSize(10)
        font_bold.setBold(True)

        # Create a vertical layout for the labels
        labels_layout = QVBoxLayout()
        labels_layout.setSpacing(1)  # Set smaller spacing between labels

        self.LBL_SETTINGS1 = QLabel("""YOU NEED TO SET YOUR LOAD ORDER FILE AND XEDIT EXECUTABLE BEFORE CLEANING
( MOD ORGANIZER 2 USERS ALSO NEED TO SET MO2 EXECUTABLE )""")
        self.LBL_SETTINGS1.setFont(font_bold)
        self.LBL_SETTINGS1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add labels to the layout
        labels_layout.addWidget(self.LBL_SETTINGS1)

        # Add the labels layout to the main layout
        self.main_layout.addLayout(labels_layout)

        # Backup buttons
        self.backup_layout = QHBoxLayout()
        self.RegBT_BACKUP_PLUGINS = self.create_button(
            "BACKUP PLUGINS",
            stylesheet="""
            QPushButton {
                color: black;
                background-color: grey;
                border-radius: 5px;
                border: 1px solid gray;}
                QPushButton:hover {
                    background-color: lightblue;
                }
            """,
            clicked=self.pact_placeholder_popup,
            enabled=False,
        )
        self.RegBT_RESTORE_BACKUP = self.create_button(
            "RESTORE BACKUP",
            stylesheet="""
            QPushButton {
                color: black;
                background-color: grey;
                border-radius: 5px;
                border: 1px solid gray;}
                QPushButton:hover {
                    background-color: lightblue;
                }
            """,
            clicked=self.pact_placeholder_popup,
            enabled=False,
        )
        self.backup_layout.addWidget(self.RegBT_BACKUP_PLUGINS)
        self.backup_layout.addWidget(self.RegBT_RESTORE_BACKUP)
        self.main_layout.addLayout(self.backup_layout)

        # Settings grid
        self.settings_layout = QGridLayout()
        self.settings_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create containers for each setting
        self.timeout_container = QWidget()
        self.timeout_layout = QVBoxLayout(self.timeout_container)
        self.timeout_layout.setContentsMargins(0, 0, 0, 0)
        self.timeout_layout.setSpacing(2)

        self.journal_container = QWidget()
        self.journal_layout = QVBoxLayout(self.journal_container)
        self.journal_layout.setContentsMargins(0, 0, 0, 0)
        self.journal_layout.setSpacing(2)

        # Cleaning timeout
        self.InputLabel_CT = QLabel("Cleaning Timeout")
        self.InputLabel_CT.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.InputField_CT = QLineEdit()
        self.InputField_CT.setValidator(QIntValidator())
        self.InputField_CT.setText(str(info.Cleaning_Timeout))
        self.InputField_CT.setFixedWidth(50)
        self.InputField_CT.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seconds_label = QLabel("(in seconds)")
        self.seconds_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add to timeout container
        self.timeout_layout.addWidget(self.InputLabel_CT)
        self.timeout_layout.addWidget(self.InputField_CT, alignment=Qt.AlignmentFlag.AlignCenter)
        self.timeout_layout.addWidget(self.seconds_label)

        # Journal expiration
        self.InputLabel_JE = QLabel("Journal Expiration")
        self.InputLabel_JE.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.InputField_JE = QLineEdit()
        self.InputField_JE.setValidator(QIntValidator())
        self.InputField_JE.setText(str(info.Journal_Expiration))
        self.InputField_JE.setFixedWidth(50)
        self.InputField_JE.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.days_label = QLabel("(in days)")
        self.days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add to journal container
        self.journal_layout.addWidget(self.InputLabel_JE)
        self.journal_layout.addWidget(self.InputField_JE, alignment=Qt.AlignmentFlag.AlignCenter)
        self.journal_layout.addWidget(self.days_label)

        # Clean plugins button
        self.RegBT_CLEAN_PLUGINS = self.create_button(
            "START CLEANING",
            stylesheet="color: black; background-color: lightgray; border-radius: 5px; border: 1px solid gray;",
            clicked=self.start_cleaning,
        )

        # Add widgets to grid with proper spacing
        self.settings_layout.addWidget(self.timeout_container, 0, 0)
        self.settings_layout.addWidget(self.RegBT_CLEAN_PLUGINS, 0, 1)
        self.settings_layout.addWidget(self.journal_container, 0, 2)

        # Add some spacing between columns
        self.settings_layout.setColumnMinimumWidth(0, 120)
        self.settings_layout.setColumnMinimumWidth(1, 200)
        self.settings_layout.setColumnMinimumWidth(2, 120)

        self.main_layout.addLayout(self.settings_layout)

        # Progress bar
        self.ProgressBar = QProgressBar()
        self.ProgressBar.setValue(0)
        self.ProgressBar.setFormat("")
        self.ProgressBar.setVisible(False)
        self.main_layout.addWidget(self.ProgressBar)

        # Bottom buttons
        self.bottom_layout = QHBoxLayout()
        self.RegBT_HELP = self.create_button(
            "HELP",
            stylesheet="""
            QPushButton {
                color: black;
                background-color: lightgray;
                border-radius: 5px;
                border: 1px solid gray;}
                QPushButton:hover {
                    background-color: lightblue;
                }
            """,
            clicked=self.help_popup,
        )
        self.RegBT_EXIT = self.create_button(
            "EXIT",
            stylesheet="""
            QPushButton {
                color: black;
                background-color: lightgray;
                border-radius: 5px;
                border: 1px solid gray;}
                QPushButton:hover {
                    background-color: lightblue;
                }
            """,
            clicked=self.close,
        )

        self.bottom_layout.addWidget(self.RegBT_HELP)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.RegBT_EXIT)
        self.main_layout.addLayout(self.bottom_layout)

        # Initialize states
        self.configured_LO = False
        self.configured_MO2 = False
        self.configured_XEDIT = False
        self.init_button_states()

    @staticmethod
    def create_button(text: str, **kwargs: Any) -> QPushButton:
        """
        Creates a QPushButton with customizable properties such as minimum size, stylesheet, padding, and
        event handlers. Provides default styles and fallback values for properties not explicitly specified
        in `kwargs`.

        Args:
            text (str): The text to display on the button.
            **kwargs (Any): Additional keyword arguments to customize the button:
                - min_width (int, optional): The minimum width for the button. Default is 100.
                - min_height (int, optional): The minimum height for the button. Default is 30.
                - padding (tuple[int, int], optional): Padding for the button in the format
                  (vertical, horizontal). Default is (8, 20).
                - stylesheet (str, optional): Custom stylesheet to override default styles.
                - clicked (Callable, optional): A callable function to connect to the button's
                  `clicked` signal.
                - enabled (bool, optional): Whether the button should be enabled or disabled.

        Returns:
            QPushButton: A QPushButton instance with applied configuration.

        """
        button = QPushButton(text)

        # Set default minimum sizes if not specified
        min_width = kwargs.get("min_width", 100)
        min_height = kwargs.get("min_height", 30)
        button.setMinimumWidth(min_width)
        button.setMinimumHeight(min_height)

        # Get padding values or use defaults
        padding = kwargs.get("padding", (8, 20))

        # Base stylesheet with customizable padding
        base_style = f"""
            QPushButton {{
                color: black;
                border-radius: 5px;
                border: 1px solid gray;
                padding: {padding[0]}px {padding[1]}px;
            }}
            QPushButton:hover {{
                background-color: lightblue;
            }}
        """

        # Combine base stylesheet with custom styles if provided
        if "stylesheet" in kwargs.get("stylesheet", ""):
            custom_style = kwargs["stylesheet"]
            # If custom style already includes the same properties, they'll override base style
            button.setStyleSheet(base_style + custom_style)
        else:
            # Add default background color if no custom style provided
            base_style = base_style.replace("QPushButton {", "QPushButton { background-color: lightgray;")
            button.setStyleSheet(base_style)

        if "clicked" in kwargs:
            button.clicked.connect(kwargs["clicked"])
        if "enabled" in kwargs:
            button.setEnabled(kwargs["enabled"])

        return button

    @staticmethod
    def create_horizontal_line() -> QFrame:
        """
        Creates and returns a horizontal line as a QFrame object.

        This static method generates a QFrame with the shape configured as
        a horizontal line (HLine) and the shadow set to sunken. It is
        commonly used in GUI layouts to create visual separators.

        :return: A QFrame object configured to represent a horizontal line
        :rtype: QFrame
        """
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def init_button_states(self) -> None:
        """
        Initializes the states of specific feature buttons based on settings and file paths.
        This includes the initialization for the "Load Order", "MO2", and "XEdit" buttons.
        The method determines the availability of respective configuration files or executables
        and updates corresponding button styles and states.
        :raises KeyError: If the settings keys ("LoadOrder TXT", "MO2 EXE", "XEDIT EXE") are
                          not found in the `pact_settings` function outputs.
        """
        # Define common button states and validation criteria
        button_configs = [
            {
                "button": self.RegBT_BROWSE_LO,
                "setting_key": "LoadOrder TXT",
                "validation_pattern": ["loadorder", "plugins"],
                "success_text": "✔️ LOAD ORDER FILE SET",
                "error_text": "❓ LOAD ORDER FILE NOT FOUND",
                "config_attr": "configured_LO"
            },
            {
                "button": self.RegBT_BROWSE_MO2,
                "setting_key": "MO2 EXE",
                "validation_pattern": ["ModOrganizer"],
                "success_text": "✔️ MO2 EXECUTABLE SET",
                "error_text": "❓ MO2 EXECUTABLE NOT FOUND",
                "config_attr": "configured_MO2"
            },
            {
                "button": self.RegBT_BROWSE_XEDIT,
                "setting_key": "XEDIT EXE",
                "validation_pattern": ["Edit"],
                "success_text": "✔️ XEDIT EXECUTABLE SET",
                "error_text": "❓ XEDIT EXECUTABLE NOT FOUND",
                "config_attr": "configured_XEDIT"
            }
        ]

        # Apply configuration to each button
        for config in button_configs:
            self._configure_button(**config)

    def _configure_button(self, button, setting_key, validation_pattern, success_text,
                          error_text, config_attr) -> None:
        """
    Configures a button's state based on the validation of its associated setting.

    :param button: The button to configure
    :param setting_key: The key for retrieving the setting value
    :param validation_pattern: List of strings to check in the setting value
    :param success_text: Text to display on successful validation
    :param error_text: Text to display on failed validation
    :param config_attr: The attribute name to store the configuration state
        """
        # Get setting value
        setting_value = pact_settings(setting_key)
        setting_str = str(setting_value)

        # Check if setting meets validation pattern
        if any(pattern in setting_str for pattern in validation_pattern):
            # Validate if path exists
            if isinstance(setting_value, str) and Path(setting_value).is_file():
                self._update_button_state(button, True, success_text)
                setattr(self, config_attr, True)
            else:
                self._update_button_state(button, False, error_text)
                setattr(self, config_attr, False)

    @staticmethod
    def _update_button_state(button, is_success, text) -> None:
        """
        Updates a button's visual state.

        :param button: The button to update
        :param is_success: Whether to apply success or warning styling
        :param text: Text to display on the button
        """
        style_color = "lightgreen" if is_success else "lightyellow"
        button.setStyleSheet(
            f"color: black; background-color: {style_color}; border-radius: 5px; border: 1px solid gray;"
        )
        button.setText(text)

    @staticmethod
    def is_xedit_running() -> bool:
        """
        Checks if the xEdit application is currently running.

        :return: True if xEdit is running, False otherwise
        """
        xedit_procs = [
            proc
            for proc in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "create_time"])
            if matches_condition(proc.name(), info)
        ]
        return any(proc.name().lower() == str(info.XEDIT_EXE).lower() for proc in xedit_procs)

    def timed_states(self) -> None:
        """
        Checks and updates the state of the cleaning operation.

        Updates UI based on cleaning thread status and xEdit process state.
        """
        xedit_running = self.is_xedit_running()

        if self.cleaning_thread is None:
            self.init_start_button(xedit_running)
        else:
            # Disable configuration buttons during cleaning
            self._set_config_buttons_enabled(False)

            # Handle thread completion
            if progress_emitter.is_done is True and isinstance(self.cleaning_thread, PactThread):
                try:
                    # Wait for thread to finish naturally instead of forcing termination
                    if self.cleaning_thread.isFinished():
                        self.reset_thread()
                    elif not self.cleaning_thread.isRunning():
                        # Thread stopped unexpectedly
                        self.reset_thread()
                except AttributeError:
                    # Thread might be None or deleted
                    self.reset_thread()

            # Update clean button if needed
            if "STOP CLEANING" not in self.RegBT_CLEAN_PLUGINS.text() and not xedit_running:
                self._update_button_state(
                    self.RegBT_CLEAN_PLUGINS,
                    is_success=None,  # Use default style
                    text="START CLEANING"
                )
                self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                    "color: black; background-color: lightblue; border-radius: 5px; border: 1px solid gray;"
                )

    def _set_config_buttons_enabled(self, enabled) -> None:
        """
        Sets the enabled state of all configuration buttons.

        :param enabled: Whether buttons should be enabled
        """
        self.RegBT_BROWSE_LO.setEnabled(enabled)
        self.RegBT_BROWSE_MO2.setEnabled(enabled)
        self.RegBT_BROWSE_XEDIT.setEnabled(enabled)
        self.RegBT_EXIT.setEnabled(enabled)

    def start_cleaning(self) -> None:
        """
    Starts the cleaning process in a background thread.
        """
        if self.cleaning_thread is None:
            # Create and configure cleaning thread
            self.cleaning_thread = PactThread(progress_bar=self.ProgressBar)

            # Connect signals BEFORE starting thread to avoid race condition
            self._connect_thread_signals()

            # Now start the thread
            self.cleaning_thread.start()

            # Update UI
            self._update_button_state(
                self.RegBT_CLEAN_PLUGINS,
                is_success=None,  # Custom styling
                text="STOP CLEANING"
            )
            self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                "color: black; background-color: pink; border-radius: 5px; border: 1px solid gray;"
            )

            # Update button connections
            self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
            self.RegBT_CLEAN_PLUGINS.clicked.connect(self.stop_cleaning)

    # noinspection PyUnresolvedReferences
    def _connect_thread_signals(self) -> None:
        """
        Connects all signals for the cleaning thread.
        """
        # For QThread's finished signal
        if hasattr(self.cleaning_thread, 'finished'):
            self.cleaning_thread.finished.connect(self.init_start_and_reset)

        # For progress_emitter signals
        if hasattr(progress_emitter, 'progress'):
            progress_emitter.progress.connect(self.ProgressBar.setValue)

        if hasattr(progress_emitter, 'max_value'):
            progress_emitter.max_value.connect(self.ProgressBar.setMaximum)

        if hasattr(progress_emitter, 'plugin_value'):
            progress_emitter.plugin_value.connect(self.ProgressBar.setFormat)

        if hasattr(progress_emitter, 'visible'):
            progress_emitter.visible.connect(self.ProgressBar.setVisible)

        if hasattr(progress_emitter, 'done'):
            # Don't forcefully terminate threads - let them finish naturally
            # The timed_states method will handle cleanup when thread finishes
            progress_emitter.done.connect(self.reset_thread)

    def init_start_button(self, xedit_running: bool = False) -> None:
        """
        Initializes the state of the Start button based on configuration.

        :param xedit_running: Flag to indicate whether xEdit is running
        """
        # Enable configuration buttons
        self._set_config_buttons_enabled(True)

        # Configure cleaning button based on prerequisites
        if self.configured_LO and self.configured_XEDIT and not xedit_running:
            self.RegBT_CLEAN_PLUGINS.setEnabled(True)
            self._update_button_state(
                self.RegBT_CLEAN_PLUGINS,
                is_success=None,  # Custom styling
                text="START CLEANING"
            )
            self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                "color: black; background-color: lightblue; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
            self.RegBT_CLEAN_PLUGINS.clicked.connect(self.start_cleaning)

    def reset_thread(self) -> None:
        """
        Resets the thread by clearing its reference.
        """
        self.cleaning_thread = None

    def init_start_and_reset(self) -> None:
        """
        Initializes the start button and resets the thread.
        """
        self.init_start_button()
        self.reset_thread()

    def stop_cleaning(self) -> None:
        """
        Stops the ongoing cleaning process.
        """
        if self.cleaning_thread is not None:
            progress_emitter.is_done = True
            self.RegBT_CLEAN_PLUGINS.setEnabled(False)

            # Wait for xEdit to close with timeout to prevent infinite loops
            is_stopping = False
            max_wait_iterations = 100  # Prevent infinite waiting
            iteration_count = 0
            while self.is_xedit_running() and iteration_count < max_wait_iterations:
                if not is_stopping:
                    self._update_button_state(
                        self.RegBT_CLEAN_PLUGINS,
                        is_success=None,  # Custom styling
                        text="...STOPPING..."
                    )
                    self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                        "color: black; background-color: orange; border-radius: 5px; border: 1px solid gray;"
                    )
                    is_stopping = True

                # Process events to keep UI responsive and add small delay
                QApplication.processEvents()
                QThread.msleep(100)  # Small delay to prevent busy waiting
                iteration_count += 1

            print("\n❌ CLEANING STOPPED! PLEASE WAIT UNTIL ALL RUNNING PROGRAMS ARE CLOSED BEFORE STARTING AGAIN!\n")
            self.ProgressBar.setFormat("Cleaning Stopped!")
            self.ProgressBar.setValue(0)

    # ================== POP-UPS / WARNINGS =====================

    backup_box_msg = """Press OK to select the ROOT FOLDER that contains all plugins you want to create a backup of. (Example: Fallout 4 / DATA folder.) This is how BACKUP works:

FIRST BACKUP : PACT will look through all subfolders from the selected folder and copy all esm / esp / esl files to PACT BACKUP / Primary Backup folder.

ALL BACKUPS AFTER : PACT will compare plugin file hashes with the primary backup. If any plugin has been modified/cleaned, it will create a new backup
and remove the plugin name from the ignore list in PACT Ignore.txt file.

NOTE that this method will NOT backup any NEW plugins to Primary Backup.
If you want to do this, you need to manually take plugins from other backup
folders and move them to the Primary Backup folder yourself."""

    restore_box_msg = """Press OK to select the ROOT FOLDER where you want to restore plugins from Primary Backup. (Example: Fallout 4 / DATA folder.) This is how RESTORE works:

PACT will take all esm/esp/esl plugins from the PACT BACKUP / Primary Backup folder and look them up in all subfolders from the selected folder.

IF a plugin match is found, PACT will replace that plugin with the one from the Primary Backup folder. The original backup of that plugin will still remain.

NOTE that this method will NOT restore plugins from OTHER backup folders.
If you want to do this, you need to manually copy plugins from other backup
folders to the Primary Backup folder, overwrite plugins and then run RESTORE."""

    help_box_msg = """If you have trouble running this program or wish to submit your PACT logs for additional help, join the Collective Modding Discord server.
    Please READ the #👋-welcome2 channel, react with the '2' emoji on the bot message there and leave your feedback in #💡-poet-guides-mods channel.
    Press OK to open the server link in your internet browser."""

    # @staticmethod recommended for func that don't call "self".

    @staticmethod
    def help_popup() -> None:
        """
        Displays a help popup dialog with a predefined message. If the "Ok" button is pressed, it opens a URL
        to a specified help resource, otherwise dismisses the dialog.

        Returns:
            None
        """
        box_help = QMessageBox()
        box_help.setIcon(QMessageBox.Icon.Question)
        box_help.setWindowTitle("Need Help?")
        box_help.setText(UiPACTMainWin.help_box_msg)  # RESERVED | box_help.setInformativeText("...")
        box_help.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if box_help.exec() != QMessageBox.StandardButton.Cancel:
            QDesktopServices.openUrl(QUrl("https://discord.com/invite/7ZZbrsGQh4"))

    def update_popup(self) -> None:
        """
        Displays a popup message indicating whether the PACT version is up-to-date or if an update is available.

        If the PACT version is up-to-date, an informational message is shown. If an update is
        available, a warning message is shown with an option to open the PACT Nexus page.

        Raises:
            TypeError: If the URL passed to QDesktopServices.openUrl is invalid.

        """
        if pact_update_check():
            QMessageBox.information(self, "PACT Update", "You have the latest version of PACT!")
        else:
            # noinspection PyArgumentList
            QMessageBox.warning(
                self, "PACT Update", "New PACT version is available!\nPress OK to open the PACT Nexus Page."
            )
            QDesktopServices.openUrl(QUrl("https://www.nexusmods.com/fallout4/mods/56255"))

    def pact_placeholder_popup(self) -> None:
        """
        Displays an informational popup to indicate that a feature is currently unavailable.

        This method creates a QMessageBox with a pre-defined title and message content,
        informing the user that the specific feature is not yet implemented or accessible.

        Raises:
            None
        """
        QMessageBox.information(self, "PACT Placeholder", "This feature is not available yet!")

    # ================= MAIN BUTTON FUNCTIONS ===================

    # Constants for UI elements
    SUCCESS_STYLE = "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
    ERROR_STYLE = "color: black; background-color: orange; border-radius: 5px; border: 1px solid gray;"
    CONFIG_FILE = "../PACT Settings.yaml"

    def update_settings(self) -> None:
        """
        Updates the application settings related to PACT configurations such as Cleaning
        Timeout and Journal Expiration. The settings are fetched from user input fields,
        validated, and saved to the configuration file.

        Raises:
            ValueError: If the input values for timeout or expiration days are not valid integers.
        """
        pact_update_settings(info)

        try:
            cleaning_timeout_value = int(self.InputField_CT.text())
            journal_expiration_days = int(self.InputField_JE.text())

            yaml_settings(self.CONFIG_FILE, "PACT_Settings.Cleaning Timeout", cleaning_timeout_value)
            yaml_settings(self.CONFIG_FILE, "PACT_Settings.Journal Expiration", journal_expiration_days)

            QMessageBox.information(self, "PACT Settings", "All PACT settings have been updated and refreshed!")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input",
                                "Please enter valid integer values for timeout and expiration days.")

    def _select_file(self, file_type, file_filter, config_key, button, success_text,
                     validation_func=None, error_text="❌ WRONG FILE", attr_name=None) -> bool:
        """
        Performs a file selection operation and updates the UI and configuration based on the selected file and validation
        results. Displays a success or error message depending on the outcome.

        Args:
            file_type: A string representing the type of file being selected (e.g., "Image", "Configuration File").
            file_filter: A string defining the file types to filter during file selection (e.g., "*.png;*.jpg").
            config_key: A string key corresponding to the location in the configuration file where the file path should be stored.
            button: A QPushButton object whose text and style will be updated based on the operation result.
            success_text: A string to display on the button when the file selection and validation are successful.
            validation_func: An optional callable function to validate the selected file. This function should return
                a boolean indicating whether the file is valid or not.
            error_text: A string to display on the button when the selected file fails validation. Default is "❌ WRONG FILE".
            attr_name: An optional string representing the name of a boolean attribute in the class. When provided and the
                operation is successful, the attribute will be updated to True.

        Returns:
            bool: True if the file is successfully selected and validated, otherwise False.
        """
        file_path, _ = QFileDialog.getOpenFileName(filter=file_filter)

        if not file_path or not Path(file_path).exists():
            return False

        # Perform validation if a validation function is provided
        is_valid = True
        if validation_func is not None:
            is_valid = validation_func(file_path)

        if is_valid:
            QMessageBox.information(self, f"New {file_type} Set", f"You have set the {file_type} to:\n{file_path}")
            yaml_settings(self.CONFIG_FILE, config_key, file_path)
            button.setStyleSheet(self.SUCCESS_STYLE)
            button.setText(success_text)

            # Update configured attribute if provided
            if attr_name and hasattr(self, attr_name):
                setattr(self, attr_name, True)

            return True
        else:
            button.setStyleSheet(self.ERROR_STYLE)
            button.setText(error_text)
            return False

    def select_file_lo(self) -> None:
        """
        Selects a load order file and validates its structure.

        This method allows users to choose a load order text file, validates its
        contents, and updates related configurations. The validation ensures that
        the chosen file name contains "loadorder" or "plugins", indicating it
        meets the load order file naming conventions.

        Returns:
            None
        """

        def validate_load_order(file_path):
            return "loadorder" in file_path or "plugins" in file_path

        self._select_file(
            file_type="Load Order File",
            file_filter="*.txt",
            config_key="PACT_Settings.LoadOrder TXT",
            button=self.RegBT_BROWSE_LO,
            success_text="✔️ LOAD ORDER FILE SET",
            validation_func=validate_load_order,
            error_text="❌ WRONG LO FILE",
            attr_name="configured_LO"
        )

    def select_file_mo2(self) -> None:
        """
        Selects a file for the MO2 executable configuration.

        This method facilitates the selection of an MO2 executable file by
        opening a file dialog with predefined filters and setting configuration
        values upon successful file selection. If the operation is successful,
        the method updates the corresponding user interface elements and sets
        internal state attributes.

        Raises:
            TypeError: If any argument passed to `_select_file` method is of an
                incorrect type.
            ValueError: If an invalid value is encountered during the file
                selection or configuration process.
        """
        self._select_file(
            file_type="MO2 Executable",
            file_filter="*.exe",
            config_key="PACT_Settings.MO2 EXE",
            button=self.RegBT_BROWSE_MO2,
            success_text="✔️ MO2 EXECUTABLE SET",
            attr_name="configured_MO2"
        )

    def select_file_xedit(self) -> None:
        """
        Selects and validates an XEDIT executable file.

        This method allows users to select a specific XEDIT executable file, validates it
        based on predetermined conditions, and updates the application's configuration settings
        accordingly.

        Returns:
            None
        """

        def validate_xedit(file_path):
            return matches_condition(file_path, info)

        self._select_file(
            file_type="XEDIT Executable",
            file_filter="*.exe",
            config_key="PACT_Settings.XEDIT EXE",
            button=self.RegBT_BROWSE_XEDIT,
            success_text="✔️ XEDIT EXECUTABLE SET",
            validation_func=validate_xedit,
            error_text="❌ WRONG XEDIT EXE",
            attr_name="configured_XEDIT"
        )


# CLEANING NEEDS A SEPARATE THREAD SO IT DOESN'T FREEZE PACT GUI
class PactThread(QThread):
    """
    Manages a progress bar and facilitates a cleaning operation process.

    This class is designed to encapsulate the logic for controlling a GUI-based progress
    bar and performing a sequence of cleaning operations. It ensures safe and correct
    execution through checks, such as detecting if a specific process (Mod Organizer 2)
    is running, and handles application state updates accordingly.

    Attributes:
        CLEANING_DELAY_MS (int): The delay in milliseconds to wait after the execution of
            cleaning operations.
        cleaning_done (bool): Indicates whether the cleaning operation has been completed.
        progress_bar (QProgressBar): The progress bar instance managed by the class.
    """
    CLEANING_DELAY_MS = 1000  # Extracted constant for clarity

    def __init__(self, progress_bar: QProgressBar, parent: QObject | None = None) -> None:
        """
        Initializes a processing handler with a progress bar and an optional parent.

        This constructor sets up the initial state of the handler, associating it with
        a provided progress bar and an optional parent object. Additionally, it
        initializes the `cleaning_done` flag to `False`.

        Args:
            progress_bar: The QProgressBar instance to associate with the processing
                handler. Used to visually track the progress of tasks.
            parent: The optional parent QObject. Defaults to None.
        """
        super().__init__(parent)
        self.cleaning_done = False
        self.progress_bar: QProgressBar = progress_bar

    def run(self) -> None:
        """
        Performs the execution of a cleaning task after ensuring specific conditions.

        The method first ensures that a required process is not already running. If the process is found to
        be running, it terminates the task. Otherwise, it proceeds with performing cleaning operations,
        introduces a delay, and completes the task.

        Args:
            self: An instance of the class that encapsulates this method.

        Raises:
            None.

        Returns:
            None.
        """
        is_mo2_running = check_process_mo2(progress_emitter, info)
        if is_mo2_running:
            self._hide_progress_bar_and_quit()
            return

        self._perform_cleaning_operations()
        self.msleep(self.CLEANING_DELAY_MS)

    def _hide_progress_bar_and_quit(self) -> None:
        """
        Hides the progress bar and quits the application.

        This method checks if a progress bar exists and hides it by setting its
        visibility to False. Afterward, it triggers the quit mechanism for the
        application. It is typically used to ensure that the progress bar is
        properly hidden before the application exits.

        Returns:
            None
        """
        if self.progress_bar:
            self.progress_bar.setVisible(False)
        self.quit()

    @staticmethod
    def _perform_cleaning_operations() -> None:
        """
        Performs a series of cleaning operations to ensure the integrity of the system's
        settings and tidy up associated plugins.

        This method is responsible for executing actions required to maintain and verify
        the proper functioning of settings configurations while cleaning up any associated
        plugins. It is designed to operate as a utility method that does not alter or return
        any external/internal state but ensures an environment clean-up process is executed
        appropriately.

        Returns:
            None
        """
        check_settings_integrity()
        clean_plugins(progress_emitter)


if __name__ == "__main__":
    gui_prompt = """\

SET YOUR LOAD ORDER FILE AND XEDIT EXECUTABLE TO ENABLE CLEANING
(MOD ORGANIZER 2 USERS ALSO NEED TO SET THE MO2 EXECUTABLE PATH)

PRESS 'START CLEANING' BUTTON TO CLEAN ALL ACTIVE GAME PLUGINS
(IF REQUIRED FILES ARE SET, BUTTON WILL BE ENABLED IN 3 SECONDS)

YOU CAN ALSO CREATE AND RESTORE PLUGIN BACKUPS (READ THE INFO CAREFULLY)
DON'T FORGET TO CHECK THE PACT README FOR MORE DETAILS AND INSTRUCTIONS
"""
    app = QApplication(sys.argv)
    ui = UiPACTMainWin()
    print(gui_prompt)
    ui.show()
    sys.exit(app.exec())
