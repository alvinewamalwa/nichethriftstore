"""Niche Thrift Store - application factory."""

import os

from flask import Flask


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=os.path.join(app.instance_path, "nichethriftstore.sqlite"),
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    from . import db, health, seed, shop

    db.init_app(app)
    app.cli.add_command(seed.seed_products_command)

    app.register_blueprint(health.bp)
    app.register_blueprint(shop.bp)

    return app