
"""Niche Thrift Store - application factory."""

import os

from dotenv import load_dotenv
from flask import Flask
from flask_wtf.csrf import CSRFProtect


csrf = CSRFProtect()


def create_app(test_config=None):
    """Create and configure the Flask application."""
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=os.path.join(app.instance_path, "nichethriftstore.sqlite"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        UPLOAD_FOLDER=os.path.join(app.instance_path, "product_images"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing. Add it to your local .env file."
        )

    from . import admin, db, health, seed, shop

    db.init_app(app)
    csrf.init_app(app)

    app.cli.add_command(seed.seed_products_command)

    app.register_blueprint(health.bp)
    app.register_blueprint(shop.bp)
    app.register_blueprint(admin.bp)
    app.cli.add_command(admin.create_admin_command)

    return app
