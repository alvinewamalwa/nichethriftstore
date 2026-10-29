
"""Tests for the homepage, health endpoint, and product catalogue."""

import os
import sqlite3

from app.db import get_db


def seed_sample_products(app):
    """Insert demonstration products into the test database."""
    runner = app.test_cli_runner()

    with app.app_context():
        result = runner.invoke(args=["seed-products"])

    assert result.exit_code == 0, result.output
    return result


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


def test_catalogue_shows_available_and_sold_but_not_hidden(app, client):
    seed_sample_products(app)

    response = client.get("/")

    assert response.status_code == 200
    assert b"Classic Denim Jacket" in response.data
    assert b"Casual Cotton Shirt" in response.data
    assert b"Vintage Knit Sweater" in response.data
    assert b"SOLD" in response.data
    assert b"Hidden Sample Item" not in response.data


def test_available_product_detail_shows_available_status(app, client):
    seed_sample_products(app)

    response = client.get("/products/classic-denim-jacket")

    assert response.status_code == 200
    assert b"Classic Denim Jacket" in response.data
    assert b"This item is available." in response.data


def test_sold_product_detail_remains_visible(app, client):
    seed_sample_products(app)

    response = client.get("/products/vintage-knit-sweater")

    assert response.status_code == 200
    assert b"Vintage Knit Sweater" in response.data
    assert b"SOLD" in response.data
    assert b"This item has been sold." in response.data


def test_hidden_product_detail_returns_404(app, client):
    seed_sample_products(app)

    response = client.get("/products/hidden-sample-item")

    assert response.status_code == 404


def test_seeding_is_repeatable(app):
    first_result = seed_sample_products(app)
    second_result = seed_sample_products(app)

    assert "Inserted 4 new products." in first_result.output
    assert "Inserted 0 new products." in second_result.output

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]

    assert count == 4
