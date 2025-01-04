from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import psutil
from PySide6.QtCore import QEventLoop, QObject, QSize, Qt, QThread, QTimer, QUrl
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
            f"Plugin Auto Cleaning Tool {yaml_settings('PACT Data/PACT Main.yaml', 'PACT_Data.version')}"
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
        Creates a customizable QPushButton instance with adjustable styles, sizes,
        and click handling.

        This function allows you to create a QPushButton with default or custom
        values for minimum width, minimum height, padding, stylesheet, and event
        connections such as click handlers. It also provides a basic hover effect
        and ensures that styles can be further customized if needed.

        :param text: The text label displayed on the button.
        :type text: str
        :param kwargs: Additional customization options for button creation. Supports
            the following keys:
                - min_width (int): Minimum width of the button.
                - min_height (int): Minimum height of the button.
                - padding (Tuple[int, int]): Padding inside the button, specified as
                  (vertical, horizontal).
                - stylesheet (str): Additional styles to be applied to the button.
                - clicked (Callable): A callable to be connected to the button's
                  clicked event.
                - enabled (bool): Whether the button should be initially enabled.
        :type kwargs: Any
        :return: A QPushButton instance with the specified customizations applied.
        :rtype: QPushButton
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

        :attributes:
          - RegBT_BROWSE_LO: Button associated with the "Load Order" feature.
          - RegBT_BROWSE_MO2: Button associated with the "MO2" executable configuration.
          - RegBT_BROWSE_XEDIT: Button associated with the "XEdit" executable configuration.
          - configured_LO: Boolean indicating the state of the "Load Order" configuration.
          - configured_MO2: Boolean indicating the state of the "MO2" configuration.
          - configured_XEDIT: Boolean indicating the state of the "XEdit" configuration.
        """
        # Initialize states for load order button
        if "loadorder" in str(pact_settings("LoadOrder TXT")) or "plugins" in str(pact_settings("LoadOrder TXT")):
            load_order_txt = pact_settings("LoadOrder TXT")
            if isinstance(load_order_txt, str) and Path(load_order_txt).is_file():
                self.RegBT_BROWSE_LO.setStyleSheet(
                    "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_LO.setText("✔️ LOAD ORDER FILE SET")
                self.configured_LO = True
            else:
                self.RegBT_BROWSE_LO.setStyleSheet(
                    "color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_LO.setText("❓ LOAD ORDER FILE NOT FOUND")
                self.configured_LO = False

        # Initialize states for MO2 button
        if "ModOrganizer" in str(pact_settings("MO2 EXE")):
            mo2_exe_path = pact_settings("MO2 EXE")
            if isinstance(mo2_exe_path, str) and Path(mo2_exe_path).is_file():
                self.RegBT_BROWSE_MO2.setStyleSheet(
                    "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_MO2.setText("✔️ MO2 EXECUTABLE SET")
                self.configured_MO2 = True
            else:
                self.RegBT_BROWSE_MO2.setStyleSheet(
                    "color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_MO2.setText("❓ MO2 EXECUTABLE NOT FOUND")
                self.configured_MO2 = False

        # Initialize states for XEdit button
        if "Edit" in str(pact_settings("XEDIT EXE")):
            xedit_exe = pact_settings("XEDIT EXE")
            if isinstance(xedit_exe, str) and Path(xedit_exe).is_file():
                self.RegBT_BROWSE_XEDIT.setStyleSheet(
                    "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_XEDIT.setText("✔️ XEDIT EXECUTABLE SET")
                self.configured_XEDIT = True
            else:
                self.RegBT_BROWSE_XEDIT.setStyleSheet(
                    "color: black; background-color: lightyellow; border-radius: 5px; border: 1px solid gray;"
                )
                self.RegBT_BROWSE_XEDIT.setText("❓ XEDIT EXECUTABLE NOT FOUND")
                self.configured_XEDIT = False

    # ============== CLEAN PLUGINS BUTTON STATES ================

    @staticmethod
    def is_xedit_running() -> bool:
        """
        Checks if the xEdit application is currently running.

        This function scans through the list of active processes and determines if any of
        them matches the executable name of the xEdit application, as specified in the
        provided configuration or context.

        :return: Returns True if the xEdit application is running, False otherwise.
        :rtype: bool
        """
        xedit_procs = [
            proc
            for proc in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "create_time"])
            if matches_condition(proc.name(), info)
        ]
        xedit_running = False
        for proc in xedit_procs:
            if proc.name().lower() == str(info.XEDIT_EXE).lower():
                xedit_running = True
        return xedit_running

    def timed_states(self) -> None:
        """
        Checks and updates the state of the cleaning operation.

        This function handles updating the button states and visual styles based on
        the current cleaning process, as well as monitoring the cleaning thread. If
        a cleaning thread exists and the process finishes, the thread is terminated
        and reset. The function also checks if the external `xEdit` tool is running
        and adjusts UI elements accordingly. Ensures proper control states and
        appearance of all relevant GUI elements.

        :raises AttributeError: When an attribute related to the cleaning thread is
            accessed improperly.
        :rtype: None
        """
        xedit_running = self.is_xedit_running()

        if self.cleaning_thread is None:
            self.init_start_button(xedit_running)
        else:
            self.RegBT_BROWSE_LO.setEnabled(False)
            self.RegBT_BROWSE_MO2.setEnabled(False)
            self.RegBT_BROWSE_XEDIT.setEnabled(False)
            self.RegBT_EXIT.setEnabled(False)
            if progress_emitter.report_done is True and isinstance(self.cleaning_thread, PactThread):
                try:
                    self.cleaning_thread.terminate()
                    self.cleaning_thread.wait()
                    self.reset_thread()
                except AttributeError:
                    pass
            if "STOP CLEANING" not in self.RegBT_CLEAN_PLUGINS.text() and xedit_running is False:
                self.RegBT_CLEAN_PLUGINS.setText("START CLEANING")
                self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                    "color: black; background-color: lightblue; border-radius: 5px; border: 1px solid gray;"
                )

    def start_cleaning(self) -> None:
        """
        Starts the cleaning process by initializing and configuring a background thread
        and updating the user interface for controlling the cleaning operation.

        When invoked, this method ensures the cleaning process is handled in a separate
        thread. It connects various signals for updating the interface components, such
        as a progress bar, provides feedback to the user during the operation, and ensures
        thread management for resource safety. If the cleaning process is interrupted,
        appropriate termination steps are executed.

        :raises RuntimeError: If any background thread actions fail during execution
                              or signal handling.
        :return: None
        """
        if self.cleaning_thread is None:
            self.cleaning_thread = PactThread(progress_bar=self.ProgressBar)
            self.cleaning_thread.start()
            self.cleaning_thread.finished.connect(self.init_start_and_reset)
            progress_emitter.progress.connect(self.ProgressBar.setValue)
            progress_emitter.max_value.connect(self.ProgressBar.setMaximum)
            progress_emitter.plugin_value.connect(self.ProgressBar.setFormat)
            progress_emitter.visible.connect(self.ProgressBar.setVisible)
            progress_emitter.done.connect(self.cleaning_thread.terminate)
            progress_emitter.done.connect(self.cleaning_thread.wait)
            progress_emitter.done.connect(self.reset_thread)
            self.RegBT_CLEAN_PLUGINS.setText("STOP CLEANING")
            self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                "color: black; background-color: pink; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
            self.RegBT_CLEAN_PLUGINS.clicked.connect(self.stop_cleaning)

    def init_start_button(self, xedit_running: bool = False) -> None:
        """
        Initializes the state of the Start button based on the current configuration and
        application context. Enables or configures different UI elements related to the
        button depending on the provided conditions. The function ensures that buttons
        become actionable when corresponding configurations are met and modifies their
        appearance for user interaction readiness.

        :param xedit_running: Flag to indicate whether xEdit is currently running.
        :type xedit_running: bool
        :return: None
        :rtype: None
        """
        if self.RegBT_BROWSE_LO and not self.RegBT_BROWSE_LO.isEnabled():
            self.RegBT_BROWSE_LO.setEnabled(True)
        if self.RegBT_BROWSE_MO2 and not self.RegBT_BROWSE_MO2.isEnabled():
            self.RegBT_BROWSE_MO2.setEnabled(True)
        if self.RegBT_BROWSE_XEDIT and not self.RegBT_BROWSE_XEDIT.isEnabled():
            self.RegBT_BROWSE_XEDIT.setEnabled(True)
        if self.RegBT_EXIT and not self.RegBT_EXIT.isEnabled():
            self.RegBT_EXIT.setEnabled(True)
        if self.configured_LO and self.configured_XEDIT and xedit_running is False:
            self.RegBT_CLEAN_PLUGINS.setEnabled(True)
            self.RegBT_CLEAN_PLUGINS.setText("START CLEANING")
            self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                "color: black; background-color: lightblue; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
            self.RegBT_CLEAN_PLUGINS.clicked.connect(self.start_cleaning)

    def reset_thread(self) -> None:
        """
        Resets the thread by clearing its reference.

        This method sets the `cleaning_thread` attribute to None, effectively resetting
        any ongoing or set-up thread associated.

        :return: None
        """
        self.cleaning_thread = None

    def init_start_and_reset(self) -> None:
        """
        Initializes the start button and resets the related thread.

        This method performs two main tasks. Firstly, it initializes the start button
        by calling the `init_start_button` method, ensuring that it is prepared for
        further operations. Secondly, it resets the thread associated with the
        execution process by calling the `reset_thread` method, aligning the system to
        a clean initial state.

        :return: None
        """
        self.init_start_button()
        self.reset_thread()

    def stop_cleaning(self) -> None:
        """
        Stops the ongoing cleaning process if it is currently running. The method disables
        certain UI components, updates the UI texts and styles to indicate the stopping process,
        and waits for any running threads or associated programs to finish execution. After
        ensuring proper shutdown, it resets UI components appropriately.

        :return: None
        """
        if self.cleaning_thread is not None:
            progress_emitter.is_done = True
            self.RegBT_CLEAN_PLUGINS.setEnabled(False)
            is_stopping = False
            while self.is_xedit_running():
                if not is_stopping:
                    self.RegBT_CLEAN_PLUGINS.setText("...STOPPING...")
                    self.RegBT_CLEAN_PLUGINS.setStyleSheet(
                        "color: black; background-color: orange; border-radius: 5px; border: 1px solid gray;"
                    )
                    is_stopping = True
                if (
                    self.cleaning_thread is not None
                ):  # In case the thread is terminated before the while loop is broken.
                    loop = QEventLoop()
                    self.cleaning_thread.finished.connect(loop.quit)
                    loop.exec()
            print(
                "\n❌ CLEANING STOPPED! PLEASE WAIT UNTIL ALL RUNNING PROGRAMS ARE CLOSED BEFORE STARTING AGAIN!\n"
            )  # With the new while loop, this message might need to change - evildarkarchon
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
        Display a help popup dialog with options for the user and an external link to a Discord invitation.

        The help popup is launched as a `QMessageBox` with predefined text, options, and a URL link
        redirecting the user to an external help or community page if they choose to proceed.

        :raise: This method does not explicitly raise errors but relies on PySide6 widgets whose behavior
                might trigger runtime exceptions depending on the application state or environment constraints.

        :return: None
        """
        Box_Help = QMessageBox()
        Box_Help.setIcon(QMessageBox.Icon.Question)
        Box_Help.setWindowTitle("Need Help?")
        Box_Help.setText(UiPACTMainWin.help_box_msg)  # RESERVED | Box_Help.setInformativeText("...")
        Box_Help.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if Box_Help.exec() != QMessageBox.StandardButton.Cancel:
            QDesktopServices.openUrl(QUrl("https://discord.com/invite/7ZZbrsGQh4"))

    def update_popup(self) -> None:
        """
        Updates the application interface by checking for updates and displays a popup
        message informing the user of their update status. If a new version of PACT is
        available, provides a link to the PACT Nexus Page.

        :raises RuntimeError: If the update process encounters a critical internal
                               error and fails to proceed.
        :return: None
        """
        if pact_update_check():
            QMessageBox.information(self, "PACT Update", "You have the latest version of PACT!")
        else:
            # noinspection PyArgumentList
            QMessageBox.warning(
                self, "PACT Update", "New PACT version is available!\nPress OK to open the PACT Nexus Page."
            )
            QDesktopServices.openUrl(QUrl("https://www.nexusmods.com/fallout4/mods/56255"))

    """ @staticmethod
    def backup_popup():
        Box_Backup = QMessageBox()
        Box_Backup.setIcon(QMessageBox.Question)  # type: ignore
        Box_Backup.setWindowTitle("PACT Backup")
        Box_Backup.setText(UiPACTMainWin.backup_box_msg)  # RESERVED | Box_Backup.setInformativeText("...")
        Box_Backup.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)  # type: ignore
        if Box_Backup.exec() != QtWidgets.QMessageBox.Cancel:  # type: ignore
            UiPACTMainWin.pact_create_backup()

    @staticmethod
    def pact_create_backup():
        plugins_folder = Path(QFileDialog.getExistingDirectory())
        if plugins_folder:
            primary_backup = Path("PACT BACKUP/Primary Backup")
            if not primary_backup.exists():
                primary_backup.mkdir(parents=True, exist_ok=True)
                print("CREATING PRIMARY BACKUP, PLEASE WAIT...")
                for files in plugins_folder.glob("**/*"):
                    for file in files:
                        if info.plugins_pattern.search(file):
                            try:
                                plugin_path = plugins_folder.joinpath(file)
                                copy_path = primary_backup.joinpath(file)
                                shutil.copy2(plugin_path, copy_path)
                            except (PermissionError, OSError):
                                print(f"❌ ERROR : Unable to create a backup for {file}")
                                print("   You can run PACT in admin mode and try again.")
                                continue
                print("PRIMARY BACKUP CREATED!")
            else:
                print("PROCESSING ADDITIONAL BACKUP, PLEASE WAIT...")
                for files in plugins_folder.glob("**/*"):
                    for file in files:
                        if info.plugins_pattern.search(file):
                            plugin_backup = Path("PACT BACKUP", "Primary Backup", file)
                            plugin_current = plugins_folder.joinpath(file)
                            if plugin_backup.exists():
                                hash1 = hashlib.sha256(plugin_backup.read_bytes()).hexdigest()
                                hash2 = hashlib.sha256(plugin_current.read_bytes()).hexdigest()
                                if hash1 != hash2:  # Compare hashes between current and backup plugins.
                                    current_date = datetime.date.today().strftime('%y-%m-%d')
                                    dated_backup = Path("PACT BACKUP", f"BACKUP {current_date}")
                                    if not dated_backup.exists():
                                        dated_backup.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(plugin_current, dated_backup)
                                    # Remove plugin name from PACT Ignore list if hashes are different.
                                    with open("PACT Ignore.txt", "r", encoding="utf-8", errors="ignore") as Ignore_List:
                                        Ignore_Check = Ignore_List.read()
                                        if str(file) in Ignore_Check:
                                            Ignore_Check = Ignore_Check.replace(str(file), "")
                                    ignore_list = yaml_settings(f"PACT Ignore.yaml", f"PACT_Ignore_{get_game_mode(info).upper()}")
                                    ignore_list = remove_from_list(ignore_list, str(file))
                                    yaml_settings(f"PACT Ignore.yaml", f"PACT_Ignore_{get_game_mode(info).upper()}", ignore_list)
                            else:  # Create plugin backup if not already in Primary Backup.
                                current_date = datetime.date.today().strftime('%y-%m-%d')
                                dated_backup = Path("PACT BACKUP", f"BACKUP {current_date}")
                                if not dated_backup.exists():
                                    dated_backup.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(plugin_current, dated_backup)
                print("ADDITIONAL BACKUP PROCESSED!")

    @staticmethod
    def restore_popup():
        Box_Restore = QMessageBox()
        Box_Restore.setIcon(QMessageBox.Question)  # type: ignore
        Box_Restore.setWindowTitle("PACT Restore")
        Box_Restore.setText(UiPACTMainWin.restore_box_msg)  # RESERVED | Box_Restore.setInformativeText("...")
        Box_Restore.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)  # type: ignore
        if Box_Restore.exec() != QMessageBox.Cancel:  # type: ignore
            UiPACTMainWin.pact_restore_backup()

    @staticmethod
    def pact_restore_backup():
        plugins_folder = Path(QFileDialog.getExistingDirectory())
        if plugins_folder:
            primary_backup = Path("PACT BACKUP", "Primary Backup")
            if not primary_backup.exists():
                print("❌ ERROR : You need to create a backup before you can restore it!")
            else:
                print("RESTORING PRIMARY BACKUP, PLEASE WAIT...")
                for files in primary_backup.glob("**/*"):
                    for file in files:
                        if info.plugins_pattern.search(file):
                            plugin_backup = primary_backup.joinpath(file)
                            plugin_current = plugins_folder.joinpath(file)
                            if plugin_backup.exists() and plugin_current.exists():
                                try:
                                    shutil.copy2(plugin_backup, plugin_current)
                                except (PermissionError, OSError):
                                    print(f"❌ ERROR : Unable to restore a backup for {file}")
                                    print("   You can run PACT in admin mode and try again.")
                                    continue
                print("PRIMARY BACKUP RESTORED!")"""  # This is commented out because it's not functional right now.

    def pact_placeholder_popup(self) -> None:
        """
        Displays an informational popup dialog indicating that the requested feature
        is a placeholder and is not currently available.

        This method invokes a `QMessageBox` dialog with a predefined title and message,
        informing the user about the unavailability of the feature.

        :return: None
        """
        QMessageBox.information(self, "PACT Placeholder", "This feature is not available yet!")

    # ================= MAIN BUTTON FUNCTIONS ===================

    def update_settings(self) -> None:
        """
        Updates the application settings for Cleaning Timeout and Journal Expiration
        based on user input, writes them to the YAML configuration file, and displays
        an information message to confirm changes.

        This method reads input values from specific input fields, updates the YAML
        settings file with the provided values, and notifies the user of successful
        updates using a message box.

        :raises ValueError: If the text inputs cannot be converted to integers.

        :rtype: None
        """
        pact_update_settings(info)
        value_CT = int(self.InputField_CT.text())
        value_JE = int(self.InputField_JE.text())
        yaml_settings("PACT Settings.yaml", "PACT_Settings.Cleaning Timeout", value_CT)
        yaml_settings("PACT Settings.yaml", "PACT_Settings.Journal Expiration", value_JE)
        QMessageBox.information(self, "PACT Settings", "All PACT settings have been updated and refreshed!")

    def select_file_lo(self) -> None:
        """
        The `select_file_lo` method allows users to select a load order file through a file dialog. It validates the file path,
        confirms its existence, and ensures it includes either "loadorder" or "plugins" in its name. The method also updates the
        application's settings and UI based on the file's validity, providing feedback to the user.

        :raises FileNotFoundError: Raised only when an expected valid file does not exist in the given path.
        :raises ValueError: Raised when the selected file is not properly configured to contain specific identifiers.

        :return: None
        """
        LO_file, _ = QFileDialog.getOpenFileName(filter="*.txt")
        if Path(LO_file).exists() and ("loadorder" in LO_file or "plugins" in LO_file):
            QMessageBox.information(self, "New Load Order File Set", f"You have set the new path to: {LO_file} \n")
            yaml_settings("PACT Settings.yaml", "PACT_Settings.LoadOrder TXT", LO_file)
            self.RegBT_BROWSE_LO.setStyleSheet(
                "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_BROWSE_LO.setText("✔️ LOAD ORDER FILE SET")
            self.configured_LO = True
        elif Path(LO_file).exists() and "loadorder" not in LO_file and "plugins" not in LO_file:
            self.RegBT_BROWSE_LO.setStyleSheet(
                "color: black; background-color: orange; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_BROWSE_LO.setText("❌ WRONG LO FILE")

    def select_file_mo2(self) -> None:
        """
        Allows user to select and set the MO2 executable file through a file dialog. Updates
        the application UI and configuration upon selection.

        :param self: Instance of the class where this method is defined.

        :raises FileNotFoundError: Raised if the selected file path does not exist.

        :raises RuntimeError: Raised if there is an error updating the YAML settings.

        :return: None
        """
        MO2_EXE, _ = QFileDialog.getOpenFileName(filter="*.exe")
        if Path(MO2_EXE).exists():
            QMessageBox.information(self, "New MO2 Executable Set", "You have set MO2 to: \n" + MO2_EXE)
            yaml_settings("PACT Settings.yaml", "PACT_Settings.MO2 EXE", MO2_EXE)
            self.RegBT_BROWSE_MO2.setStyleSheet(
                "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_BROWSE_MO2.setText("✔️ MO2 EXECUTABLE SET")
            self.configured_MO2 = True

    def select_file_xedit(self) -> None:
        """
        This function provides a dialog for the user to select an executable file for XEDIT.
        The selected file is checked to ensure it exists and meets the necessary XEDIT criteria.
        If valid, it updates the relevant configuration settings and modifies the appearance
        and text of a button in the user interface.

        :raises ValueError: if the selected file is not compatible with XEDIT requirements.

        :return: None
        """
        XEDIT_EXE, _ = QFileDialog.getOpenFileName(filter="*.exe")
        if Path(XEDIT_EXE).exists() and matches_condition(XEDIT_EXE, info):
            QMessageBox.information(self, "New MO2 Executable Set", "You have set XEDIT to: \n" + XEDIT_EXE)
            yaml_settings("PACT Settings.yaml", "PACT_Settings.XEDIT EXE", XEDIT_EXE)
            self.RegBT_BROWSE_XEDIT.setStyleSheet(
                "color: black; background-color: lightgreen; border-radius: 5px; border: 1px solid gray;"
            )
            self.RegBT_BROWSE_XEDIT.setText("✔️ XEDIT EXECUTABLE SET")
            self.configured_XEDIT = True
        elif Path(XEDIT_EXE).exists() and not matches_condition(XEDIT_EXE, info):
            self.RegBT_BROWSE_XEDIT.setText("❌ WRONG XEDIT EXE")
            self.RegBT_BROWSE_XEDIT.setStyleSheet(
                "color: black; background-color: orange; border-radius: 5px; border: 1px solid gray;"
            )


# CLEANING NEEDS A SEPARATE THREAD SO IT DOESN'T FREEZE PACT GUI
class PactThread(QThread):
    """
    Handles cleaning operations in a separate thread that interacts with a progress bar.

    The class provides functionality for executing plugin cleaning processes in a
    dedicated thread. This ensures that the UI remains responsive during the
    cleaning process, while the status is updated in the progress bar. The
    thread also includes utilities to check for specific conditions (e.g.,
    whether certain processes are running) and adjusts its behavior accordingly.

    :ivar cleaning_done: Indicates whether the cleaning operations are completed.
    :type cleaning_done: bool
    :ivar progress_bar: A progress bar instance used to display progress updates.
    :type progress_bar: QProgressBar
    """
    CLEANING_DELAY_MS = 1000  # Extracted constant for clarity

    def __init__(self, progress_bar: QProgressBar, parent: QObject | None = None) -> None:
        """
        Initializes an instance of the class responsible for managing a progress bar and
        indicating cleaning status. This class is designed to encapsulate the state and
        control logic for the provided progress bar component.

        :param progress_bar: The QProgressBar instance that this object will manage.
                             It is used to display the progress visually to the user.
        :param parent: Optional parent QObject for this instance. If provided, the parent
                       will assume ownership of the object to manage its lifetime.
        """
        super().__init__(parent)
        self.cleaning_done = False
        self.progress_bar: QProgressBar = progress_bar

    def run(self) -> None:
        """
        Performs the main cleaning routine by first checking if a specific process
        (Mod Organizer 2) is running. If the process is detected, the cleaning
        routine is aborted, the progress bar is hidden, and the application quits
        immediately. Otherwise, it proceeds with the cleaning operations, ensuring
        a delay after the execution.

        This function encapsulates the control flow of the cleaning operation,
        managing the required checks and executions step-by-step.

        :raises RuntimeError: if any cleaning operations fail during execution.

        :return: None
        """
        is_mo2_running = check_process_mo2(progress_emitter)
        if is_mo2_running:
            self._hide_progress_bar_and_quit()
            return

        self._perform_cleaning_operations()
        self.msleep(self.CLEANING_DELAY_MS)

    def _hide_progress_bar_and_quit(self) -> None:
        """
        Hides the progress bar if it is visible and quits the application. This function checks the visibility
        of the progress bar, and if it is visible, it hides the progress bar before exiting the application.
        No value is returned.

        :return: None
        """
        if self.progress_bar:
            self.progress_bar.setVisible(False)
        self.quit()

    @staticmethod
    def _perform_cleaning_operations() -> None:
        """
        Performs a series of cleaning and integrity check operations.

        This static method executes necessary actions to ensure that
        settings are consistent and that plugins are cleaned up. It
        relies on auxiliary functions for these operations to maintain
        the system's operational integrity.

        :raises RuntimeError: If an error occurs during checking of settings
                              integrity.
        :raises ValueError: If invalid progress emitter is encountered during
                            plugin cleanup.

        :return: None
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
