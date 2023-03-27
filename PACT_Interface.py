import os
import sys
import psutil
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QUrl, QTimer, QThread
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog
from PACT_Start import (info, PACT_config, PACT_Current, pact_ini_update, pact_update_check, check_process_mo2, check_settings_paths, check_settings_integrity, clean_plugins)

'''TEMPLATES
QMessageBox.NoIcon | Question | Information | Warning | Critical
'''


class UiPACTMainWin(object):
    def __init__(self):
        super().__init__()  # Allow subclasses to inherit & extend behavior of parent class.
        self.configured_LO = False
        self.configured_MO2 = False
        self.configured_XEDIT = False

        self.ChkBT_UPDATE = None
        self.ChkBT_STATS = None
        self.LINE_SEPARATOR1 = None
        self.LBL_SETTINGS1 = None
        self.LBL_SETTINGS2 = None
        self.RegBT_BROWSE_LO = None
        self.RegBT_BROWSE_MO2 = None
        self.RegBT_BROWSE_XEDIT = None
        self.RegBT_CHECKUPDATES = None
        self.RegBT_CLEAN_PLUGINS = None

        self.RegBT_HELP = None
        self.RegBT_EXIT = None
        self.RegBT_CHECKUPDATES = None

        self.timer = QTimer()  # For CLEAN PLUGINS button auto check.
        self.timer.timeout.connect(self.timed_states)  # type: ignore
        self.timer.start(3000)  # In ms, will override QTimer.singleShot
        self.thread = None

    def setup_ui(self, PACT_WINDOW):
        # MAIN WINDOW
        PACT_WINDOW.setObjectName("PACT_WINDOW")
        PACT_WINDOW.setWindowTitle(f"Plugin Auto Cleaning Tool {PACT_Current[-4:]}")
        PACT_WINDOW.resize(640, 640)
        PACT_WINDOW.setMinimumSize(QtCore.QSize(640, 320))
        PACT_WINDOW.setMaximumSize(QtCore.QSize(640, 320))
        PACT_WINDOW.setWindowFlags(PACT_WINDOW.windowFlags() | Qt.WindowMinimizeButtonHint)  # type: ignore

        # ==================== MAIN WINDOW ITEMS =====================
        # TOP

        # Button - Browse Load Order
        self.RegBT_BROWSE_LO = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_BROWSE_LO.setGeometry(QtCore.QRect(80, 50, 150, 32))
        self.RegBT_BROWSE_LO.setObjectName("RegBT_BROWSE_LO")
        self.RegBT_BROWSE_LO.setText("SET LOAD ORDER FILE")
        self.RegBT_BROWSE_LO.setStyleSheet("background-color: lightyellow; border-radius: 5px; border: 1px solid gray;")
        self.RegBT_BROWSE_LO.clicked.connect(self.select_file_lo)  # type: ignore
        if "loadorder" in PACT_config["MAIN"]["LoadOrder TXT"] or "plugins" in PACT_config["MAIN"]["LoadOrder TXT"]:
            self.RegBT_BROWSE_LO.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")
            self.RegBT_BROWSE_LO.setText("✔️ LOAD ORDER FILE SET")
            self.configured_LO = True

        # Button - Browse MO2 EXE
        self.RegBT_BROWSE_MO2 = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_BROWSE_MO2.setGeometry(QtCore.QRect(245, 50, 150, 32))
        self.RegBT_BROWSE_MO2.setObjectName("RegBT_BROWSE_MO2")
        self.RegBT_BROWSE_MO2.setText("SET MO2 EXECUTABLE")
        self.RegBT_BROWSE_MO2.setStyleSheet("background-color: lightyellow; border-radius: 5px; border: 1px solid gray;")
        self.RegBT_BROWSE_MO2.clicked.connect(self.select_file_mo2)  # type: ignore
        if "ModOrganizer" in PACT_config["MAIN"]["MO2 EXE"]:
            self.RegBT_BROWSE_MO2.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")
            self.RegBT_BROWSE_MO2.setText("✔️ MO2 EXECUTABLE SET")
            self.configured_MO2 = True

        # Button - Browse XEDIT EXE
        self.RegBT_BROWSE_XEDIT = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_BROWSE_XEDIT.setGeometry(QtCore.QRect(410, 50, 150, 32))
        self.RegBT_BROWSE_XEDIT.setObjectName("RegBT_BROWSE_XEDIT")
        self.RegBT_BROWSE_XEDIT.setText("SET XEDIT EXECUTABLE")
        self.RegBT_BROWSE_XEDIT.setStyleSheet("background-color: lightyellow; border-radius: 5px; border: 1px solid gray;")
        self.RegBT_BROWSE_XEDIT.clicked.connect(self.select_file_xedit)  # type: ignore
        if "Edit" in PACT_config["MAIN"]["XEDIT EXE"]:
            self.RegBT_BROWSE_XEDIT.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")
            self.RegBT_BROWSE_XEDIT.setText("✔️ XEDIT EXECUTABLE SET")
            self.configured_XEDIT = True

        # SEPARATOR LINE 1
        self.LINE_SEPARATOR1 = QtWidgets.QFrame(PACT_WINDOW)
        self.LINE_SEPARATOR1.setGeometry(QtCore.QRect(80, 100, 480, 20))
        self.LINE_SEPARATOR1.setFrameShape(QtWidgets.QFrame.Shape.HLine)  # type: ignore
        self.LINE_SEPARATOR1.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)  # type: ignore
        self.LINE_SEPARATOR1.setObjectName("LINE_SEPARATOR1")

        # SEPARATOR TEXT 1
        self.LBL_SETTINGS1 = QtWidgets.QLabel(PACT_WINDOW)
        self.LBL_SETTINGS1.setGeometry(QtCore.QRect(50, 120, 550, 24))
        self.LBL_SETTINGS1.setText("YOU NEED TO SET YOUR LOAD ORDER FILE AND XEDIT EXECUTABLE BEFORE CLEANING")
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.LBL_SETTINGS1.setFont(font)
        self.LBL_SETTINGS1.setObjectName("LBL_NOTE_SET")

        # SEPARATOR TEXT 2
        self.LBL_SETTINGS2 = QtWidgets.QLabel(PACT_WINDOW)
        self.LBL_SETTINGS2.setGeometry(QtCore.QRect(120, 140, 550, 24))
        self.LBL_SETTINGS2.setText("( MOD ORGANIZER 2 USERS ALSO NEED TO SET MO2 EXECUTABLE )")
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.LBL_SETTINGS2.setFont(font)
        self.LBL_SETTINGS2.setObjectName("LBL_NOTE_MO2")

        # MAIN
        # Button - CLEAN PLUGINS
        self.RegBT_CLEAN_PLUGINS = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_CLEAN_PLUGINS.setGeometry(QtCore.QRect(245, 200, 150, 32))
        self.RegBT_CLEAN_PLUGINS.setObjectName("RegBT_CLEAN_PLUGINS")
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.RegBT_CLEAN_PLUGINS.setFont(font)
        self.RegBT_CLEAN_PLUGINS.setEnabled(False)  # type: ignore
        self.RegBT_CLEAN_PLUGINS.setText("START CLEANING")
        self.RegBT_CLEAN_PLUGINS.setStyleSheet("background-color: lightgray; border-radius: 5px; border: 1px solid gray;")  # type: ignore
        self.RegBT_CLEAN_PLUGINS.clicked.connect(self.start_cleaning)  # type: ignore

        # BOTTOM
        # Button - HELP
        self.RegBT_HELP = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_HELP.setGeometry(QtCore.QRect(20, 280, 110, 24))
        self.RegBT_HELP.setObjectName("RegBT_HELP")
        self.RegBT_HELP.setText("HELP")
        self.RegBT_HELP.setToolTip("How To Use PACT GUI")
        self.RegBT_HELP.clicked.connect(self.help_popup)  # type: ignore

        # Button - Check Updates
        self.RegBT_CHECKUPDATES = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_CHECKUPDATES.setGeometry(QtCore.QRect(245, 280, 150, 24))
        self.RegBT_CHECKUPDATES.setObjectName("RegBT_CHECKUPDATES")
        self.RegBT_CHECKUPDATES.setText("CHECK FOR UPDATES")
        self.RegBT_CHECKUPDATES.clicked.connect(self.update_popup)  # type: ignore

        # Button - EXIT
        self.RegBT_EXIT = QtWidgets.QPushButton(PACT_WINDOW)
        self.RegBT_EXIT.setGeometry(QtCore.QRect(510, 280, 110, 24))
        self.RegBT_EXIT.setObjectName("RegBT_EXIT")
        self.RegBT_EXIT.setText("EXIT")
        self.RegBT_EXIT.setToolTip("Exit PACT GUI")
        self.RegBT_EXIT.clicked.connect(PACT_WINDOW.close)  # type: ignore

    # ============== CLEAN PLUGINS BUTTON STATES ================

    def timed_states(self):
        xedit_procs = [proc for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'create_time']) if 'edit.exe' in proc.info['name'].lower()]
        xedit_running = False
        for proc in xedit_procs:
            if proc.info['name'].lower() == str(info.XEDIT_EXE).lower():
                xedit_running = True

        if self.thread is None:
            self.RegBT_BROWSE_LO.setEnabled(True)
            self.RegBT_BROWSE_MO2.setEnabled(True)
            self.RegBT_BROWSE_XEDIT.setEnabled(True)
            self.RegBT_EXIT.setEnabled(True)
            if self.configured_LO and self.configured_XEDIT and xedit_running is False:
                self.RegBT_CLEAN_PLUGINS.setEnabled(True)
                self.RegBT_CLEAN_PLUGINS.setText("START CLEANING")
                self.RegBT_CLEAN_PLUGINS.setStyleSheet("background-color: lightblue; border-radius: 5px; border: 1px solid gray;")
                self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
                self.RegBT_CLEAN_PLUGINS.clicked.connect(self.start_cleaning)
        else:
            self.RegBT_BROWSE_LO.setEnabled(False)
            self.RegBT_BROWSE_MO2.setEnabled(False)
            self.RegBT_BROWSE_XEDIT.setEnabled(False)
            self.RegBT_EXIT.setEnabled(False)
            thread = PactThread()
            if thread.cleaning_done is True:
                thread.finished_signal.connect(thread.quit)
                thread.finished_signal.connect(thread.wait)
                self.thread = None
            if "STOP CLEANING" not in self.RegBT_CLEAN_PLUGINS.text() and xedit_running is False:
                self.RegBT_CLEAN_PLUGINS.setText("START CLEANING")
                self.RegBT_CLEAN_PLUGINS.setStyleSheet("background-color: lightblue; border-radius: 5px; border: 1px solid gray;")

    def start_cleaning(self):
        if self.thread is None:
            self.thread = PactThread()
            self.thread.start()
            self.RegBT_CLEAN_PLUGINS.setText("STOP CLEANING")
            self.RegBT_CLEAN_PLUGINS.setStyleSheet("background-color: pink; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            self.RegBT_CLEAN_PLUGINS.clicked.disconnect()
            self.RegBT_CLEAN_PLUGINS.clicked.connect(self.stop_cleaning)

    def stop_cleaning(self):
        if self.thread is not None:
            self.thread.terminate()
            self.thread.wait()
            self.thread = None
            self.RegBT_CLEAN_PLUGINS.setEnabled(False)
            self.RegBT_CLEAN_PLUGINS.setText("...STOPPING...")
            self.RegBT_CLEAN_PLUGINS.setStyleSheet("background-color: orange; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            print("\n❌ CLEANING STOPPED! PLEASE WAIT UNTIL ALL RUNNING PROGRAMS ARE CLOSED BEFORE STARTING AGAIN!\n")

    # ================== POP-UPS / WARNINGS =====================
    # @staticmethod recommended for func that don't call "self".

    help_popup_msg = """If you have trouble running this program or wish to submit your PACT logs for additional help, join the Collective Modding Discord server.
    Please READ the #👋-welcome2 channel, react with the "2" emoji on the bot message there and leave your feedback in #💡-poet-guides-mods channel.
    Press OK to open the server link in your internet browser."""

    @staticmethod
    def help_popup():
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Question)  # type: ignore
        msgBox.setWindowTitle("Need Help?")
        msgBox.setText(UiPACTMainWin.help_popup_msg)  # RESERVED | msgBox.setInformativeText("...")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)  # type: ignore
        if msgBox.exec() != QtWidgets.QMessageBox.Cancel:  # type: ignore
            QDesktopServices.openUrl(QUrl("https://discord.com/invite/7ZZbrsGQh4"))

    @staticmethod
    def update_popup():
        if pact_update_check():
            QtWidgets.QMessageBox.information(PACT_WINDOW, "PACT Update", "You have the latest version of PACT!")
        else:
            QtWidgets.QMessageBox.warning(PACT_WINDOW, "PACT Update", "New PACT version is available!\nPress OK to open the PACT Nexus Page.")
            QDesktopServices.openUrl(QUrl("https://www.nexusmods.com/fallout4/mods/56255"))

    # ================= MAIN BUTTON FUNCTIONS ===================

    def select_file_lo(self):
        LO_file, _ = QFileDialog.getOpenFileName(filter="*.txt")  # type: ignore
        if os.path.exists(LO_file) and ("loadorder" in LO_file or "plugins" in LO_file):
            QtWidgets.QMessageBox.information(PACT_WINDOW, "New Load Order File Set", f"You have set the new path to: {LO_file} \n")  # type: ignore
            pact_ini_update("LoadOrder TXT", LO_file)
            self.RegBT_BROWSE_LO.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            self.RegBT_BROWSE_LO.setText("✔️ LOAD ORDER FILE SET")  # type: ignore
            self.configured_LO = True
        elif os.path.exists(LO_file) and "loadorder" not in LO_file and "plugins" not in LO_file:
            self.RegBT_BROWSE_LO.setStyleSheet("background-color: orange; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            self.RegBT_BROWSE_LO.setText("❌ WRONG LO FILE")  # type: ignore

    def select_file_mo2(self):
        MO2_EXE, _ = QFileDialog.getOpenFileName(filter="*.exe")  # type: ignore
        if os.path.exists(info.MO2_EXE):
            QtWidgets.QMessageBox.information(PACT_WINDOW, "New MO2 Executable Set", "You have set MO2 to: \n" + MO2_EXE)  # type: ignore
            pact_ini_update("MO2 EXE", MO2_EXE)
            self.RegBT_BROWSE_MO2.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            self.RegBT_BROWSE_MO2.setText("✔️ MO2 EXECUTABLE SET")  # type: ignore
            self.configured_MO2 = True

    def select_file_xedit(self):
        XEDIT_EXE, _ = QFileDialog.getOpenFileName(filter="*.exe")  # type: ignore
        if os.path.exists(XEDIT_EXE) and "edit" in XEDIT_EXE.lower():
            QtWidgets.QMessageBox.information(PACT_WINDOW, "New MO2 Executable Set", "You have set XEDIT to: \n" + XEDIT_EXE)  # type: ignore
            pact_ini_update("XEDIT EXE", XEDIT_EXE)
            self.RegBT_BROWSE_XEDIT.setStyleSheet("background-color: lightgreen; border-radius: 5px; border: 1px solid gray;")  # type: ignore
            self.RegBT_BROWSE_XEDIT.setText("✔️ XEDIT EXECUTABLE SET")  # type: ignore
            self.configured_XEDIT = True
        elif os.path.exists(XEDIT_EXE) and "edit" not in XEDIT_EXE.lower():
            self.RegBT_BROWSE_XEDIT.setText("❌ WRONG XEDIT EXE")  # type: ignore
            self.RegBT_BROWSE_XEDIT.setStyleSheet("background-color: orange; border-radius: 5px; border: 1px solid gray;")  # type: ignore


# CLEANING NEEDS A SEPARATE THREAD SO IT DOESN'T FREEZE PACT GUI
class PactThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaning_done = False

    def run(self):  # def Plugins_CLEAN():
        check_process_mo2()
        check_settings_paths()
        check_settings_integrity()
        while not self.cleaning_done:
            self.cleaning_done = clean_plugins()
            self.msleep(1000)


if __name__ == "__main__":
    gui_prompt = """\
-----
SET YOUR LOAD ORDER FILE AND XEDIT EXECUTABLE TO ENABLE CLEANING
     (MOD ORGANIZER 2 USERS ALSO NEED TO SET MO2 EXECUTABLE)

PRESS 'START CLEANING' BUTTON TO CLEAN ALL ACTIVE GAME PLUGINS
(IF REQUIRED FILES ARE SET, IT WILL ENABLE ITSELF IN 3 SECONDS)
-----
    """
    print(gui_prompt)
    app = QtWidgets.QApplication(sys.argv)
    PACT_WINDOW = QtWidgets.QDialog()
    ui = UiPACTMainWin()
    ui.setup_ui(PACT_WINDOW)
    PACT_WINDOW.show()
    sys.exit(app.exec())
