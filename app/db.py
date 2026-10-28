"""SQLite connection handling and database initialisation."""

import sqlite3
from pathlib import Path

import click
from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db():
    """Return this request's database connection, creating it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=5)
        g.db.row_factory = sqlite3.Row
        # SQLite does NOT enforce foreign keys unless this is switched on
        # for every new connection.
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    """Close the connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables. Safe to run repeatedly; never deletes data."""
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    db.commit()


@click.command("init-db")
def init_db_command():
    """Create the database tables. Safe to run more than once."""
    try:
        init_db()
    except (sqlite3.Error, OSError) as exc:
        raise click.ClickException(f"Could not initialise the database: {exc}") from exc
    click.echo(f"Database ready at {current_app.config['DATABASE']}")


def init_app(app):
    """Register database handling with the app."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)