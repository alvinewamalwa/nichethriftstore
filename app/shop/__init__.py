"""Shop routes for the Niche Thrift Store."""

from pathlib import Path
import secrets

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    send_from_directory,
)

from ..db import get_db
from ..order_services import expire_reservations

bp = Blueprint("shop", __name__)


def get_public_product(slug):
    """Return a product that is allowed to appear in the public shop."""

    db = get_db()
    expire_reservations(db)

    return db.execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status, image_filename
        FROM products
        WHERE slug = ?
          AND status IN ('available', 'reserved', 'sold')
        """,
        (slug,),
    ).fetchone()


@bp.get("/")
def index():
    """Display available, reserved and sold products publicly."""

    db = get_db()
    expire_reservations(db)

    products = db.execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status, image_filename
        FROM products
        WHERE status IN ('available', 'reserved', 'sold')
        ORDER BY
            CASE status
                WHEN 'available' THEN 0
                WHEN 'reserved' THEN 1
                WHEN 'sold' THEN 2
            END,
            created_at DESC,
            id DESC
        """
    ).fetchall()

    return render_template(
        "shop/index.html",
        products=products,
    )


@bp.get("/products/<slug>")
def product_detail(slug):
    """Display a public product, including reserved and sold items."""

    product = get_public_product(slug)

    if product is None:
        abort(404)

    return render_template(
        "shop/product_detail.html",
        product=product,
        errors=[],
        form_data={},
    )


@bp.post("/products/<slug>/order")
def create_order(slug):
    """Create an order request without reserving the product."""

    db = get_db()
    expire_reservations(db)

    product = db.execute(
        """
        SELECT id, slug, name, description, price, size,
               item_condition, status, image_filename
        FROM products
        WHERE slug = ?
          AND status = 'available'
        """,
        (slug,),
    ).fetchone()

    if product is None:
        abort(404)

    form_data = {
        "customer_name": request.form.get(
            "customer_name", ""
        ).strip(),
        "contact": request.form.get(
            "contact", ""
        ).strip(),
        "courier_name": request.form.get(
            "courier_name", ""
        ).strip(),
        "courier_office": request.form.get(
            "courier_office", ""
        ).strip(),
        "note": request.form.get(
            "note", ""
        ).strip(),
    }

    errors = []

    if not form_data["customer_name"]:
        errors.append("Please enter your name.")
    elif len(form_data["customer_name"]) > 100:
        errors.append("Your name must be 100 characters or fewer.")

    if not form_data["contact"]:
        errors.append("Please enter your phone or WhatsApp number.")
    elif len(form_data["contact"]) > 40:
        errors.append("Your contact must be 40 characters or fewer.")

    if not form_data["courier_name"]:
        errors.append("Please enter your preferred courier.")
    elif len(form_data["courier_name"]) > 100:
        errors.append("The courier name must be 100 characters or fewer.")

    if not form_data["courier_office"]:
        errors.append(
            "Please enter your preferred courier collection office."
        )
    elif len(form_data["courier_office"]) > 150:
        errors.append(
            "The courier office must be 150 characters or fewer."
        )

    if len(form_data["note"]) > 1000:
        errors.append("Your note must be 1,000 characters or fewer.")

    if errors:
        return (
            render_template(
                "shop/product_detail.html",
                product=product,
                errors=errors,
                form_data=form_data,
            ),
            400,
        )

    public_ref = f"NTS-{secrets.token_hex(4).upper()}"

    try:
        cursor = db.execute(
            """
            INSERT INTO orders (
                public_ref,
                customer_name,
                contact,
                courier_name,
                courier_office,
                note,
                status,
                total
            )
            VALUES (?, ?, ?, ?, ?, ?, 'new', ?)
            """,
            (
                public_ref,
                form_data["customer_name"],
                form_data["contact"],
                form_data["courier_name"],
                form_data["courier_office"],
                form_data["note"],
                product["price"],
            ),
        )

        order_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO order_items (
                order_id,
                product_id,
                product_name,
                unit_price
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                product["id"],
                product["name"],
                product["price"],
            ),
        )

        # A customer request must never reserve the product automatically.
        db.commit()

    except Exception:
        db.rollback()

        current_app.logger.exception(
            "Could not create customer order request."
        )

        return (
            render_template(
                "shop/product_detail.html",
                product=product,
                errors=[
                    "We could not submit your request. Please try again."
                ],
                form_data=form_data,
            ),
            500,
        )

    return render_template(
        "shop/order_success.html",
        public_ref=public_ref,
        product_name=product["name"],
    )


@bp.get("/product-images/<filename>")
def product_image(filename):
    """Serve images belonging to publicly visible products."""

    if filename != Path(filename).name or filename in {".", ".."}:
        abort(404)

    db = get_db()
    expire_reservations(db)

    product = db.execute(
        """
        SELECT 1
        FROM products
        WHERE image_filename = ?
          AND status IN ('available', 'reserved', 'sold')
        """,
        (filename,),
    ).fetchone()

    if product is None:
        abort(404)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
    )