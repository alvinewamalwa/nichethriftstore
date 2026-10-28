
"""Tests for database initialisation and configuration."""

import sqlite3

from app.db import get_db, init_db


def test_required_tables_are_created(app):
    with app.app_context():
        db = get_db()

        rows = db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {row["name"] for row in rows}

        assert {
            "products",
            "orders",
            "order_items",
            "admin_users",
        }.issubset(table_names)


def test_database_initialisation_is_repeatable(app):
    with app.app_context():
        init_db()
        init_db()

        db = get_db()
        result = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                  'products',
                  'orders',
                  'order_items',
                  'admin_users'
              )
            """
        ).fetchone()

        assert result["total"] == 4


def test_foreign_keys_are_enabled(app):
    with app.app_context():
        db = get_db()
        result = db.execute("PRAGMA foreign_keys").fetchone()

        assert result[0] == 1


def test_negative_price_is_rejected(app):
    with app.app_context():
        db = get_db()

        columns = db.execute(
            "PRAGMA table_info(products)"
        ).fetchall()

        column_names = {column["name"] for column in columns}

        price_column = next(
            (
                name
                for name in ("price_kes", "price")
                if name in column_names
            ),
            None,
        )

        assert price_column is not None, (
            "Could not identify the product price column."
        )

        try:
            db.execute(
                f'INSERT INTO products (name, slug, "{price_column}") '
                "VALUES (?, ?, ?)",
                ("Test item", "test-negative-price", -1),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
        else:
            db.rollback()
            raise AssertionError(
                "The database accepted a negative product price."
            )
