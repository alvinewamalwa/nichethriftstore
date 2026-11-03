
"""Tests for customer order requests."""

from app.db import get_db

from tests.test_app import seed_sample_products


def submit_order(client, slug, **overrides):
    """Submit a valid order request, allowing individual fields to be overridden."""
    form_data = {
        "customer_name": "Jane Customer",
        "contact": "0712345678",
        "courier_name": "North Rift",
        "courier_office": "Nairobi town office",
        "note": "Please contact me on WhatsApp.",
    }
    form_data.update(overrides)

    return client.post(
        f"/products/{slug}/order",
        data=form_data,
        follow_redirects=True,
    )


def test_customer_can_submit_order_request(app, client):
    seed_sample_products(app)

    response = submit_order(client, "classic-denim-jacket")

    assert response.status_code == 200
    assert b"Request received!" in response.data
    assert b"NTS-" in response.data

    with app.app_context():
        order = get_db().execute(
            "SELECT * FROM orders"
        ).fetchone()

        item = get_db().execute(
            "SELECT * FROM order_items"
        ).fetchone()

        product = get_db().execute(
            """
            SELECT status
            FROM products
            WHERE slug = ?
            """,
            ("classic-denim-jacket",),
        ).fetchone()

    assert order is not None
    assert order["customer_name"] == "Jane Customer"
    assert order["contact"] == "0712345678"
    assert order["courier_name"] == "North Rift"
    assert order["courier_office"] == "Nairobi town office"
    assert order["status"] == "new"

    assert item is not None
    assert item["product_name"] == "Classic Denim Jacket"
    assert item["unit_price"] == order["total"]

    assert product["status"] == "available"


def test_each_order_request_has_a_unique_reference(app, client):
    seed_sample_products(app)

    first_response = submit_order(
        client,
        "classic-denim-jacket",
        contact="0711111111",
    )
    second_response = submit_order(
        client,
        "classic-denim-jacket",
        contact="0722222222",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    with app.app_context():
        orders = get_db().execute(
            "SELECT public_ref FROM orders ORDER BY id"
        ).fetchall()

    assert len(orders) == 2
    assert orders[0]["public_ref"] != orders[1]["public_ref"]


def test_order_request_requires_customer_name(app, client):
    seed_sample_products(app)

    response = submit_order(
        client,
        "classic-denim-jacket",
        customer_name="",
    )

    assert response.status_code == 400
    assert b"Please enter your name." in response.data

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

    assert count == 0


def test_order_request_requires_contact(app, client):
    seed_sample_products(app)

    response = submit_order(
        client,
        "classic-denim-jacket",
        contact="",
    )

    assert response.status_code == 400
    assert b"Please enter your phone or WhatsApp number." in response.data


def test_sold_product_cannot_receive_order_request(app, client):
    seed_sample_products(app)

    response = client.post(
        "/products/vintage-knit-sweater/order",
        data={
            "customer_name": "Jane Customer",
            "contact": "0712345678",
            "courier_name": "North Rift",
            "courier_office": "Nairobi town office",
        },
    )

    assert response.status_code == 404

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

    assert count == 0


def test_hidden_product_cannot_receive_order_request(app, client):
    seed_sample_products(app)

    response = client.post(
        "/products/hidden-sample-item/order",
        data={
            "customer_name": "Jane Customer",
            "contact": "0712345678",
            "courier_name": "North Rift",
            "courier_office": "Nairobi town office",
        },
    )

    assert response.status_code == 404

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

    assert count == 0


def test_order_request_requires_csrf_token(app, client):
    seed_sample_products(app)

    # Enable CSRF for this test only.
    app.config["WTF_CSRF_ENABLED"] = True

    response = client.post(
        "/products/classic-denim-jacket/order",
        data={
            "customer_name": "Jane Customer",
            "contact": "0712345678",
            "courier_name": "North Rift",
            "courier_office": "Nairobi town office",
        },
    )

    assert response.status_code == 400

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

    assert count == 0
