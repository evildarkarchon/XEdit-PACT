"""Pytest configuration and common fixtures for XEdit-PACT tests."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from PySide6.QtCore import QCoreApplication

from PactLib.config_manager import ConfigManager
from PactLib.logging_config import setup_test_logging
from PactLib.state_manager import StateManager


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
    """Sample configuration data for testing."""
    return {
        "Load_Order": {"File": "/path/to/loadorder.txt"},
        "Mod_Organizer": {"Binary": "/path/to/ModOrganizer.exe", "Install_Path": "/path/to/ModOrganizer"},
        "xEdit": {"Binary": "/path/to/xEdit.exe", "Install_Path": "/path/to/xEdit"},
        "PACT_Data": {
            "XEdit_Lists": {"Skyrim": ["Skyrim.esm", "Update.esm"], "Fallout4": ["Fallout4.esm"]},
            "Skip_Lists": {"Skyrim": ["Dawnguard.esm", "HearthFires.esm"], "Fallout4": ["DLCRobot.esm"]},
            "QAC_Lists": {"Skyrim": ["Unofficial Skyrim Patch.esp"], "Fallout4": ["Unofficial Fallout 4 Patch.esp"]},
        },
        "Settings": {"Journal_Expiration": 7, "Cleaning_Timeout": 300, "CPU_Threshold": 5, "MO2_Mode": False},
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
