"""Administrator order management."""

from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .admin import login_required
from .db import get_db
from .order_services import expire_reservations, utc_now


bp = Blueprint(
    "order_admin",
    __name__,
    url_prefix="/admin/orders",
)


def get_order(order_id):
    """Fetch an order together with its product snapshot."""

    db = get_db()

    order = db.execute(
        """
        SELECT
            o.*,
            oi.product_id,
            oi.product_name,
            oi.unit_price
        FROM orders AS o
        JOIN order_items AS oi ON oi.order_id = o.id
        WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()

    if order is None:
        abort(404)

    return order


@bp.get("/")
@login_required
def inbox():
    """Display all customer order requests."""

    db = get_db()
    expire_reservations(db)

    orders = db.execute(
        """
        SELECT
            o.id,
            o.public_ref,
            o.customer_name,
            o.contact,
            o.courier_name,
            o.courier_office,
            o.status,
            o.total,
            o.created_at,
            oi.product_name,
            oi.unit_price
        FROM orders AS o
        JOIN order_items AS oi ON oi.order_id = o.id
        ORDER BY
            CASE o.status
                WHEN 'new' THEN 0
                WHEN 'contacted' THEN 1
                WHEN 'confirmed' THEN 2
                WHEN 'completed' THEN 3
                WHEN 'cancelled' THEN 4
            END,
            o.created_at DESC,
            o.id DESC
        """
    ).fetchall()

    return render_template(
        "admin/orders.html",
        orders=orders,
    )


@bp.route("/<int:order_id>", methods=("GET", "POST"))
@login_required
def detail(order_id):
    """View and manage one customer order."""

    db = get_db()
    expire_reservations(db)
    order = get_order(order_id)

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        now = utc_now()

        try:
            if action == "contacted":
                if order["status"] != "new":
                    raise ValueError(
                        "Only new requests can be marked as contacted."
                    )

                db.execute(
                    """
                    UPDATE orders
                    SET status = 'contacted',
                        updated_at = ?
                    WHERE id = ?
                      AND status = 'new'
                    """,
                    (now, order_id),
                )

                db.commit()
                flash("Order marked as contacted.", "success")

            elif action == "confirm":
                if order["status"] not in {"new", "contacted"}:
                    raise ValueError(
                        "This request cannot be confirmed in its current status."
                    )

                try:
                    delivery_charge = int(
                        request.form.get("delivery_charge", "").strip()
                    )
                    deposit_paid = int(
                        request.form.get("deposit_paid", "").strip()
                    )
                except ValueError:
                    raise ValueError("Enter valid whole-number amounts.")

                if delivery_charge < 0 or deposit_paid < 0:
                    raise ValueError("Amounts cannot be negative.")

                minimum_deposit = (
                    order["unit_price"] * 75 + 99
                ) // 100

                total = order["unit_price"] + delivery_charge

                if deposit_paid < minimum_deposit:
                    raise ValueError(
                        f"The minimum reservation deposit is "
                        f"KSh {minimum_deposit:,}."
                    )

                if deposit_paid > total:
                    raise ValueError(
                        "The deposit cannot exceed the total order amount."
                    )

                if order["product_id"] is None:
                    raise ValueError(
                        "The original product is no longer available."
                    )

                # Reserve only if the product is still available.
                cursor = db.execute(
                    """
                    UPDATE products
                    SET status = 'reserved',
                        updated_at = ?
                    WHERE id = ?
                      AND status = 'available'
                    """,
                    (now, order["product_id"]),
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "This product is no longer available for reservation."
                    )

                expires_at = (
                    datetime.now(timezone.utc) + timedelta(days=3)
                ).replace(microsecond=0).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

                db.execute(
                    """
                    UPDATE orders
                    SET status = 'confirmed',
                        delivery_charge = ?,
                        total = ?,
                        deposit_paid = ?,
                        balance_paid = 0,
                        reservation_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?
                      AND status IN ('new', 'contacted')
                    """,
                    (
                        delivery_charge,
                        total,
                        deposit_paid,
                        expires_at,
                        now,
                        order_id,
                    ),
                )

                db.commit()

                flash(
                    "Reservation confirmed. The item is reserved for three days.",
                    "success",
                )

            elif action == "balance":
                if order["status"] != "confirmed":
                    raise ValueError(
                        "Additional payments can only be recorded "
                        "for confirmed reservations."
                    )

                try:
                    amount = int(
                        request.form.get("amount", "").strip()
                    )
                except ValueError:
                    raise ValueError(
                        "Enter a valid whole-number payment amount."
                    )

                if amount <= 0:
                    raise ValueError(
                        "Payment amount must be greater than zero."
                    )

                amount_paid = (
                    order["deposit_paid"]
                    + order["balance_paid"]
                    + amount
                )

                if amount_paid > order["total"]:
                    raise ValueError(
                        "The payment would exceed the order total."
                    )

                db.execute(
                    """
                    UPDATE orders
                    SET balance_paid = balance_paid + ?,
                        updated_at = ?
                    WHERE id = ?
                      AND status = 'confirmed'
                    """,
                    (amount, now, order_id),
                )

                db.commit()
                flash("Additional payment recorded.", "success")

            elif action == "complete":
                if order["status"] != "confirmed":
                    raise ValueError(
                        "Only confirmed reservations can be completed."
                    )

                total_paid = (
                    order["deposit_paid"] + order["balance_paid"]
                )

                if total_paid < order["total"]:
                    outstanding = order["total"] - total_paid
                    raise ValueError(
                        f"Payment is incomplete. "
                        f"KSh {outstanding:,} is still outstanding."
                    )

                if order["product_id"] is None:
                    raise ValueError(
                        "The original product is no longer available."
                    )

                cursor = db.execute(
                    """
                    UPDATE products
                    SET status = 'sold',
                        updated_at = ?
                    WHERE id = ?
                      AND status = 'reserved'
                    """,
                    (now, order["product_id"]),
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "The product is no longer marked as reserved."
                    )

                db.execute(
                    """
                    UPDATE orders
                    SET status = 'completed',
                        updated_at = ?
                    WHERE id = ?
                      AND status = 'confirmed'
                    """,
                    (now, order_id),
                )

                db.commit()

                flash(
                    "Order completed and product marked as sold.",
                    "success",
                )

            elif action == "cancel":
                if order["status"] in {"completed", "cancelled"}:
                    raise ValueError(
                        "This order can no longer be cancelled."
                    )

                db.execute(
                    """
                    UPDATE orders
                    SET status = 'cancelled',
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, order_id),
                )

                if order["product_id"] is not None:
                    db.execute(
                        """
                        UPDATE products
                        SET status = 'available',
                            updated_at = ?
                        WHERE id = ?
                          AND status = 'reserved'
                        """,
                        (now, order["product_id"]),
                    )

                db.commit()
                flash("Order cancelled.", "success")

            else:
                raise ValueError("Unknown order action.")

        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")

        except Exception:
            db.rollback()
            raise

        return redirect(
            url_for("order_admin.detail", order_id=order_id)
        )

    order = get_order(order_id)

    total_paid = order["deposit_paid"] + order["balance_paid"]
    outstanding = max(order["total"] - total_paid, 0)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    return render_template(
        "admin/order_detail.html",
        order=order,
        total_paid=total_paid,
        outstanding=outstanding,
        minimum_deposit=minimum_deposit,
    )