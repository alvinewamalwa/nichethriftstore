"""Shared order and reservation services."""

from datetime import datetime, timezone


def utc_now():
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def expire_reservations(db):
    """
    Cancel expired reservations and release their products.

    The order cancellation and product release happen in one transaction.
    """
    now = utc_now()

    try:
        db.execute("BEGIN IMMEDIATE")

        expired_orders = db.execute(
            """
            SELECT o.id, oi.product_id
            FROM orders AS o
            JOIN order_items AS oi ON oi.order_id = o.id
            WHERE o.status = 'confirmed'
              AND o.reservation_expires_at IS NOT NULL
              AND o.reservation_expires_at <= ?
            """,
            (now,),
        ).fetchall()

        for order in expired_orders:
            cursor = db.execute(
                """
                UPDATE orders
                SET status = 'cancelled',
                    updated_at = ?
                WHERE id = ?
                  AND status = 'confirmed'
                  AND reservation_expires_at <= ?
                """,
                (now, order["id"], now),
            )

            # Only release the product if this order was actually cancelled.
            if cursor.rowcount == 1 and order["product_id"] is not None:
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

    except Exception:
        db.rollback()
        raise