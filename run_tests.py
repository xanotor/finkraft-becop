#!/usr/bin/env python3
"""Convenience test runner executing the complete test suite."""

import os
import sys
import unittest

if __name__ == "__main__":
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
    sys.path.insert(0, src_dir)

    loader = unittest.TestLoader()
    start_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "tests"))
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
