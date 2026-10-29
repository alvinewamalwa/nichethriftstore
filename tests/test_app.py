
"""Tests for the homepage and health endpoint."""

import sqlite3

from app import create_app


def test_homepage_returns_success(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Find your next favourite piece." in response.data
    assert b"Explore our finds" in response.data


def test_unknown_page_returns_404(client):
    response = client.get("/this-page-does-not-exist")

    assert response.status_code == 404


def test_health_endpoint_returns_success(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_health_endpoint_fails_when_database_is_missing(app, client):
    database_path = app.config["DATABASE"]
    connection = sqlite3.connect(database_path)
    connection.close()

    import os
    os.remove(database_path)

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json == {"status": "unavailable"}


def test_health_endpoint_fails_when_schema_is_missing(app, client):
    database_path = app.config["DATABASE"]

    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS admin_users;
        """
    )
    connection.close()

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json == {"status": "unavailable"}
