"""Run tests from any directory and forbid accidental real DB connections."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    import database

    def forbidden():
        raise AssertionError("Test attempted a real database connection")

    monkeypatch.setattr(database, "get_connection", forbidden)
