
"""Shop routes for the Niche Thrift Store."""

from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    send_from_directory,
)

from ..db import get_db

bp = Blueprint("shop", __name__)


@bp.get("/")
def index():
    """Display available and sold products."""
    products = get_db().execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status, image_filename
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
               item_condition, status, image_filename
        FROM products
        WHERE slug = ?
          AND status IN ('available', 'sold')
        """,
        (slug,),
    ).fetchone()

    if product is None:
        abort(404)

    return render_template("shop/product_detail.html", product=product)


@bp.get("/product-images/<filename>")
def product_image(filename):
    """Serve an image only when it belongs to a public product."""
    # Only allow a simple filename, never a directory path.
    if filename != Path(filename).name or filename in {".", ".."}:
        abort(404)

    product = get_db().execute(
        """
        SELECT 1
        FROM products
        WHERE image_filename = ?
          AND status IN ('available', 'sold')
        """,
        (filename,),
    ).fetchone()

    if product is None:
        abort(404)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
    )
