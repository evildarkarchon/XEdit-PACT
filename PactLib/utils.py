"""Utility functions for XEdit-PACT."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import psutil
import ruamel.yaml
from PySide6.QtCore import QMutex, QMutexLocker, QThread

if TYPE_CHECKING:
    from subprocess import CompletedProcess

    from ruamel.yaml.main import YAML

logger: logging.Logger = logging.getLogger(__name__)


class YamlManager:
    """Thread-safe YAML file manager with caching capabilities using Qt threading."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._cache_mutex = QMutex()
        self._file_mutexes: dict[str, QMutex] = {}
        self._file_mutexes_mutex = QMutex()
        self._yaml = ruamel.yaml.YAML()
        self._yaml.indent(offset=2)
        self._yaml.width = 300

    def _get_file_mutex(self, yaml_path: str) -> QMutex:
        """Get or create a mutex for the specified file path."""
        with QMutexLocker(self._file_mutexes_mutex):
            if yaml_path not in self._file_mutexes:
                self._file_mutexes[yaml_path] = QMutex()
            return self._file_mutexes[yaml_path]

    def get_value(self, yaml_path: str, key_path: str | list[str]) -> Any:
        """
        Retrieves a value from a specified YAML file at a given key path.

        This method reads a YAML file, locks it to prevent concurrent modifications,
        and navigates through its structure based on the key path to return the desired
        value. If the key path cannot be fully resolved, the method returns None.

        Args:
            yaml_path: Path to the YAML file from which the value is to be retrieved.
            key_path: A string or a list of strings representing the hierarchical key path
                to the desired value within the YAML structure.

        Returns:
            The value at the specified key path within the YAML file. If the key path
            does not exist or cannot be resolved, returns None.
        """
        file_mutex: QMutex = self._get_file_mutex(yaml_path)
        
        # Use Qt mutex with timeout to prevent deadlocks
        if not file_mutex.tryLock(5000):  # 5 second timeout
            logger.error(f"Timeout acquiring lock for file: {yaml_path}")
            return None
            
        try:
            data = self._load_yaml(yaml_path)
            keys: list[str] = self._parse_key_path(key_path)

            # Traverse the YAML structure
            value: Any = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None

            return value
        finally:
            file_mutex.unlock()

    def set_value(self, yaml_path: str, key_path: str | list[str], new_value: Any) -> None:
        """
        Updates a value in a YAML file at the specified key path. If the key path does not
        exist, intermediary dictionaries will be created to establish the path.

        Args:
            yaml_path: The file path to the YAML file that will be modified.
            key_path: The key path where the value will be set. It can be provided as a single
                string with keys separated by a delimiter, or as a list of individual string keys.
            new_value: The new value to be assigned at the specified key path.
        """
        file_mutex: QMutex = self._get_file_mutex(yaml_path)
        
        # Use Qt mutex with timeout to prevent deadlocks
        if not file_mutex.tryLock(5000):  # 5 second timeout
            logger.error(f"Timeout acquiring lock for file: {yaml_path}")
            return
            
        try:
            data: Any = self._load_yaml(yaml_path)
            keys: list[str] = self._parse_key_path(key_path)

            # Navigate to the parent of the final key
            current: Any = data
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Set the value at the final key
            current[keys[-1]] = new_value

            # Save changes back to file
            self._save_yaml(yaml_path, data)
        finally:
            file_mutex.unlock()

    @staticmethod
    def _parse_key_path(key_path: str | list[str]) -> list[str]:
        """Convert a dot-separated string path to list of keys."""
        return key_path.split(".") if isinstance(key_path, str) else key_path

    def _load_yaml(self, yaml_path: str) -> Any:
        """Load YAML file, using cache if available."""
        with QMutexLocker(self._cache_mutex):
            if yaml_path not in self._cache:
                try:
                    path: Path = Path(yaml_path)
                    if not path.exists():
                        logger.warning(f"YAML file not found: {yaml_path}")
                        self._cache[yaml_path] = {}
                    else:
                        with path.open(encoding="utf-8") as yaml_file:
                            content = yaml_file.read().strip()
                            if not content:
                                # Handle empty file
                                self._cache[yaml_path] = {}
                            else:
                                self._cache[yaml_path] = self._yaml.load(content) or {}
                except (OSError, ruamel.yaml.YAMLError, ValueError) as e:
                    logger.error(f"Failed to load YAML file '{yaml_path}': {e}")
                    self._cache[yaml_path] = {}

            return self._cache[yaml_path]

    def _save_yaml(self, yaml_path: str, data: Any) -> None:
        """Save data to YAML file with atomic write."""
        try:
            path: Path = Path(yaml_path)
            temp_path: Path = path.with_suffix(".tmp")

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file
            with temp_path.open("w", encoding="utf-8") as temp_file:
                self._yaml.dump(data, temp_file)

            # Atomic rename
            temp_path.replace(path)

            # Update cache
            with QMutexLocker(self._cache_mutex):
                self._cache[yaml_path] = data
        except (OSError, ruamel.yaml.YAMLError, ValueError) as e:
            logger.error(f"Failed to save YAML file '{yaml_path}': {e}")
            # Clean up temp file if it exists
            with contextlib.suppress(OSError):
                Path(yaml_path).with_suffix(".tmp").unlink(missing_ok=True)


