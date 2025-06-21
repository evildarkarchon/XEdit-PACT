#!/usr/bin/env python3
"""Test runner script for XEdit-PACT."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pytest


def main() -> None:
    """Run the test suite with default configuration."""
    # Default pytest arguments
    args = [
        "--verbose",
        "--tb=short",
        "--cov=PactLib",
        "--cov=PACT_Interface",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "tests/",
    ]

    # Add command line arguments if provided
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])

    # Run pytest
    exit_code = pytest.main(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
