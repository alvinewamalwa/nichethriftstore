"""Shop routes for the Niche Thrift Store."""

from flask import Blueprint, abort, render_template

from ..db import get_db

bp = Blueprint("shop", __name__)


@bp.get("/")
def index():
    """Display available and sold products."""
    products = get_db().execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status
        FROM products
        WHERE status IN ('available', 'sold')
        ORDER BY
            CASE status
                WHEN 'available' THEN 0
                WHEN 'sold' THEN 1
            END,
            created_at DESC,
            id DESC
        """
    ).fetchall()

    return render_template("shop/index.html", products=products)


@bp.get("/products/<slug>")
def product_detail(slug):
    """Display details for a publicly visible product."""
    product = get_db().execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status
        FROM products
        WHERE slug = ?
          AND status IN ('available', 'sold')
        """,
        (slug,),
    ).fetchone()

    if product is None:
        abort(404)

    return render_template("shop/product_detail.html", product=product)