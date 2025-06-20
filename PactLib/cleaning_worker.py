"""Worker thread for plugin cleaning operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from PactLib.cleaning_service import CleaningService
from PactLib.state_manager import StateManager

if TYPE_CHECKING:
    from PactLib.cleaning_service import CleaningService
    from PactLib.state_manager import StateManager

logger: logging.Logger = logging.getLogger(__name__)


class CleaningWorker(QThread):
    """Worker thread for cleaning plugins with clear signals."""

    # Signals
    progress = Signal(int, int)  # current, total
    plugin_started = Signal(str)  # plugin name
    plugin_completed = Signal(str, bool, str)  # plugin, success, message
    plugin_progress = Signal(dict)  # real-time progress info from cleaning
    log_output = Signal(str)  # real-time log output from xEdit
    finished = Signal()
    error = Signal(str)  # error message

    def __init__(
        self,
        service: CleaningService,
        state: StateManager,
        plugins: list[str],
    ) -> None:
        """Initialize the cleaning worker."""
        super().__init__()
        self.service: CleaningService = service
        self.state: StateManager = state
        self.plugins: list[str] = plugins
        self._should_stop = False

    def run(self) -> None:
        """
        Handles the execution of the cleaning process for plugins. The method validates
        the environment, sets up real-time callbacks for progress and log reporting,
        and manages the cleaning workflow for plugins with status updates and error
        handling. If the cleaning process is interrupted or encounters errors, the
        method ensures all necessary cleanup is performed before finishing.

        Raises:
            OSError: If an OS error occurs during plugin processing.
            RuntimeError: If an unexpected runtime error occurs during execution.
            ValueError: If an invalid value is encountered during operations.
        """
        try:
            # Validate environment first
            valid, message = self.service.validate_environment()
            if not valid:
                self.error.emit(message)
                return

            # Set up real-time callbacks for the cleaning service
            self.service.set_progress_callback(self._on_cleaning_progress)
            self.service.set_log_callback(self._on_log_output)

            # Update state
            self.state.update(
                is_cleaning=True,
                total_plugins=len(self.plugins),
                plugins_to_clean=self.plugins.copy(),
                progress=0,
            )

            # Process each plugin
            for i, plugin in enumerate(self.plugins):
                if self._should_stop:
                    logger.info("Cleaning stopped by user")
                    break

                # Update current plugin
                self.state.update(current_plugin=plugin)
                self.plugin_started.emit(plugin)

                # Clean the plugin with real-time monitoring
                result = self.service.clean_plugin(plugin)

                # Update results
                self.state.add_result(plugin, result.status, result.message)
                self.plugin_completed.emit(plugin, result.success, result.message)
                self.progress.emit(i + 1, len(self.plugins))

                logger.info(
                    f"Processed {plugin}: {result.status} "
                    f"({result.duration:.1f}s) - {result.message}"
                )

        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"Error in cleaning worker: {e}")
            self.error.emit(str(e))
        finally:
            # Reset cleaning state
            self.state.update(is_cleaning=False, current_plugin=None)
            self.finished.emit()

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True
        self.requestInterruption()

    def _on_cleaning_progress(self, progress_info: dict) -> None:
        """Handle real-time progress updates from cleaning service."""
        # Emit the progress signal with detailed information
        self.plugin_progress.emit(progress_info)

    def _on_log_output(self, log_line: str) -> None:
        """Handle real-time log output from xEdit process."""
        # Emit the log output signal
        self.log_output.emit(log_line)

    def get_summary(self) -> str:
        """
        Constructs and returns a summary of cleaning statistics from the system state.

        This method retrieves the cleaning statistics from the system's state and formats
        them into a human-readable summary. The returned summary includes information
        about cleaned, failed, and skipped items, the total count, and entries handled
        via QuickAutoClean. The statistics are sourced from the `cleaning_stats` data
        within the system's state.

        Returns:
            str: A formatted string representing the summary of cleaning statistics.
        """
        stats = self.state.state.cleaning_stats
        return (
            f"Cleaning complete:\n"
            f"  Cleaned: {stats['cleaned']}\n"
            f"  Failed: {stats['failed']}\n"
            f"  Skipped: {stats['skipped']}\n"
            f"  QuickAutoClean: {stats['quickautoclean']}\n"
            f"  Total: {stats['total']}"
        )