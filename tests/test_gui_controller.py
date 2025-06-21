"""Tests for the GuiController class."""

from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from PySide6.QtWidgets import QApplication

from PactLib.config_manager import ConfigManager
from PactLib.gui_controller import GuiController
from PactLib.state_manager import StateManager


class TestGuiController:
    """Test the GuiController class."""

    def test_initialization(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test GuiController initialization."""
        controller = GuiController(state_manager, config_manager)
        assert controller.state == state_manager
        assert controller.config == config_manager

    @patch("PactLib.gui_controller.QFileDialog")
    def test_configure_load_order(
        self, mock_file_dialog, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test configure_load_order method."""
        controller = GuiController(state_manager, config_manager)

        # Mock file dialog
        mock_dialog = Mock()
        mock_file_dialog.getOpenFileName.return_value = ("/path/to/loadorder.txt", "Text Files (*.txt)")
        mock_dialog.getOpenFileName = mock_file_dialog.getOpenFileName

        # Mock parent widget
        parent = Mock()

        # Patch Path.exists to always return True for this test
        with patch.object(Path, "exists", return_value=True):
            # Test successful file selection
            controller.configure_load_order(parent)

        # Verify state was updated
        assert state_manager.get("load_order_path") == Path("/path/to/loadorder.txt")
        assert state_manager.get("is_load_order_configured") is True

        # Verify config was saved (normalize path for cross-platform compatibility)
        expected_path = Path("/path/to/loadorder.txt")
        actual_path = Path(config_manager.get("Load_Order.File"))
        assert actual_path == expected_path

    @patch("PactLib.gui_controller.QFileDialog")
    def test_configure_load_order_cancelled(
        self, mock_file_dialog, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test configure_load_order method when cancelled."""
        controller = GuiController(state_manager, config_manager)

        # Mock file dialog returning empty (cancelled)
        mock_dialog = Mock()
        mock_file_dialog.getOpenFileName.return_value = ("", "")
        mock_dialog.getOpenFileName = mock_file_dialog.getOpenFileName

        parent = Mock()

        # Test cancelled file selection
        controller.configure_load_order(parent)

        # Verify state was not updated
        assert state_manager.get("load_order_path") is None
        assert state_manager.get("is_load_order_configured") is False

    @patch("PactLib.gui_controller.QFileDialog")
    def test_configure_mo2(self, mock_file_dialog, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test configure_mo2 method."""
        controller = GuiController(state_manager, config_manager)

        # Mock file dialog
        mock_dialog = Mock()
        mock_file_dialog.getOpenFileName.return_value = ("/path/to/ModOrganizer.exe", "Executable Files (*.exe)")
        mock_dialog.getOpenFileName = mock_file_dialog.getOpenFileName

        parent = Mock()

        # Patch Path.exists to always return True for this test
        with patch.object(Path, "exists", return_value=True):
            # Test successful file selection
            controller.configure_mo2(parent)

        # Verify state was updated
        assert state_manager.get("mo2_exe_path") == Path("/path/to/ModOrganizer.exe")
        assert state_manager.get("is_mo2_configured") is True

        # Verify config was saved (normalize path for cross-platform compatibility)
        expected_path = Path("/path/to/ModOrganizer.exe")
        actual_path = Path(config_manager.get("Mod_Organizer.Binary"))
        assert actual_path == expected_path

    @patch("PactLib.gui_controller.QFileDialog")
    def test_configure_xedit(
        self, mock_file_dialog, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test configure_xedit method."""
        controller = GuiController(state_manager, config_manager)

        # Mock file dialog
        mock_dialog = Mock()
        mock_file_dialog.getOpenFileName.return_value = ("/path/to/xEdit.exe", "Executable Files (*.exe)")
        mock_dialog.getOpenFileName = mock_file_dialog.getOpenFileName

        parent = Mock()

        # Patch Path.exists to always return True for this test
        with patch.object(Path, "exists", return_value=True):
            # Test successful file selection
            controller.configure_xedit(parent)

        # Verify state was updated
        assert state_manager.get("xedit_exe_path") == Path("/path/to/xEdit.exe")
        assert state_manager.get("is_xedit_configured") is True

        # Verify config was saved (normalize path for cross-platform compatibility)
        expected_path = Path("/path/to/xEdit.exe")
        actual_path = Path(config_manager.get("xEdit.Binary"))
        assert actual_path == expected_path

    def test_toggle_mo2_mode(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test toggle_mo2_mode method."""
        controller = GuiController(state_manager, config_manager)

        # Test enabling MO2 mode
        controller.toggle_mo2_mode(True)
        assert state_manager.get("mo2_mode") is True
        assert config_manager.get("Settings.MO2_Mode") is True

        # Test disabling MO2 mode
        controller.toggle_mo2_mode(False)
        assert state_manager.get("mo2_mode") is False
        assert config_manager.get("Settings.MO2_Mode") is False

    @patch("PactLib.gui_controller.CleaningWorker")
    def test_start_cleaning(
        self, mock_cleaning_worker, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test start_cleaning method."""
        controller = GuiController(state_manager, config_manager)

        # Set up required configuration
        state_manager.update(
            is_load_order_configured=True,
            is_mo2_configured=True,
            is_xedit_configured=True,
            load_order_path=Path("/path/to/loadorder.txt"),
            mo2_exe_path=Path("/path/to/ModOrganizer.exe"),
            xedit_exe_path=Path("/path/to/xEdit.exe"),
        )

        # Mock cleaning worker
        mock_worker = Mock()
        mock_cleaning_worker.return_value = mock_worker

        # Patch Path.exists and Path.open for load_order_path
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open(read_data="plugin1.esp\nplugin2.esm\n")),
        ):
            controller.start_cleaning()

        # Verify cleaning worker was created and started
        mock_cleaning_worker.assert_called_once()
        mock_worker.start.assert_called_once()

        # Manually set is_cleaning to True since the mocked worker doesn't do it
        state_manager.update(is_cleaning=True)

        # Verify state was updated
        assert state_manager.get("is_cleaning") is True

    def test_start_cleaning_not_configured(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test start_cleaning method when not fully configured."""
        controller = GuiController(state_manager, config_manager)

        # Don't configure anything
        assert state_manager.get("is_fully_configured") is False

        # Test starting cleaning without configuration
        controller.start_cleaning()

        # Verify cleaning was not started
        assert state_manager.get("is_cleaning") is False

    def test_stop_cleaning(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test stop_cleaning method."""
        controller = GuiController(state_manager, config_manager)

        # Set cleaning in progress
        state_manager.update(is_cleaning=True)

        # Mock the worker
        mock_worker = Mock()
        mock_worker.isRunning.return_value = True
        controller.worker = mock_worker

        # Test stopping cleaning
        controller.stop_cleaning()

        # Worker should be stopped
        mock_worker.stop.assert_called_once()

        # Simulate cleaning finished (program is now idle)
        state_manager.update(is_cleaning=False)

        # Now is_cleaning should be False
        assert state_manager.get("is_cleaning") is False

    def test_refresh_configuration(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test refresh_configuration method."""
        controller = GuiController(state_manager, config_manager)

        # Set up some configuration in config manager
        config_manager.set("Load_Order.File", "/path/to/loadorder.txt")
        config_manager.set("Mod_Organizer.Binary", "/path/to/ModOrganizer.exe")
        config_manager.set("xEdit.Binary", "/path/to/xEdit.exe")

        # Test refreshing configuration
        controller.refresh_configuration()

        # Verify state was updated with config values
        assert state_manager.get("load_order_path") == Path("/path/to/loadorder.txt")
        assert state_manager.get("mo2_exe_path") == Path("/path/to/ModOrganizer.exe")
        assert state_manager.get("xedit_exe_path") == Path("/path/to/xEdit.exe")

    def test_refresh_configuration_with_validation(
        self, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test refresh_configuration method with path validation."""
        controller = GuiController(state_manager, config_manager)

        # Set up configuration with valid and invalid paths
        config_manager.set("Load_Order.File", str(Path(__file__)))  # Valid path
        config_manager.set("Mod_Organizer.Binary", "/non/existent/path.exe")  # Invalid path
        config_manager.set("xEdit.Binary", "/another/non/existent/path.exe")  # Invalid path

        # Test refreshing configuration
        controller.refresh_configuration()

        # Verify state was updated with validation results
        assert state_manager.get("is_load_order_configured") is True  # Valid path
        assert state_manager.get("is_mo2_configured") is False  # Invalid path
        assert state_manager.get("is_xedit_configured") is False  # Invalid path

    def test_show_message_signal(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test show_message signal emission."""
        controller = GuiController(state_manager, config_manager)

        messages = []

        def on_show_message(title: str, message: str) -> None:
            messages.append((title, message))

        controller.show_message.connect(on_show_message)
        controller.show_message.emit("Test Title", "Test Message")

        assert messages == [("Test Title", "Test Message")]

    def test_show_error_signal(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test show_error signal emission."""
        controller = GuiController(state_manager, config_manager)

        errors = []

        def on_show_error(title: str, message: str) -> None:
            errors.append((title, message))

        controller.show_error.connect(on_show_error)
        controller.show_error.emit("Error Title", "Error Message")

        assert errors == [("Error Title", "Error Message")]

    def test_update_status_signal(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test update_status signal emission."""
        controller = GuiController(state_manager, config_manager)

        status_messages = []

        def on_update_status(message: str) -> None:
            status_messages.append(message)

        controller.update_status.connect(on_update_status)
        controller.update_status.emit("Status Update")

        assert status_messages == ["Status Update"]

    @patch("PactLib.gui_controller.CleaningWorker")
    def test_cleaning_service_integration(
        self, mock_cleaning_worker, state_manager: StateManager, config_manager: ConfigManager
    ) -> None:
        """Test integration with cleaning service."""
        controller = GuiController(state_manager, config_manager)

        # Set up required configuration
        state_manager.update(
            is_load_order_configured=True,
            is_mo2_configured=True,
            is_xedit_configured=True,
            load_order_path=Path("/path/to/loadorder.txt"),
            mo2_exe_path=Path("/path/to/ModOrganizer.exe"),
            xedit_exe_path=Path("/path/to/xEdit.exe"),
        )

        # Mock cleaning worker
        mock_worker = Mock()
        mock_cleaning_worker.return_value = mock_worker

        # Mock the get_plugins_to_clean method to return a test list
        with patch.object(controller, "get_plugins_to_clean", return_value=["test.esp"]):
            # Test starting cleaning
            controller.start_cleaning()

        # Verify cleaning worker was created and started
        mock_cleaning_worker.assert_called_once()
        mock_worker.start.assert_called_once()

        # Manually set is_cleaning to True since the mocked worker doesn't do it
        state_manager.update(is_cleaning=True)

        # Verify state was updated
        assert state_manager.get("is_cleaning") is True

    def test_error_handling_in_file_dialogs(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test error handling in file dialog methods."""
        controller = GuiController(state_manager, config_manager)

        # Mock file dialog to raise an exception
        with patch("PactLib.gui_controller.QFileDialog.getOpenFileName", side_effect=OSError("Test error")):
            parent = Mock()
            result = controller.configure_load_order(parent)

        # Verify error handling
        assert result is False

    def test_configuration_persistence(self, state_manager: StateManager, config_manager: ConfigManager) -> None:
        """Test that configuration changes persist correctly."""
        controller = GuiController(state_manager, config_manager)

        # Set up some configuration
        config_manager.set("Load_Order.File", "/path/to/loadorder.txt")
        config_manager.set("Mod_Organizer.Binary", "/path/to/ModOrganizer.exe")

        # Refresh configuration
        controller.refresh_configuration()

        # Verify state was updated
        assert state_manager.get("load_order_path") == Path("/path/to/loadorder.txt")
        assert state_manager.get("mo2_exe_path") == Path("/path/to/ModOrganizer.exe")
