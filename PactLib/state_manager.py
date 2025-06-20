"""Centralized state management for XEdit-PACT."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QMutex, QMutexLocker, QObject, Signal

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class AppState:
    """Single source of truth for all application state."""

    # Configuration state
    load_order_path: Path | None = None
    mo2_exe_path: Path | None = None
    mo2_install_path: Path | None = None
    xedit_exe_path: Path | None = None
    xedit_install_path: Path | None = None

    # Configuration validity
    is_load_order_configured: bool = False
    is_mo2_configured: bool = False
    is_xedit_configured: bool = False

    # Runtime state
    is_cleaning: bool = False
    current_plugin: str | None = None
    current_operation: str = ""

    # Progress state
    progress: int = 0
    total_plugins: int = 0
    plugins_to_clean: list[str] = field(default_factory=list)

    # Results
    cleaned_plugins: set[str] = field(default_factory=set)
    failed_plugins: set[str] = field(default_factory=set)
    skipped_plugins: set[str] = field(default_factory=set)
    quickautoclean_plugins: set[str] = field(default_factory=set)

    # Settings
    journal_expiration: int = 7
    cleaning_timeout: int = 300
    cpu_threshold: int = 5
    mo2_mode: bool = False
    game_type: str | None = None

    @property
    def is_fully_configured(self) -> bool:
        """Check if all required configuration is present."""
        return all(
            [
                self.is_load_order_configured,
                self.is_mo2_configured,
                self.is_xedit_configured,
            ]
        )

    @property
    def cleaning_stats(self) -> dict[str, int]:
        """Get current cleaning statistics."""
        return {
            "cleaned": len(self.cleaned_plugins),
            "failed": len(self.failed_plugins),
            "skipped": len(self.skipped_plugins),
            "quickautoclean": len(self.quickautoclean_plugins),
            "total": self.total_plugins,
        }


class StateManager(QObject):
    """Thread-safe state manager with Qt signals."""

    # Signals for state changes
    state_changed: Signal = Signal(str, object)  # (property_name, new_value)
    configuration_changed: Signal = Signal(bool)  # is_fully_configured
    progress_changed: Signal = Signal(int, int)  # current, total
    cleaning_started: Signal = Signal()
    cleaning_finished: Signal = Signal()
    plugin_processed: Signal = Signal(str, str, str)  # plugin, status, message

    def __init__(self) -> None:
        """Initialize the state manager."""
        super().__init__()
        self._state = AppState()
        self._mutex = QMutex()

    def update(self, **kwargs: Any) -> None:
        """Update state properties and emit appropriate signals."""
        with QMutexLocker(self._mutex):
            config_changed = False
            progress_changed = False

            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    old_value = getattr(self._state, key)
                    if old_value != value:
                        setattr(self._state, key, value)
                        self.state_changed.emit(key, value)

                        # Check for specific state changes
                        if key in ["is_load_order_configured", "is_mo2_configured", "is_xedit_configured"]:
                            config_changed = True
                        elif key in ["progress", "total_plugins"]:
                            progress_changed = True
                        elif key == "is_cleaning":
                            if value:
                                self.cleaning_started.emit()
                            else:
                                self.cleaning_finished.emit()

            # Emit aggregate signals
            if config_changed:
                self.configuration_changed.emit(self._state.is_fully_configured)
            if progress_changed:
                self.progress_changed.emit(self._state.progress, self._state.total_plugins)

    def get(self, property_name: str, default: Any = None) -> Any:
        """Get a state property value safely."""
        with QMutexLocker(self._mutex):
            return getattr(self._state, property_name, default)

    @property
    def state(self) -> AppState:
        """Get a snapshot of the current state."""
        with QMutexLocker(self._mutex):
            return replace(self._state)

    def add_result(self, plugin: str, status: str, message: str = "") -> None:
        """Add a plugin processing result."""
        with QMutexLocker(self._mutex):
            if status == "cleaned":
                self._state.cleaned_plugins.add(plugin)
            elif status == "failed":
                self._state.failed_plugins.add(plugin)
            elif status == "skipped":
                self._state.skipped_plugins.add(plugin)
            elif status == "quickautoclean":
                self._state.quickautoclean_plugins.add(plugin)

            self._state.progress += 1
            self.plugin_processed.emit(plugin, status, message)
            self.progress_changed.emit(self._state.progress, self._state.total_plugins)

    def reset_cleaning_state(self) -> None:
        """Reset all cleaning-related state."""
        with QMutexLocker(self._mutex):
            self._state.is_cleaning = False
            self._state.current_plugin = None
            self._state.current_operation = ""
            self._state.progress = 0
            self._state.total_plugins = 0
            self._state.plugins_to_clean.clear()
            self._state.cleaned_plugins.clear()
            self._state.failed_plugins.clear()
            self._state.skipped_plugins.clear()
            self._state.quickautoclean_plugins.clear()

    def update_configuration_paths(
        self,
        load_order_path: Path | None = None,
        mo2_exe_path: Path | None = None,
        mo2_install_path: Path | None = None,
        xedit_exe_path: Path | None = None,
        xedit_install_path: Path | None = None,
    ) -> None:
        """Update configuration paths and validity flags."""
        updates: dict[str, Any] = {}

        if load_order_path is not None:
            updates["load_order_path"] = load_order_path
            updates["is_load_order_configured"] = load_order_path.exists()

        if mo2_exe_path is not None:
            updates["mo2_exe_path"] = mo2_exe_path
            updates["is_mo2_configured"] = mo2_exe_path.exists()
            if mo2_install_path:
                updates["mo2_install_path"] = mo2_install_path

        if xedit_exe_path is not None:
            updates["xedit_exe_path"] = xedit_exe_path
            updates["is_xedit_configured"] = xedit_exe_path.exists()
            if xedit_install_path:
                updates["xedit_install_path"] = xedit_install_path

        if updates:
            self.update(**updates)