"""Pytest configuration and common fixtures for AutoQAC tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from PySide6.QtCore import QCoreApplication

from AutoQACLib.config_manager import ConfigManager
from AutoQACLib.logging_config import setup_test_logging
from AutoQACLib.state_manager import StateManager


@pytest.fixture(scope="session")
def qt_app() -> Generator[QCoreApplication, None, None]:
    """Create a Qt application for testing."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app
    app.quit()


@pytest.fixture
def temp_config_file() -> Generator[Path, None, None]:
    """Create a temporary configuration file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        config_path = Path(f.name)

    yield config_path

    # Cleanup
    config_path.unlink(missing_ok=True)


@pytest.fixture
def config_manager(temp_config_file: Path) -> ConfigManager:
    """Create a ConfigManager instance with a temporary config file."""
    return ConfigManager(temp_config_file)


@pytest.fixture
def state_manager() -> StateManager:
    """Create a StateManager instance for testing."""
    return StateManager()


@pytest.fixture
def sample_config_data() -> dict:
    """Provide sample configuration data for testing."""
    return {
        "AutoQAC_Data": {
            "Skip_Lists": {
                "Skyrim": ["Skyrim.esm", "Update.esm", "Dawnguard.esm"],
                "Fallout4": ["Fallout4.esm", "DLCRobot.esm"],
            },
            "XEdit_Lists": {
                "Skyrim": ["Skyrim.esm", "Update.esm"],
                "Fallout4": ["Fallout4.esm"],
            },
        },
        "Settings": {
            "Partial_Forms": False,
            "MO2_Mode": False,
        },
    }


@pytest.fixture
def sample_plugin_list() -> list[str]:
    """Sample list of plugins for testing."""
    return [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
        "Unofficial Skyrim Patch.esp",
        "TestPlugin1.esp",
        "TestPlugin2.esp",
    ]


# Configure logging for tests
@pytest.fixture(autouse=True)
def setup_logging() -> None:
    """Setup logging for tests with file output."""
    setup_test_logging()
