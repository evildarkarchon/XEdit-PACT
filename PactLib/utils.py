"""Utility functions for XEdit-PACT."""

from __future__ import annotations

import contextlib
import logging
import threading
from pathlib import Path
from typing import Any

import psutil
import ruamel.yaml

logger = logging.getLogger(__name__)


class YamlManager:
    """Thread-safe YAML file manager with caching capabilities."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.RLock()
        self._file_locks: dict[str, threading.RLock] = {}
        self._file_locks_lock = threading.Lock()
        self._yaml = ruamel.yaml.YAML()
        self._yaml.indent(offset=2)
        self._yaml.width = 300

    def _get_file_lock(self, yaml_path: str) -> threading.RLock:
        """Get or create a lock for the specified file path."""
        with self._file_locks_lock:
            if yaml_path not in self._file_locks:
                self._file_locks[yaml_path] = threading.RLock()
            return self._file_locks[yaml_path]

    def get_value(self, yaml_path: str, key_path: str | list[str]) -> Any:
        """Retrieve a value from the YAML file at the specified key path."""
        file_lock = self._get_file_lock(yaml_path)
        with file_lock:
            data = self._load_yaml(yaml_path)
            keys = self._parse_key_path(key_path)

            # Traverse the YAML structure
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return value

    def set_value(self, yaml_path: str, key_path: str | list[str], new_value: Any) -> None:
        """Set a value in the YAML file at the specified key path."""
        file_lock = self._get_file_lock(yaml_path)
        with file_lock:
            data = self._load_yaml(yaml_path)
            keys = self._parse_key_path(key_path)

            # Navigate to the parent of the final key
            current = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Set the value at the final key
            current[keys[-1]] = new_value

            # Save changes back to file
            self._save_yaml(yaml_path, data)

    @staticmethod
    def _parse_key_path(key_path: str | list[str]) -> list[str]:
        """Convert a dot-separated string path to list of keys."""
        return key_path.split(".") if isinstance(key_path, str) else key_path

    def _load_yaml(self, yaml_path: str) -> Any:
        """Load YAML file, using cache if available."""
        with self._cache_lock:
            if yaml_path not in self._cache:
                try:
                    path = Path(yaml_path)
                    if not path.exists():
                        logger.warning(f"YAML file not found: {yaml_path}")
                        self._cache[yaml_path] = {}
                    else:
                        with path.open(encoding="utf-8") as yaml_file:
                            self._cache[yaml_path] = self._yaml.load(yaml_file) or {}
                except Exception as e:
                    logger.error(f"Failed to load YAML file '{yaml_path}': {e}")
                    self._cache[yaml_path] = {}

            return self._cache[yaml_path]

    def _save_yaml(self, yaml_path: str, data: Any) -> None:
        """Save data to YAML file with atomic write."""
        try:
            path = Path(yaml_path)
            temp_path = path.with_suffix(".tmp")

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file
            with temp_path.open("w", encoding="utf-8") as temp_file:
                self._yaml.dump(data, temp_file)

            # Atomic rename
            temp_path.replace(path)

            # Update cache
            with self._cache_lock:
                self._cache[yaml_path] = data
        except Exception as e:
            logger.error(f"Failed to save YAML file '{yaml_path}': {e}")
            # Clean up temp file if it exists
            with contextlib.suppress(OSError):
                Path(yaml_path).with_suffix(".tmp").unlink(missing_ok=True)


# Create singleton instance
_yaml_manager = YamlManager()


def yaml_settings(yaml_path: str | Path, key_path: str | list[str]) -> Any:
    """
    Access values in a YAML file.

    Args:
        yaml_path: The file path to the YAML file
        key_path: Dot-separated string or list of strings representing the path to the key

    Returns:
        The value at the specified key path in the YAML file, or None if not found
    """
    return _yaml_manager.get_value(str(yaml_path), key_path)


def yaml_settings_write(yaml_path: str | Path, new_value: Any, key_path: str | list[str] | None = None) -> None:
    """
    Write values to a YAML file.

    Args:
        yaml_path: The file path to the YAML file
        new_value: The new value to set
        key_path: Optional dot-separated string or list of strings representing the path to the key
    """
    if key_path is None:
        # Write entire file
        path = Path(yaml_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        yaml = ruamel.yaml.YAML()
        yaml.indent(offset=2)
        yaml.width = 300
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(new_value, f)
    else:
        _yaml_manager.set_value(str(yaml_path), key_path, new_value)


def check_process(pid: int, threshold: int = 5) -> bool:
    """
    Check if a process is active based on CPU usage.

    Args:
        pid: Process ID to check
        threshold: CPU usage threshold percentage

    Returns:
        True if process is active (CPU usage above threshold), False otherwise
    """
    try:
        process = psutil.Process(pid)
        cpu_percent = process.cpu_percent(interval=1)
        return cpu_percent > threshold
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def detect_xedit_game(xedit_path: str) -> str | None:
    """
    Detect which game an xEdit executable is for based on its filename.

    Args:
        xedit_path: Path to the xEdit executable

    Returns:
        Game identifier string or None if not recognized
    """
    filename = Path(xedit_path).stem.lower()

    game_map = {
        "fo3edit": "FO3",
        "fnvedit": "FNV",
        "fo4edit": "FO4",
        "fo4vredit": "FO4",
        "sseedit": "SSE",
        "tes5edit": "SSE",
        "skyrimvredit": "SSE",
    }

    for key, game in game_map.items():
        if key in filename:
            return game

    return None


def run_process(command: list[str], timeout: int | None = None) -> tuple[int, str, str]:
    """
    Run a subprocess and return its exit code, stdout, and stderr.

    Args:
        command: Command and arguments to run
        timeout: Optional timeout in seconds

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    import subprocess

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout, check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Process timed out"
    except Exception as e:
        return -1, "", str(e)


