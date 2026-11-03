
"""Tests for administrator order management."""

from datetime import datetime, timedelta, timezone

from app.db import get_db
from tests.test_admin import get_csrf_token, login_test_admin
from tests.test_app import seed_sample_products
from tests.test_orders import submit_order


def create_customer_order(app, client):
    """Create a customer order request and return its order ID."""

    seed_sample_products(app)

    response = submit_order(
        client,
        "classic-denim-jacket",
    )

    assert response.status_code == 200

    with app.app_context():
        order = get_db().execute(
            "SELECT id FROM orders ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return order["id"]


def get_order_and_product(app, order_id):
    """Return an order and its associated product."""

    with app.app_context():
        return get_db().execute(
            """
            SELECT
                o.*,
                oi.product_id,
                oi.unit_price,
                p.status AS product_status
            FROM orders AS o
            JOIN order_items AS oi ON oi.order_id = o.id
            JOIN products AS p ON p.id = oi.product_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()


def post_order_action(client, order_id, data):
    """Submit an authenticated order-management action."""

    token = get_csrf_token(
        client,
        f"/admin/orders/{order_id}",
    )

    form_data = {
        "csrf_token": token,
        **data,
    }

    return client.post(
        f"/admin/orders/{order_id}",
        data=form_data,
        follow_redirects=True,
    )


def confirm_order(client, order_id, delivery_charge=300, deposit_paid=None):
    """Confirm a request using a valid deposit."""

    if deposit_paid is None:
        response = client.get(
            f"/admin/orders/{order_id}"
        )
        assert response.status_code == 200

        raise ValueError(
            "Pass deposit_paid explicitly when confirming an order."
        )

    return post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": str(delivery_charge),
            "deposit_paid": str(deposit_paid),
        },
    )


def test_order_inbox_requires_admin_login(client):
    response = client.get("/admin/orders/")

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_can_view_customer_order_inbox(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    response = client.get("/admin/orders/")

    assert response.status_code == 200
    assert b"Jane Customer" in response.data
    assert b"North Rift" in response.data

    order = get_order_and_product(app, order_id)
    assert order["status"] == "new"
    assert order["product_status"] == "available"


def test_admin_can_mark_order_as_contacted(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    response = post_order_action(
        client,
        order_id,
        {"action": "contacted"},
    )

    assert response.status_code == 200
    assert b"Order marked as contacted." in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "contacted"
    assert order["product_status"] == "available"


def test_admin_cannot_confirm_order_with_insufficient_deposit(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    response = post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit - 1),
        },
    )

    assert response.status_code == 200
    assert b"minimum reservation deposit" in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "new"
    assert order["product_status"] == "available"


def test_admin_can_confirm_order_and_reserve_product(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    delivery_charge = 300

    response = post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": str(delivery_charge),
            "deposit_paid": str(minimum_deposit),
        },
    )

    assert response.status_code == 200
    assert b"Reservation confirmed." in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "confirmed"
    assert order["product_status"] == "reserved"
    assert order["delivery_charge"] == delivery_charge
    assert order["total"] == order["unit_price"] + delivery_charge
    assert order["deposit_paid"] == minimum_deposit
    assert order["balance_paid"] == 0
    assert order["reservation_expires_at"] is not None

    expiry = datetime.strptime(
        order["reservation_expires_at"],
        "%Y-%m-%dT%H:%M:%SZ",
    ).replace(tzinfo=timezone.utc)

    remaining = expiry - datetime.now(timezone.utc)

    assert timedelta(days=2, hours=23) < remaining <= timedelta(days=3)


def test_two_requests_cannot_reserve_the_same_product(app, client):
    first_order_id = create_customer_order(app, client)

    response = submit_order(
        client,
        "classic-denim-jacket",
        contact="0722222222",
    )
    assert response.status_code == 200

    with app.app_context():
        second_order = get_db().execute(
            "SELECT id FROM orders ORDER BY id DESC LIMIT 1"
        ).fetchone()

    second_order_id = second_order["id"]

    login_test_admin(app, client)

    first_order = get_order_and_product(app, first_order_id)

    minimum_deposit = (
        first_order["unit_price"] * 75 + 99
    ) // 100

    first_response = post_order_action(
        client,
        first_order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit),
        },
    )

    assert first_response.status_code == 200
    assert b"Reservation confirmed." in first_response.data

    second_response = post_order_action(
        client,
        second_order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit),
        },
    )

    assert second_response.status_code == 200
    assert b"no longer available for reservation" in second_response.data

    first_order = get_order_and_product(app, first_order_id)
    second_order = get_order_and_product(app, second_order_id)

    assert first_order["status"] == "confirmed"
    assert second_order["status"] == "new"
    assert first_order["product_status"] == "reserved"
    assert second_order["product_status"] == "reserved"


def test_admin_cannot_complete_order_before_full_payment(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    delivery_charge = 300
    total = order["unit_price"] + delivery_charge

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": str(delivery_charge),
            "deposit_paid": str(minimum_deposit),
        },
    )

    response = post_order_action(
        client,
        order_id,
        {"action": "complete"},
    )

    assert response.status_code == 200
    assert b"Payment is incomplete." in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "confirmed"
    assert order["product_status"] == "reserved"
    assert order["deposit_paid"] == minimum_deposit
    assert order["total"] == total


def test_admin_can_record_balance_and_complete_fully_paid_order(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    delivery_charge = 300
    total = order["unit_price"] + delivery_charge
    outstanding = total - minimum_deposit

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": str(delivery_charge),
            "deposit_paid": str(minimum_deposit),
        },
    )

    payment_response = post_order_action(
        client,
        order_id,
        {
            "action": "balance",
            "amount": str(outstanding),
        },
    )

    assert payment_response.status_code == 200
    assert b"Additional payment recorded." in payment_response.data

    order = get_order_and_product(app, order_id)

    assert order["deposit_paid"] + order["balance_paid"] == total

    completion_response = post_order_action(
        client,
        order_id,
        {"action": "complete"},
    )

    assert completion_response.status_code == 200
    assert b"Order completed" in completion_response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "completed"
    assert order["product_status"] == "sold"


def test_admin_cannot_record_payment_above_order_total(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    delivery_charge = 300
    total = order["unit_price"] + delivery_charge

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": str(delivery_charge),
            "deposit_paid": str(minimum_deposit),
        },
    )

    response = post_order_action(
        client,
        order_id,
        {
            "action": "balance",
            "amount": str(total),
        },
    )

    assert response.status_code == 200
    assert b"payment would exceed the order total" in response.data

    order = get_order_and_product(app, order_id)

    assert order["balance_paid"] == 0
    assert order["status"] == "confirmed"


def test_admin_can_cancel_reservation_and_release_product(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit),
        },
    )

    response = post_order_action(
        client,
        order_id,
        {"action": "cancel"},
    )

    assert response.status_code == 200
    assert b"Order cancelled." in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "cancelled"
    assert order["product_status"] == "available"


def test_expired_reservation_is_cancelled_and_product_released(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit),
        },
    )

    expired_time = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    with app.app_context():
        get_db().execute(
            """
            UPDATE orders
            SET reservation_expires_at = ?
            WHERE id = ?
            """,
            (expired_time, order_id),
        )
        get_db().commit()

    response = client.get("/admin/orders/")

    assert response.status_code == 200

    order = get_order_and_product(app, order_id)

    assert order["status"] == "cancelled"
    assert order["product_status"] == "available"


def test_public_shop_expires_reservation_and_releases_product(app, client):
    order_id = create_customer_order(app, client)
    login_test_admin(app, client)

    order = get_order_and_product(app, order_id)

    minimum_deposit = (
        order["unit_price"] * 75 + 99
    ) // 100

    post_order_action(
        client,
        order_id,
        {
            "action": "confirm",
            "delivery_charge": "300",
            "deposit_paid": str(minimum_deposit),
        },
    )

    expired_time = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    with app.app_context():
        get_db().execute(
            """
            UPDATE orders
            SET reservation_expires_at = ?
            WHERE id = ?
            """,
            (expired_time, order_id),
        )
        get_db().commit()

    # Visiting the public catalogue should trigger expiry.
    response = client.get("/")

    assert response.status_code == 200
    assert b"Classic Denim Jacket" in response.data

    order = get_order_and_product(app, order_id)

    assert order["status"] == "cancelled"
    assert order["product_status"] == "available"
