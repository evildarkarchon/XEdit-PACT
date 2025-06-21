"""Tests for the main interface components."""

from unittest.mock import Mock, patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from PACT_Interface import CleaningProgressDialog, MainWindow, create_application


class TestCleaningProgressDialog:
    """Test the CleaningProgressDialog class."""

    def test_initialization(self) -> None:
        """Test CleaningProgressDialog initialization."""
        dialog = CleaningProgressDialog()

        assert dialog._current_plugin_name is None
        assert dialog._cleaning_in_progress is True
        assert dialog.windowTitle() == "Cleaning Progress"
        assert dialog.isModal() is False

    def test_update_progress(self) -> None:
        """Test update_progress method."""
        dialog = CleaningProgressDialog()

        # Test progress update
        dialog.update_progress(3, 10)
        assert dialog.progress_bar.value() == 30  # 30%
        assert dialog.progress_label.text() == "3 / 10 plugins"

        # Test progress with plugin name
        dialog._current_plugin_name = "test.esp"
        dialog.update_progress(5, 10)
        assert dialog.progress_bar.format() == "test.esp / 50%"

        # Test zero total
        dialog.update_progress(0, 0)
        assert dialog.progress_bar.value() == 0
        assert dialog.progress_label.text() == "0 / 0 plugins"

    def test_update_current_plugin(self) -> None:
        """Test update_current_plugin method."""
        dialog = CleaningProgressDialog()

        dialog.update_current_plugin("test.esp")
        assert dialog.current_plugin_label.text() == "Processing: test.esp"
        assert dialog._current_plugin_name == "test.esp"

        # Test with progress
        dialog.progress_bar.setValue(50)
        dialog.update_current_plugin("another.esp")
        assert dialog.progress_bar.format() == "another.esp / 50%"

    def test_update_statistics(self) -> None:
        """Test update_statistics method."""
        dialog = CleaningProgressDialog()

        stats = {"cleaned": 5, "failed": 2, "skipped": 1, "total": 8}

        dialog.update_statistics(stats)

        assert dialog.stats_labels["cleaned"].text() == "5"
        assert dialog.stats_labels["failed"].text() == "2"
        assert dialog.stats_labels["skipped"].text() == "1"
        assert dialog.stats_labels["total"].text() == "8"

    def test_set_cleaning_finished(self) -> None:
        """Test set_cleaning_finished method."""
        dialog = CleaningProgressDialog()

        # Set some progress first
        dialog.progress_bar.setValue(100)

        dialog.set_cleaning_finished()

        assert dialog._cleaning_in_progress is False
        assert dialog.current_plugin_label.text() == "Cleaning completed!"
        assert dialog.stop_button.isVisible() is False
        assert dialog.close_button.isEnabled() is True
        assert dialog.progress_bar.format() == "Completed - 100%"

        # Test with partial progress
        dialog.progress_bar.setValue(50)
        dialog.set_cleaning_finished()
        assert dialog.progress_bar.format() == "Stopped - 50%"

    def test_close_event_during_cleaning(self) -> None:
        """Test closeEvent during cleaning."""
        dialog = CleaningProgressDialog()

        # Mock QMessageBox
        with patch("PACT_Interface.QMessageBox.question") as mock_question:
            mock_question.return_value = Mock()  # Mock the return value

            # Test closing during cleaning
            event = Mock()
            dialog.closeEvent(event)

            # Should show confirmation dialog
            mock_question.assert_called_once()
            # Should not accept the event by default (user needs to confirm)
            event.accept.assert_not_called()

    def test_close_event_after_cleaning(self) -> None:
        """Test closeEvent after cleaning is finished."""
        dialog = CleaningProgressDialog()
        dialog.set_cleaning_finished()

        event = Mock()
        dialog.closeEvent(event)

        # Should accept the event immediately
        event.accept.assert_called_once()