def run_process_with_realtime_output(
    command: list[str], 
    output_callback: callable | None = None,
    timeout: int | None = None,
    working_dir: str | Path | None = None
) -> tuple[int, str, str]:
    """
    Run a subprocess with real-time output monitoring.

    Args:
        command: Command and arguments to run
        output_callback: Optional callback function called with each output line
        timeout: Optional timeout in seconds  
        working_dir: Optional working directory for the process

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    import subprocess
    import threading
    import time
    
    start_time = time.time()
    stdout_lines = []
    stderr_lines = []
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1,  # Line buffered
            universal_newlines=True,
            cwd=str(working_dir) if working_dir else None
        )
        
        def read_output(pipe: Any, line_list: list[str], callback: callable | None) -> None:
            """Read output from pipe and call callback for each line."""
            try:
                for line in iter(pipe.readline, ''):
                    line = line.rstrip('\n\r')
                    if line:
                        line_list.append(line)
                        if callback:
                            callback(line)
            except Exception as e:
                logger.error(f"Error reading process output: {e}")
            finally:
                pipe.close()
        
        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(
            target=read_output, 
            args=(process.stdout, stdout_lines, output_callback)
        )
        stderr_thread = threading.Thread(
            target=read_output,
            args=(process.stderr, stderr_lines, None)
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Monitor for timeout
        while process.poll() is None:
            if timeout and (time.time() - start_time) > timeout:
                process.terminate()
                process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
                if process.poll() is None:
                    process.kill()  # Force kill if still running
                return -1, '\n'.join(stdout_lines), "Process timed out"
            
            time.sleep(0.1)
        
        # Wait for threads to finish reading all output
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        
        return process.returncode, '\n'.join(stdout_lines), '\n'.join(stderr_lines)
        
    except Exception as e:
        return -1, "", str(e)


def monitor_log_file(
    log_path: str | Path,
    line_callback: callable,
    stop_event: threading.Event,
    poll_interval: float = 0.1
) -> None:
    """
    Monitor a log file for new lines and call callback for each new line.
    
    Args:
        log_path: Path to the log file to monitor
        line_callback: Function to call with each new line
        stop_event: Threading event to signal when to stop monitoring
        poll_interval: How often to check for new lines (seconds)
    """
    log_path = Path(log_path)
    
    try:
        # Wait for file to exist
        while not log_path.exists() and not stop_event.is_set():
            threading.Event().wait(poll_interval)
        
        if stop_event.is_set():
            return
            
        with log_path.open('r', encoding='utf-8', errors='ignore') as f:
            # Start from end of existing file
            f.seek(0, 2)
            
            while not stop_event.is_set():
                line = f.readline()
                if line:
                    line_callback(line.rstrip('\n\r'))
                else:
                    threading.Event().wait(poll_interval)
                    
    except Exception as e:
        logger.error(f"Error monitoring log file '{log_path}': {e}")