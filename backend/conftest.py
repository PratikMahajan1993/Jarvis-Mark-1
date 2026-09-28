"""Pytest hooks for the backend tree (live_service gating)."""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run tests marked live_service (desk-only external services)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_service: tests that require live external services",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="need --live option to run")
    for item in items:
        if "live_service" in item.keywords:
            item.add_marker(skip)
