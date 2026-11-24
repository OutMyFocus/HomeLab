"""Shared test setup."""

import pytest

from mtgscanner import config


@pytest.fixture(autouse=True)
def first_machine_by_default(monkeypatch):
    """The app now starts on the Sorter Mk2 (config.MACHINE_MODEL). Most machine tests were
    written for the first machine, whose code is still there, so they start on it; Mk2
    tests switch with {"model": "mk2"} as before."""
    monkeypatch.setattr(config, "MACHINE_MODEL", "mk1")
