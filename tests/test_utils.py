"""Tests for the utils module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from PactLib.utils import YamlManager, yaml_settings, yaml_settings_write


class TestYamlManager:
    """Test the YamlManager class."""

    def test_initialization(self) -> None:
        """Test YamlManager initialization."""
        manager = YamlManager()
        assert manager._cache == {}
        assert manager._file_mutexes == {}

    def test_parse_key_path(self) -> None:
        """Test _parse_key_path method."""
        manager = YamlManager()

        # Test string path
        keys = manager._parse_key_path("level1.level2.level3")
        assert keys == ["level1", "level2", "level3"]

        # Test list path
        keys = manager._parse_key_path(["level1", "level2", "level3"])
        assert keys == ["level1", "level2", "level3"]

    def test_get_value_simple(self) -> None:
        """Test getting a simple value from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            yaml_path = f.name

        try:
            manager = YamlManager()
            value = manager.get_value(yaml_path, "key")
            assert value == "value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_get_value_nested(self) -> None:
        """Test getting a nested value from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
level1:
  level2:
    level3: nested_value
""")
            yaml_path = f.name

        try:
            manager = YamlManager()
            value = manager.get_value(yaml_path, "level1.level2.level3")
            assert value == "nested_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_get_value_nonexistent(self) -> None:
        """Test getting a non-existent value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            yaml_path = f.name

        try:
            manager = YamlManager()
            value = manager.get_value(yaml_path, "nonexistent")
            assert value is None

            value = manager.get_value(yaml_path, "key.nonexistent")
            assert value is None
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_set_value_simple(self) -> None:
        """Test setting a simple value in YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: old_value\n")
            yaml_path = f.name

        try:
            manager = YamlManager()
            manager.set_value(yaml_path, "key", "new_value")

            # Verify the value was set
            value = manager.get_value(yaml_path, "key")
            assert value == "new_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_set_value_nested(self) -> None:
        """Test setting a nested value in YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("level1: {}\n")
            yaml_path = f.name

        try:
            manager = YamlManager()
            manager.set_value(yaml_path, "level1.level2.level3", "nested_value")

            # Verify the value was set
            value = manager.get_value(yaml_path, "level1.level2.level3")
            assert value == "nested_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_set_value_create_intermediate(self) -> None:
        """Test setting a value with non-existent intermediate keys."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{}\n")
            yaml_path = f.name

        try:
            manager = YamlManager()
            manager.set_value(yaml_path, "new.level1.level2", "value")

            # Verify the value was set and intermediate keys created
            value = manager.get_value(yaml_path, "new.level1.level2")
            assert value == "value"

            # Check that intermediate structure exists
            level1 = manager.get_value(yaml_path, "new.level1")
            assert isinstance(level1, dict)
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_cache_functionality(self) -> None:
        """Test that YAML files are cached."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            yaml_path = f.name

        try:
            manager = YamlManager()

            # First read should load from file
            value1 = manager.get_value(yaml_path, "key")
            assert value1 == "value"

            # Second read should use cache
            value2 = manager.get_value(yaml_path, "key")
            assert value2 == "value"

            # Cache should contain the file
            assert yaml_path in manager._cache
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_empty_file_handling(self) -> None:
        """Test handling of empty YAML files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            yaml_path = f.name

        try:
            manager = YamlManager()
            value = manager.get_value(yaml_path, "key")
            assert value is None

            # Should be able to set values in empty file
            manager.set_value(yaml_path, "new_key", "new_value")
            value = manager.get_value(yaml_path, "new_key")
            assert value == "new_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_nonexistent_file_handling(self) -> None:
        """Test handling of non-existent YAML files."""
        yaml_path = "/nonexistent/file.yaml"
        manager = YamlManager()

        value = manager.get_value(yaml_path, "key")
        assert value is None

        # Should be able to set values (creates file)
        manager.set_value(yaml_path, "key", "value")
        value = manager.get_value(yaml_path, "key")
        assert value == "value"

        # Clean up created file
        Path(yaml_path).unlink(missing_ok=True)

    def test_thread_safety(self) -> None:
        """Test thread safety of YAML operations."""
        import threading
        import time

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{}\n")
            yaml_path = f.name

        try:
            manager = YamlManager()

            def write_values(thread_id: int) -> None:
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"value_{thread_id}_{i}"
                    manager.set_value(yaml_path, key, value)
                    time.sleep(0.001)

            def read_values(thread_id: int) -> None:
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    manager.get_value(yaml_path, key)
                    time.sleep(0.001)

            # Create multiple threads
            threads = []
            for i in range(5):
                write_thread = threading.Thread(target=write_values, args=(i,))
                read_thread = threading.Thread(target=read_values, args=(i,))
                threads.extend([write_thread, read_thread])
                write_thread.start()
                read_thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Should not have crashed
            assert True
        finally:
            Path(yaml_path).unlink(missing_ok=True)


class TestYamlSettingsFunctions:
    """Test the yaml_settings and yaml_settings_write functions."""

    def test_yaml_settings_simple(self) -> None:
        """Test yaml_settings function with simple value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            yaml_path = f.name

        try:
            value = yaml_settings(yaml_path, "key")
            assert value == "value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_yaml_settings_nested(self) -> None:
        """Test yaml_settings function with nested value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
level1:
  level2:
    level3: nested_value
""")
            yaml_path = f.name

        try:
            value = yaml_settings(yaml_path, "level1.level2.level3")
            assert value == "nested_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_yaml_settings_write_simple(self) -> None:
        """Test yaml_settings_write function with simple value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{}\n")
            yaml_path = f.name

        try:
            yaml_settings_write(yaml_path, "new_value", "key")
            value = yaml_settings(yaml_path, "key")
            assert value == "new_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_yaml_settings_write_nested(self) -> None:
        """Test yaml_settings_write function with nested value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("{}\n")
            yaml_path = f.name

        try:
            yaml_settings_write(yaml_path, "nested_value", "level1.level2.level3")
            value = yaml_settings(yaml_path, "level1.level2.level3")
            assert value == "nested_value"
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_yaml_settings_write_replace_data(self) -> None:
        """Test yaml_settings_write function replacing entire data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("old_key: old_value\n")
            yaml_path = f.name

        try:
            new_data = {"new_key": "new_value", "another_key": "another_value"}
            yaml_settings_write(yaml_path, new_data)

            # Should replace entire content
            value1 = yaml_settings(yaml_path, "new_key")
            value2 = yaml_settings(yaml_path, "another_key")
            old_value = yaml_settings(yaml_path, "old_key")

            assert value1 == "new_value"
            assert value2 == "another_value"
            assert old_value is None
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_error_handling(self) -> None:
        """Test error handling in YAML operations."""
        # Test with invalid YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            yaml_path = f.name

        try:
            # Should handle invalid YAML gracefully
            value = yaml_settings(yaml_path, "key")
            assert value is None
        finally:
            Path(yaml_path).unlink(missing_ok=True)

    def test_path_object_handling(self) -> None:
        """Test that functions handle Path objects correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            yaml_path = Path(f.name)

        try:
            value = yaml_settings(yaml_path, "key")
            assert value == "value"

            yaml_settings_write(yaml_path, "new_value", "new_key")
            value = yaml_settings(yaml_path, "new_key")
            assert value == "new_value"
        finally:
            yaml_path.unlink(missing_ok=True)