# Create singleton instance
_yaml_manager = YamlManager()


def yaml_settings(yaml_path: str | Path, key_path: str | list[str]) -> Any:
    """
    Retrieve a specific value from a YAML file based on the provided key path.

    This function utilizes an external YAML management utility to extract
    a value from a YAML file. The exact value to be retrieved is determined
    by the provided key_path parameter. The function automatically handles
    conversions of the yaml_path to a string for compatibility with the
    YAML management utility.

    Args:
        yaml_path: The file path of the YAML file. Can be provided as a string
            or as a Path object.
        key_path: The path to the specific key or keys in the YAML structure.
            Can be provided as a string for a single key path or as a list of
            strings for hierarchical key paths.

    Returns:
        The value associated with the provided key path in the YAML file. The
        returned value can vary depending on the structure of the YAML file
        and the key path provided.
    """
    return _yaml_manager.get_value(str(yaml_path), key_path)


def yaml_settings_write(yaml_path: str | Path, new_value: Any, key_path: str | list[str] | None = None) -> None:
    """
    Updates or writes a YAML file with the specified new value. If a key path is
    provided, the function updates the value at the specified path; otherwise, it
    overwrites the entire YAML file with the new value.

    Args:
        yaml_path (str | Path): The file path to the YAML file to be written.
        new_value (Any): The new value to write or update in the YAML file.
        key_path (str | list[str] | None, optional): The key path within the YAML
            file to update. If None, the entire file is replaced with the new
            value. Defaults to None.
    """
    if key_path is None:
        # Write entire file
        path: Path = Path(yaml_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        yaml: YAML = ruamel.yaml.YAML()
        yaml.indent(offset=2)
        yaml.width = 300
        with path.open("w", encoding="utf-8") as f:
            yaml.dump(new_value, f)
    else:
        _yaml_manager.set_value(str(yaml_path), key_path, new_value)


def check_process(pid: int, threshold: int = 5) -> bool:
    """
    Checks whether a process exceeds a specified CPU usage threshold.

    This function retrieves the CPU usage percentage of a process specified
    by its process ID (PID) and compares it to a given threshold. If the
    process's CPU usage exceeds the threshold, the function returns True;
    otherwise, it returns False. If the process does not exist or cannot
    be accessed, the function returns False.

    Args:
        pid: The process ID of the target process.
        threshold: The CPU usage threshold percentage to compare against. Defaults to 5.

    Returns:
        bool: True if the process exceeds the CPU usage threshold, False otherwise.
    """
    try:
        process = psutil.Process(pid)
        cpu_percent: float = process.cpu_percent(interval=1)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    else:
        return cpu_percent > threshold


def detect_xedit_game(xedit_path: str) -> str | None:
    """
    Detects the game corresponding to the provided xEdit executable path.

    The function analyzes the filename of the provided xEdit executable path.
    Based on predefined mappings from xEdit executables to games, it returns
    the corresponding game's identifier. If no match is found, the function
    returns None.

    Args:
        xedit_path: The path to the xEdit executable file.

    Returns:
        The game identifier as a string, e.g., "FO3", "FNV", or "SSE", if the
        filename matches a known pattern. Otherwise, returns None.
    """
    filename: str = Path(xedit_path).stem.lower()

    game_map: dict[str, str] = {
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
    Executes an external process using a given command and optionally enforces a timeout
    for its execution. Captures and returns the process's return code, standard output,
    and standard error.

    Args:
        command (list[str]): A list of strings representing the command and arguments to
            execute.
        timeout (int | None): The maximum amount of time in seconds to allow the process
            to run. If None, no timeout is applied.

    Returns:
        tuple[int, str, str]: A tuple containing the process's return code, captured
            standard output, and captured standard error.

    Raises:
        subprocess.TimeoutExpired: If the process exceeds the specified timeout duration.
        OSError: If an OS-related error occurs during execution.
        subprocess.SubprocessError: If a general subprocess-related error occurs during
            execution.
    """
    import subprocess  # noqa: PLC0415

    try:
        result: CompletedProcess[str] = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return -1, "", "Process timed out"
    except (OSError, subprocess.SubprocessError) as e:
        return -1, "", str(e)
    else:
        return result.returncode, result.stdout, result.stderr


def run_process_with_realtime_output(
    command: list[str], 
    output_callback: Callable[[str], None] | None = None,
    timeout: int | None = None,
    working_dir: str | Path | None = None
) -> tuple[int, str, str]:
    """
    Executes a subprocess command with real-time output handling and optional timeout.

    This function starts a subprocess with the specified command and continuously reads
    its stdout and stderr in real-time. It allows optional callbacks for processing the
    real-time stdout. A timeout can also be specified to terminate the process if it
    exceeds the allowed execution time. The subprocess is executed in the specified
    working directory if provided. The function returns the exit code, stdout, and
    stderr of the process.

    Args:
        command (list[str]): The command to execute as a list of strings, where the first
            element is the executable and the remaining elements are its arguments.
        output_callback (Callable[[str], None] | None, optional): A callback function to
            handle each line of the standard output in real-time. If None, stdout is
            collected without processing.
        timeout (int | None, optional): The maximum allowed time in seconds for the
            subprocess to run. If the process exceeds this time, it is terminated.
            Defaults to None, meaning no timeout is applied.
        working_dir (str | Path | None, optional): The working directory in which the
            subprocess should execute. If None, the current working directory is used.
            Defaults to None.

    Returns:
        tuple[int, str, str]: A tuple containing the exit code (int), the collected
            standard output as a single string (str), and the collected standard error
            as a single string (str).

    Raises:
        OSError: If there is an issue creating or managing the subprocess.
        subprocess.SubprocessError: If the subprocess encounters an unexpected error.
        ValueError: If there is an issue with invalid parameters or process handling.
    """
    import subprocess  # noqa: PLC0415
    import time  # noqa: PLC0415
    
    start_time: float = time.time()
    stdout_lines: list[Any] = []
    stderr_lines: list[Any] = []
    
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
        
        def read_output(pipe: Any, line_list: list[str], callback: Callable[[str], None] | None) -> None:
            """Read output from pipe and call callback for each line."""
            try:
                for line in iter(pipe.readline, ''):
                    line = line.rstrip('\n\r')
                    if line:
                        line_list.append(line)
                        if callback:
                            callback(line)
            except (OSError, ValueError) as e:
                logger.error(f"Error reading process output: {e}")
            finally:
                pipe.close()
        
        class OutputReaderThread(QThread):
            def __init__(self, pipe: Any, line_list: list[str], callback: Callable[[str], None] | None) -> None:
                super().__init__()
                self.pipe = pipe
                self.line_list = line_list
                self.callback = callback
            
            def run(self) -> None:
                read_output(self.pipe, self.line_list, self.callback)
        
        # Start threads to read stdout and stderr
        stdout_thread: OutputReaderThread = OutputReaderThread(process.stdout, stdout_lines, output_callback)
        stderr_thread: OutputReaderThread = OutputReaderThread(process.stderr, stderr_lines, None)
        
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
        stdout_thread.wait(5000)  # 5 second timeout
        stderr_thread.wait(5000)  # 5 second timeout
        
        return process.returncode, '\n'.join(stdout_lines), '\n'.join(stderr_lines)
        
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return -1, "", str(e)

def monitor_log_file(
    log_file_path: str | Path,
    line_callback: Callable[[str], None],
    stop_event: Any,  # Changed from threading.Event to Any for Qt compatibility
    poll_interval: float = 0.1
) -> None:
    """
    Monitors a log file for new lines in real-time, invoking a callback function
    for each new line. The monitoring process terminates when the provided stop
    event is set. Skips non-existing files until they appear and starts from the
    end of the file when monitoring begins.

    Args:
        log_path: The path to the log file to monitor. Can be either a string or
            a Path object.
        line_callback: A callable function that processes a new log file line.
            The function takes a single string argument representing the new line
            from the log file.
        stop_event: A Qt event object used to signal the monitoring process
            to stop. When the event is set, the monitoring stops gracefully.
        poll_interval: The interval in seconds to wait between checks for new lines
            in the log file or for file existence.

    Raises:
        OSError: If an issue occurs while opening the file or reading from it.
        ValueError: If an invalid operation is attempted on the file.
    """
    log_path: Path = Path(log_file_path)
    
    try:
        # Wait for file to exist
        while not log_path.exists() and not stop_event.is_set():
            QThread.msleep(int(poll_interval * 1000))
        
        if stop_event.is_set():
            return
            
        with log_path.open('r', encoding='utf-8', errors='ignore') as f:
            # Start from end of existing file
            f.seek(0, 2)
            
            while not stop_event.is_set():
                line: str = f.readline()
                if line:
                    line_callback(line.rstrip('\n\r'))
                else:
                    QThread.msleep(int(poll_interval * 1000))
                    
    except (OSError, ValueError) as e:
        logger.error(f"Error monitoring log file '{log_path}': {e}")