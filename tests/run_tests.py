#!/usr/bin/env python
"""
Test runner script for the trading system.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py unit         # Run unit tests only
    python run_tests.py integration  # Run integration tests
    python run_tests.py e2e          # Run end-to-end tests
    python run_tests.py --coverage   # Run with coverage report
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    # Change to tests directory
    tests_dir = Path(__file__).parent
    os.chdir(tests_dir)
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Parse arguments
    args = sys.argv[1:]
    
    # Handle test type selection
    if "unit" in args:
        cmd.append("unit/")
        args.remove("unit")
    elif "integration" in args:
        cmd.append("integration/")
        args.remove("integration")
    elif "e2e" in args:
        cmd.append("e2e/")
        args.remove("e2e")
    
    # Handle coverage flag
    if "--coverage" in args:
        cmd.extend(["--cov=../", "--cov-report=html", "--cov-report=term"])
        args.remove("--coverage")
    
    # Add verbose by default
    if "-v" not in args and "--verbose" not in args:
        cmd.append("-v")
    
    # Add any remaining args
    cmd.extend(args)
    
    # Print command
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)
    
    # Execute
    result = subprocess.run(cmd)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