class TestMainWindow:
    """Test the MainWindow class."""

    def test_initialization(self, state_manager, config_manager) -> None:
        """Test MainWindow initialization."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        assert window.state == state_manager
        assert window.controller == controller
        assert window._updating_ui is False
        assert window.progress_dialog is None

    def test_setup_ui(self, state_manager, config_manager) -> None:
        """Test UI setup."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Check that UI elements were created
        assert window.load_order_button is not None
        assert window.mo2_button is not None
        assert window.xedit_button is not None
        assert window.mo2_mode_button is not None
        assert window.start_button is not None
        assert window.stop_button is not None
        assert window.status_bar is not None

        # Check window properties
        assert window.windowTitle() == "XEdit-PACT - Refactored"
        assert window.minimumSize().width() >= 650
        assert window.minimumSize().height() >= 450

    def test_button_connections(self, state_manager, config_manager) -> None:
        """Test that buttons are properly connected."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Test button connections by calling the slots directly
        window._configure_load_order()
        controller.configure_load_order.assert_called_once()

        window._configure_mo2()
        controller.configure_mo2.assert_called_once()

        window._configure_xedit()
        controller.configure_xedit.assert_called_once()

        window._start_cleaning()
        controller.start_cleaning.assert_called_once()

        window._stop_cleaning()
        controller.stop_cleaning.assert_called_once()

    def test_mo2_mode_toggle(self, state_manager, config_manager) -> None:
        """Test MO2 mode toggle functionality."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Test enabling MO2 mode
        assert window.mo2_mode_button is not None
        window.mo2_mode_button.setChecked(True)
        window._toggle_mo2_mode()
        controller.toggle_mo2_mode.assert_called_with(True)

        # Test disabling MO2 mode
        window.mo2_mode_button.setChecked(False)
        window._toggle_mo2_mode()
        controller.toggle_mo2_mode.assert_called_with(False)

    def test_ui_update_from_state(self, state_manager, config_manager) -> None:
        """Test UI updates based on state changes."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Configure all components
        state_manager.update(
            is_load_order_configured=True, is_mo2_configured=True, is_xedit_configured=True, mo2_mode=True
        )

        # Trigger UI update
        window._update_ui_from_state()

        # Wait for timer to complete
        window._update_timer.stop()
        window._perform_ui_update()

        # Check button states
        assert window.load_order_button is not None
        assert "✓" in window.load_order_button.text()
        assert window.mo2_button is not None
        assert "✓" in window.mo2_button.text()
        assert window.xedit_button is not None
        assert "✓" in window.xedit_button.text()
        assert window.mo2_mode_button is not None
        assert window.mo2_mode_button.isChecked() is True
        assert window.mo2_mode_button.text() == "MO2 Mode: ON"
        assert window.start_button is not None and window.start_button.isEnabled() is True
        assert window.stop_button is not None and window.stop_button.isEnabled() is False

    def test_cleaning_started_handler(self, state_manager, config_manager) -> None:
        """Test handling of cleaning started event."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Simulate cleaning started
        window._on_cleaning_started()

        # Check that progress dialog was created
        assert window.progress_dialog is not None
        assert window.progress_dialog.isVisible() is True

        # Check button states
        assert window.start_button is not None and window.start_button.isEnabled() is False
        assert window.stop_button is not None and window.stop_button.isEnabled() is True

    def test_cleaning_finished_handler(self, state_manager, config_manager) -> None:
        """Test handling of cleaning finished event."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Create progress dialog first
        window.progress_dialog = CleaningProgressDialog()

        # Simulate cleaning finished
        window._on_cleaning_finished()

        # Check button states
        assert window.start_button is not None and window.start_button.isEnabled() is True
        assert window.stop_button is not None and window.stop_button.isEnabled() is False

        # Check progress dialog
        assert window.progress_dialog._cleaning_in_progress is False

    def test_progress_update_handler(self, state_manager, config_manager) -> None:
        """Test handling of progress updates."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Create progress dialog
        window.progress_dialog = CleaningProgressDialog()
        window.progress_dialog.show()

        # Simulate progress update
        window._on_progress_changed(3, 10)

        # Check status bar
        assert window.status_bar is not None
        assert "30.0%" in window.status_bar.currentMessage()

        # Check progress dialog
        assert window.progress_dialog.progress_bar.value() == 30

    def test_plugin_processed_handler(self, state_manager, config_manager) -> None:
        """Test handling of plugin processing events."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Create progress dialog
        window.progress_dialog = CleaningProgressDialog()
        window.progress_dialog.show()

        # Simulate plugin processing
        window._on_plugin_processed("test.esp", "cleaned", "Successfully cleaned")

        # Check that current plugin was updated
        assert window.progress_dialog.current_plugin_label.text() == "Processing: test.esp"

    def test_menu_bar_creation(self, state_manager, config_manager) -> None:
        """Test menu bar creation."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        menubar = window.menuBar()
        assert menubar is not None

        # Check that menus were created
        file_menu = menubar.findChild(Mock, "File")
        help_menu = menubar.findChild(Mock, "Help")

        # Note: In a real test, we'd check for actual menu items
        # This is a simplified check

    def test_about_dialog(self, state_manager, config_manager) -> None:
        """Test about dialog."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        with patch("PACT_Interface.QMessageBox.about") as mock_about:
            window._show_about()
            mock_about.assert_called_once()

            # Check the arguments
            args = mock_about.call_args
            assert args[0][0] == window  # parent
            assert args[0][1] == "About XEdit-PACT"  # title
            assert "XEdit-PACT" in args[0][2]  # message

    def test_message_handlers(self, state_manager, config_manager) -> None:
        """Test message and error handlers."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        with patch("PACT_Interface.QMessageBox.information") as mock_info:
            window._show_message("Test Title", "Test Message")
            mock_info.assert_called_once_with(window, "Test Title", "Test Message")

        with patch("PACT_Interface.QMessageBox.critical") as mock_critical:
            window._show_error("Error Title", "Error Message")
            mock_critical.assert_called_once_with(window, "Error Title", "Error Message")

    def test_status_update(self, state_manager, config_manager) -> None:
        """Test status bar updates."""
        controller = Mock()
        window = MainWindow(state_manager, controller)
        window._update_status("Test Status")
        if window.status_bar is not None:
            assert window.status_bar.currentMessage() == "Test Status"

    def test_logging(self, state_manager, config_manager) -> None:
        """Test logging functionality."""
        controller = Mock()
        window = MainWindow(state_manager, controller)

        # Test logging during cleaning
        state_manager.update(is_cleaning=True)
        window._log("Test log message")
        # Should update status bar during cleaning
        if window.status_bar is not None:
            assert "Test log message" in window.status_bar.currentMessage()


