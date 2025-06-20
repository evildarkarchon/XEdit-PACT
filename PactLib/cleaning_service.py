"""Business logic for plugin cleaning operations."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from logging import Logger
from typing import TYPE_CHECKING, Any, Callable

from PactLib.state_manager import AppState
from PactLib.utils import detect_xedit_game, run_process_with_realtime_output

if TYPE_CHECKING:
    from re import Pattern

    from PactLib.config_manager import ConfigManager
    from PactLib.state_manager import AppState, StateManager


logger: Logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    """Result of a plugin cleaning operation."""

    success: bool
    message: str
    status: str  # "cleaned", "failed", "skipped", "quickautoclean"
    duration: float = 0.0


class CleaningService:
    """Pure business logic for plugin cleaning - no Qt dependencies."""

    def __init__(self, config: ConfigManager, state: StateManager) -> None:
        """Initialize the cleaning service."""
        self.config = config
        self.state = state
        self.progress_callback: Callable | None = None
        self.log_callback: Callable | None = None

    def set_progress_callback(self, callback: Callable | None) -> None:
        """
        Sets the progress callback to monitor or handle progress updates during an operation.
        The callback function will be called whenever progress changes.

        Args:
            callback (Callable | None): A function to handle progress updates. If provided,
                the function should take necessary parameters as required for processing the progress
                information. If None, no progress updates will be processed.
        """
        self.progress_callback = callback

    def set_log_callback(self, callback: Callable | None) -> None:
        """
        Sets a callback function for logging events.

        This method allows the user to set a callable function that will be used for
        logging purposes. If no callback is provided or if `None` is passed, the
        logging callback will be disabled.

        Args:
            callback (Callable | None): A callable function to handle logging events,
                or `None` to disable the logging callback.
        """
        self.log_callback = callback

    def clean_plugin(self, plugin_name: str) -> CleanResult:
        """
        Cleans a specified plugin by performing either a normal cleaning or a quick auto
        cleaning based on the current application state. If the plugin is in the skip
        list, it is skipped. Errors encountered during the cleaning process are logged
        and appropriately handled.

        Args:
            plugin_name: The name of the plugin to be cleaned.

        Returns:
            CleanResult: An object representing the result of the cleaning operation. It
            contains the success status, an optional message, the operation status
            (e.g., "skipped", "failed"), and the time duration of the cleaning process.
        """
        start_time: float = time.time()

        try:
            # Get current state
            state_snapshot: AppState = self.state.state

            # Check if plugin should be skipped
            if self._should_skip_plugin(plugin_name, state_snapshot.game_type):
                return CleanResult(
                    success=True,
                    message=f"Skipped {plugin_name} (in skip list)",
                    status="skipped",
                    duration=time.time() - start_time,
                )

            # Check if plugin needs QuickAutoClean
            if self._needs_quickautoclean(plugin_name, state_snapshot.game_type):
                return self._run_quickautoclean(plugin_name, state_snapshot)

            # Run normal cleaning
            return self._run_normal_clean(plugin_name, state_snapshot)

        except (OSError, RuntimeError, ValueError, KeyError) as e:
            logger.error(f"Error cleaning {plugin_name}: {e}")
            return CleanResult(
                success=False,
                message=f"Error cleaning {plugin_name}: {e!s}",
                status="failed",
                duration=time.time() - start_time,
            )

    def _should_skip_plugin(self, plugin_name: str, game_type: str | None) -> bool:
        """Check if plugin should be skipped."""
        if not game_type:
            return False

        game_config: dict[str, Any] = self.config.get_game_config(game_type)
        skip_list: list[str] = game_config.get("skip_list", [])

        # Also check universal skip list
        universal_skip: list[str] = self.config.get("PACT_Data.Skip_Lists.Universal", [])

        return plugin_name.lower() in [p.lower() for p in skip_list + universal_skip]

    def _needs_quickautoclean(self, plugin_name: str, game_type: str | None) -> bool:
        """Check if plugin needs QuickAutoClean."""
        if not game_type:
            return False

        game_config: dict[str, Any] = self.config.get_game_config(game_type)
        qac_list: list[str] = game_config.get("quickautoclean_list", [])

        # Also check universal QAC list
        universal_qac: list[str] = self.config.get("PACT_Data.QAC_Lists.Universal", [])

        return plugin_name.lower() in [p.lower() for p in qac_list + universal_qac]

    def _run_quickautoclean(self, plugin_name: str, state_snapshot: AppState) -> CleanResult:
        """Run QuickAutoClean on a plugin."""
        logger.info(f"Running QuickAutoClean on {plugin_name}")

        command: list[str] = self._build_cleaning_command(
            plugin_name,
            state_snapshot,
            quickautoclean=True,
        )

        result: CleanResult = self._execute_cleaning_command(command, plugin_name, state_snapshot.cleaning_timeout)

        if result.success:
            return CleanResult(
                success=True,
                message=f"QuickAutoClean completed for {plugin_name}",
                status="quickautoclean",
                duration=result.duration,
            )
        return result

    def _run_normal_clean(self, plugin_name: str, state_snapshot: AppState) -> CleanResult:
        """Run normal cleaning on a plugin."""
        logger.info(f"Running normal clean on {plugin_name}")

        command: list[str] = self._build_cleaning_command(
            plugin_name,
            state_snapshot,
            quickautoclean=False,
        )

        result: CleanResult = self._execute_cleaning_command(command, plugin_name, state_snapshot.cleaning_timeout)

        if result.success:
            result.status = "cleaned"

        return result

    def _build_cleaning_command(
        self, plugin_name: str, state_snapshot: AppState, quickautoclean: bool = False
    ) -> list[str]:
        """Build the command to clean a plugin."""
        command: list[str] = []

        # Add MO2 if in MO2 mode
        if state_snapshot.mo2_mode and state_snapshot.mo2_exe_path:
            command.extend([str(state_snapshot.mo2_exe_path), "moshell", "run"])

        # Add xEdit executable
        command.append(str(state_snapshot.xedit_exe_path))

        # Add arguments
        if quickautoclean:
            command.extend(["-quickautoclean", "-autoload"])
        else:
            command.extend(["-autoclean", "-autoload"])

        # Add plugin name
        command.append(plugin_name)

        return command

    def _execute_cleaning_command(self, command: list[str], plugin_name: str, timeout: int) -> CleanResult:
        """Execute the cleaning command with real-time monitoring."""
        start_time: float = time.time()

        try:
            # Prepare progress tracking variables
            self._current_plugin = plugin_name
            self._cleaning_stats = {
                "undeleted": 0,
                "removed": 0,
                "skipped": 0,
                "partial_forms": 0,
                "total_processed": 0,
            }

            # Create output callback for real-time monitoring
            def on_output_line(line: str) -> None:
                """Handle real-time output from xEdit process."""
                if self.log_callback:
                    self.log_callback(line)

                # Parse line for cleaning statistics and progress
                self._parse_cleaning_output(line, plugin_name)

            # Execute command with real-time monitoring
            logger.info(f"Executing command: {' '.join(command)}")
            exit_code, _, stderr = run_process_with_realtime_output(
                command=command, output_callback=on_output_line, timeout=timeout, working_dir=None
            )

            duration: float = time.time() - start_time

            # Check result
            if exit_code == 0:
                stats_summary: str = self._get_cleaning_summary()
                return CleanResult(
                    success=True,
                    message=f"Successfully cleaned {plugin_name}{stats_summary}",
                    status="cleaned",
                    duration=duration,
                )
            if exit_code == -1:
                # Timeout or other error
                timeout_error_msg: str = stderr.strip() if stderr else "Process failed or timed out"
                return CleanResult(
                    success=False,
                    message=f"Failed to clean {plugin_name}: {timeout_error_msg}",
                    status="failed",
                    duration=duration,
                )
            # Non-zero exit code
            exit_error_msg: str = stderr.strip() if stderr else f"Process exited with code {exit_code}"
            return CleanResult(
                success=False,
                message=f"Failed to clean {plugin_name}: {exit_error_msg}",
                status="failed",
                duration=duration,
            )

        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError) as e:
            logger.error(f"Error executing cleaning command for {plugin_name}: {e}")
            return CleanResult(
                success=False,
                message=f"Error cleaning {plugin_name}: {e!s}",
                status="failed",
                duration=time.time() - start_time,
            )

    def _parse_cleaning_output(self, line: str, plugin_name: str) -> None:
        """Parse xEdit output line for cleaning statistics and progress."""
        import re  # noqa: PLC0415

        # Pattern matching for xEdit cleaning operations
        patterns: dict[str, Pattern[str]] = {
            "undeleted": re.compile(r"Undeleting:\s*(.*)", re.IGNORECASE),
            "removed": re.compile(r"Removing:\s*(.*)", re.IGNORECASE),
            "skipped": re.compile(r"Skipping:\s*(.*)", re.IGNORECASE),
            "partial_forms": re.compile(r"Making Partial Form:\s*(.*)", re.IGNORECASE),
        }

        # Check each pattern and update stats
        for stat_type, pattern in patterns.items():
            if pattern.search(line):
                self._cleaning_stats[stat_type] += 1
                self._cleaning_stats["total_processed"] += 1

                # Emit progress update if callback is set
                if self.progress_callback:
                    progress_info: dict[str, Any] = {
                        "plugin": plugin_name,
                        "action": stat_type,
                        "line": line.strip(),
                        "stats": self._cleaning_stats.copy(),
                    }
                    self.progress_callback(progress_info)
                break

        # Check for completion indicators
        if ("Done." in line or "Cleaning completed" in line) and self.progress_callback:
            completion_info: dict[str, Any] = {
                "plugin": plugin_name,
                "action": "completed",
                "line": line.strip(),
                "stats": self._cleaning_stats.copy(),
            }
            self.progress_callback(completion_info)

    def _get_cleaning_summary(self) -> str:
        """Generate a summary of cleaning statistics."""
        stats: dict[str, int] = self._cleaning_stats
        if stats["total_processed"] == 0:
            return ""

        summary_parts: list[Any] = []
        if stats["undeleted"] > 0:
            summary_parts.append(f"{stats['undeleted']} undeleted")
        if stats["removed"] > 0:
            summary_parts.append(f"{stats['removed']} removed")
        if stats["skipped"] > 0:
            summary_parts.append(f"{stats['skipped']} skipped")
        if stats["partial_forms"] > 0:
            summary_parts.append(f"{stats['partial_forms']} partial forms")

        if summary_parts:
            return f" ({', '.join(summary_parts)})"
        return f" ({stats['total_processed']} items processed)"

    def validate_environment(self) -> tuple[bool, str]:
        """
        Validates the application environment, ensuring all paths, required executables,
        and configurations are appropriately set. This function performs the following checks:

        1. Verifies that all required paths are configured.
        2. Ensures the xEdit executable exists and is properly set.
        3. Attempts to auto-detect the game type if not already specified.
        4. Confirms the presence of the MO2 executable if operating in MO2 mode.

        Returns a tuple indicating the validation status and an associated message.

        Returns:
            tuple[bool, str]: A tuple where the first element signifies the success
                (True for valid environment, False otherwise) and the second element
                contains a detailed message explaining the result of the validation.
        """
        state_snapshot: AppState = self.state.state

        # Check configuration
        if not state_snapshot.is_fully_configured:
            return False, "Not all paths are configured"

        # Check xEdit executable
        if not state_snapshot.xedit_exe_path or not state_snapshot.xedit_exe_path.exists():
            return False, "xEdit executable not found"

        # Detect game type if not set
        if not state_snapshot.game_type:
            game_type: str | None = detect_xedit_game(str(state_snapshot.xedit_exe_path))
            if game_type:
                self.state.update(game_type=game_type)
            else:
                # For generic xEdit executables (xEdit.exe, xEdit64.exe),
                # we can't auto-detect game type, but we can still proceed
                logger.warning(
                    "Could not auto-detect game type from xEdit executable. "
                    "For generic xEdit executables, game type may need to be set manually."
                )

        # Check MO2 if in MO2 mode
        if state_snapshot.mo2_mode and (not state_snapshot.mo2_exe_path or not state_snapshot.mo2_exe_path.exists()):
            return False, "MO2 executable not found (required in MO2 mode)"

        return True, "Environment validated successfully"
