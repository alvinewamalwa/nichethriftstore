
"""Shared pytest fixtures for the application."""

import pytest

from app import create_app
from app.db import init_db


@pytest.fixture()
def app(tmp_path):
    """Create a test application with a temporary database."""
    database_path = tmp_path / "test.sqlite"

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(database_path),
            "SECRET_KEY": "test-only-secret",
        }
    )

    with app.app_context():
        init_db()

    yield app


@pytest.fixture()
def client(app):
    """Provide a test client for sending HTTP requests."""
    return app.test_client()
