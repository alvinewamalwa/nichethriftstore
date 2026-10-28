"""Niche Thrift Store - application factory."""

import os

from flask import Flask


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        # Deliberately no default. If SECRET_KEY is not set in the environment,
        # Flask refuses to use sessions instead of silently using a guessable
        # key. Nothing needs sessions yet; the cart will (Day 3).
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=os.path.join(app.instance_path, "nichethriftstore.sqlite"),
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    from . import db, health, shop

    db.init_app(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(shop.bp)

    return app