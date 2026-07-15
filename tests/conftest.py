"""Shared pytest configuration for tests run from the repository root."""

import os


def pytest_configure():
    os.chdir(os.path.dirname(os.path.dirname(__file__)))
