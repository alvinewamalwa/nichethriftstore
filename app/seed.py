"""Insert repeatable demonstration products into the local database."""

import click
from flask import current_app

from .db import get_db

SAMPLE_PRODUCTS = [
    {
        "slug": "classic-denim-jacket",
        "name": "Classic Denim Jacket",
        "description": "A timeless denim jacket for everyday outfits.",
        "price": 800,
        "size": "M",
        "item_condition": "excellent",
        "status": "available",
    },
    {
        "slug": "vintage-knit-sweater",
        "name": "Vintage Knit Sweater",
        "description": "A cosy knit sweater with a classic vintage look.",
        "price": 650,
        "size": "L",
        "item_condition": "good",
        "status": "sold",
    },
    {
        "slug": "casual-cotton-shirt",
        "name": "Casual Cotton Shirt",
        "description": "A versatile cotton shirt for casual wear.",
        "price": 450,
        "size": "S",
        "item_condition": "excellent",
        "status": "available",
    },
    {
        "slug": "hidden-sample-item",
        "name": "Hidden Sample Item",
        "description": "A demonstration item that should not appear publicly.",
        "price": 500,
        "size": "M",
        "item_condition": "good",
        "status": "hidden",
    },
]


@click.command("seed-products")
def seed_products_command():
    """Insert sample products without duplicating existing slugs."""
    db = get_db()
    inserted = 0

    try:
        for product in SAMPLE_PRODUCTS:
            cursor = db.execute(
                """
                INSERT INTO products (
                    slug, name, description, price, size,
                    item_condition, status
                )
                VALUES (
                    :slug, :name, :description, :price, :size,
                    :item_condition, :status
                )
                ON CONFLICT(slug) DO NOTHING
                """,
                product,
            )
            inserted += cursor.rowcount

        db.commit()
    except Exception:
        db.rollback()
        raise

    click.echo(f"Sample-products command finished. Inserted {inserted} new products.")