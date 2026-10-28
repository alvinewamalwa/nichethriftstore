"""Health check endpoint for monitoring."""

import os
import sqlite3

from flask import Blueprint, current_app, jsonify

from .db import get_db

bp = Blueprint("health", __name__)


def check_database():
    """Raise an exception if the database is not usable."""
    path = current_app.config["DATABASE"]
    # Check the file exists first so a health check never creates an empty one.
    if not os.path.exists(path):
        raise FileNotFoundError("database file not found; run 'flask --app app init-db'")

    db = get_db()
    db.execute("SELECT 1").fetchone()

    table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("products",),
    ).fetchone()
    if table is None:
        raise RuntimeError("database schema missing; run 'flask --app app init-db'")


@bp.get("/healthz")
def healthz():
    try:
        check_database()
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        # Details go to the server log only, never to the visitor.
        current_app.logger.error("Health check failed: %s", exc)
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok"), 200