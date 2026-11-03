
"""SQLite connection handling and database initialisation."""

import sqlite3
from pathlib import Path

import click
from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            timeout=5,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    """Create tables and safely add columns to existing databases."""

    Path(current_app.config["DATABASE"]).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # Preserve compatibility with databases created before photo uploads.
    product_columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(products)").fetchall()
    }

    if "image_filename" not in product_columns:
        db.execute(
            "ALTER TABLE products ADD COLUMN image_filename TEXT"
        )

    # Safely extend older orders tables.
    order_columns = {
        row["name"]
        for row in db.execute("PRAGMA table_info(orders)").fetchall()
    }

    new_order_columns = {
        "courier_name": "TEXT NOT NULL DEFAULT ''",
        "courier_office": "TEXT NOT NULL DEFAULT ''",
        "delivery_charge": "INTEGER DEFAULT NULL",
        "deposit_paid": "INTEGER NOT NULL DEFAULT 0",
        "balance_paid": "INTEGER NOT NULL DEFAULT 0",
        "reservation_expires_at": "TEXT",
    }

    for column_name, column_definition in new_order_columns.items():
        if column_name not in order_columns:
            db.execute(
                f"ALTER TABLE orders ADD COLUMN "
                f"{column_name} {column_definition}"
            )

    db.commit()


@click.command("init-db")
def init_db_command():
    try:
        init_db()
    except (sqlite3.Error, OSError) as exc:
        raise click.ClickException(
            f"Could not initialise the database: {exc}"
        ) from exc

    click.echo(
        f"Database ready at {current_app.config['DATABASE']}"
    )


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