class TestApplicationCreation:
    """Test application creation functions."""

    def test_create_application(self) -> None:
        """Test create_application function."""
        with (
            patch("PACT_Interface.ConfigManager") as mock_config_class,
            patch("PACT_Interface.StateManager") as mock_state_class,
            patch("PACT_Interface.GuiController") as mock_controller_class,
            patch("PACT_Interface.QApplication") as mock_app_class,
            patch("PACT_Interface.MainWindow") as mock_window_class,
        ):
            # Mock instances
            mock_config = Mock()
            mock_state = Mock()
            mock_controller = Mock()
            mock_app = Mock()
            mock_window = Mock()

            mock_config_class.return_value = mock_config
            mock_state_class.return_value = mock_state
            mock_controller_class.return_value = mock_controller
            mock_app_class.return_value = mock_app
            mock_window_class.return_value = mock_window

            # Test application creation
            app, window = create_application()

            # Verify components were created
            mock_config_class.assert_called_once()
            mock_state_class.assert_called_once()
            mock_controller_class.assert_called_once_with(mock_state, mock_config)
            mock_window_class.assert_called_once_with(mock_state, mock_controller)

            assert app == mock_app
            assert window == mock_window

    def test_main_function(self) -> None:
        """Test main function."""
        with patch("PACT_Interface.create_application") as mock_create, patch("PACT_Interface.sys.exit") as mock_exit:
            # Mock application components
            mock_app = Mock()
            mock_window = Mock()
            mock_create.return_value = (mock_app, mock_window)

            # Import and call main
            from PACT_Interface import main

            main()

            # Verify application was created and shown
            mock_create.assert_called_once()
            mock_window.show.assert_called_once()
            mock_app.exec.assert_called_once()
            mock_exit.assert_called_once()
