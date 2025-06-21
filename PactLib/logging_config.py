"""Centralized logging configuration for XEdit-PACT."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: Path | str = "logs",
    log_file: str = "xedit_pact.log",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 5,
    console_level: int = logging.WARNING,
    file_level: int = logging.DEBUG,
    encoding: str = "utf-8",
) -> None:
    """
    Setup logging with rotating file handler and optional console output.

    Args:
        log_dir: Directory to store log files
        log_file: Name of the main log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        console_level: Logging level for console output
        file_level: Logging level for file output
        encoding: File encoding for log files
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / log_file, maxBytes=max_bytes, backupCount=backup_count, encoding=encoding
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def setup_test_logging(
    log_dir: Path | str = "logs",
    log_file: str = "test_xedit_pact.log",
    max_bytes: int = 1 * 1024 * 1024,  # 1MB for tests
    backup_count: int = 3,
    encoding: str = "utf-8",
) -> None:
    """
    Setup logging specifically for tests.

    Args:
        log_dir: Directory to store test log files
        log_file: Name of the test log file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        encoding: File encoding for log files
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Create test log file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / log_file, maxBytes=max_bytes, backupCount=backup_count, encoding=encoding
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Configure root logger for tests
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add test file handler only (no console output for tests)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_startup_info(logger: logging.Logger, app_name: str = "XEdit-PACT", version: str = "2.0.0") -> None:
    """
    Log application startup information.

    Args:
        logger: Logger instance to use
        app_name: Application name
        version: Application version
    """
    logger.info("=" * 60)
    logger.info(f"{app_name} v{version} - Starting up")
    logger.info("=" * 60)

    # Get log file path from handlers
    log_file_path = "Not configured"
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            log_file_path = handler.baseFilename
            break
        elif isinstance(handler, logging.FileHandler):
            log_file_path = handler.baseFilename
            break

    logger.info(f"Log file: {log_file_path}")
    logger.info(f"Log level: {logger.getEffectiveLevel()}")
    logger.info("=" * 60)
