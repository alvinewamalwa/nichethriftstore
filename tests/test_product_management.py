"""Tests for administrator product creation and editing."""

import re

from werkzeug.security import generate_password_hash

from app.db import get_db


def create_test_admin(app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO admin_users (username, password_hash)
            VALUES (?, ?)
            """,
            ("productadmin", generate_password_hash("test-password-123")),
        )
        db.commit()


def get_csrf_token(client, page):
    response = client.get(page)
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response.get_data(as_text=True),
    )
    assert match is not None
    return match.group(1)


def login_admin(app, client):
    create_test_admin(app)
    token = get_csrf_token(client, "/admin/login")

    response = client.post(
        "/admin/login",
        data={
            "csrf_token": token,
            "username": "productadmin",
            "password": "test-password-123",
        },
    )
    assert response.status_code == 302


def valid_product_data(**overrides):
    data = {
        "name": "Vintage Denim Jacket",
        "description": "A classic vintage denim jacket.",
        "price": "2500",
        "size": "M",
        "item_condition": "excellent",
        "status": "available",
    }
    data.update(overrides)
    return data


def test_product_creation_page_requires_login(client):
    response = client.get("/admin/products/new")

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_can_open_product_creation_form(app, client):
    login_admin(app, client)

    response = client.get("/admin/products/new")

    assert response.status_code == 200
    assert b"Add a new product" in response.data
    assert b"Product name" in response.data


def test_admin_can_create_product(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product created successfully." in response.data
    assert b"Vintage Denim Jacket" in response.data

    with app.app_context():
        product = get_db().execute(
            """
            SELECT slug, name, description, price, size,
                   item_condition, status
            FROM products
            WHERE name = ?
            """,
            ("Vintage Denim Jacket",),
        ).fetchone()

        assert product is not None
        assert product["slug"] == "vintage-denim-jacket"
        assert product["description"] == "A classic vintage denim jacket."
        assert product["price"] == 2500
        assert product["size"] == "M"
        assert product["item_condition"] == "excellent"
        assert product["status"] == "available"


def test_product_creation_generates_unique_slugs(app, client):
    login_admin(app, client)

    for _ in range(2):
        token = get_csrf_token(client, "/admin/products/new")
        response = client.post(
            "/admin/products/new",
            data={
                "csrf_token": token,
                **valid_product_data(),
            },
        )
        assert response.status_code == 302

    with app.app_context():
        products = get_db().execute(
            """
            SELECT slug
            FROM products
            WHERE name = ?
            ORDER BY id
            """,
            ("Vintage Denim Jacket",),
        ).fetchall()

        assert [row["slug"] for row in products] == [
            "vintage-denim-jacket",
            "vintage-denim-jacket-2",
        ]


def test_product_creation_rejects_empty_name(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(name="   "),
        },
    )

    assert response.status_code == 400
    assert b"Product name is required." in response.data

    with app.app_context():
        count = get_db().execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]
        assert count == 0


def test_product_creation_rejects_invalid_price(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(price="-100"),
        },
    )

    assert response.status_code == 400
    assert b"Price cannot be negative." in response.data


def test_product_creation_rejects_non_numeric_price(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(price="abc"),
        },
    )

    assert response.status_code == 400
    assert b"Enter a valid whole-number price" in response.data


def test_product_creation_rejects_invalid_condition(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(item_condition="damaged"),
        },
    )

    assert response.status_code == 400
    assert b"Choose a valid product condition." in response.data


def test_product_creation_rejects_invalid_status(app, client):
    login_admin(app, client)
    token = get_csrf_token(client, "/admin/products/new")

    response = client.post(
        "/admin/products/new",
        data={
            "csrf_token": token,
            **valid_product_data(status="published"),
        },
    )

    assert response.status_code == 400
    assert b"Choose a valid product status." in response.data


def test_product_edit_page_requires_login(app, client):
    with app.app_context():
        cursor = get_db().execute(
            """
            INSERT INTO products (
                slug, name, price, item_condition, status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("edit-test", "Edit Test", 1000, "good", "available"),
        )
        get_db().commit()
        product_id = cursor.lastrowid

    response = client.get(f"/admin/products/{product_id}/edit")

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_can_edit_product(app, client):
    login_admin(app, client)

    with app.app_context():
        cursor = get_db().execute(
            """
            INSERT INTO products (
                slug, name, description, price, size,
                item_condition, status, image_filename
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "original-product-slug",
                "Original Product",
                "Original description",
                1000,
                "S",
                "good",
                "available",
                "existing-photo.png",
            ),
        )
        get_db().commit()
        product_id = cursor.lastrowid

    page = f"/admin/products/{product_id}/edit"
    token = get_csrf_token(client, page)

    response = client.post(
        page,
        data={
            "csrf_token": token,
            **valid_product_data(
                name="Updated Product Name",
                description="Updated description",
                price="3500",
                size="L",
                item_condition="new_with_tags",
                status="sold",
            ),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product updated successfully." in response.data

    with app.app_context():
        product = get_db().execute(
            """
            SELECT slug, name, description, price, size,
                   item_condition, status, image_filename
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

        assert product["slug"] == "original-product-slug"
        assert product["name"] == "Updated Product Name"
        assert product["description"] == "Updated description"
        assert product["price"] == 3500
        assert product["size"] == "L"
        assert product["item_condition"] == "new_with_tags"
        assert product["status"] == "sold"
        assert product["image_filename"] == "existing-photo.png"


def test_editing_unknown_product_returns_404(app, client):
    login_admin(app, client)

    response = client.get("/admin/products/99999/edit")

    assert response.status_code == 404


def test_admin_dashboard_shows_product_management_controls(app, client):
    login_admin(app, client)

    response = client.get("/admin/")

    assert response.status_code == 200
    assert b"Add new product" in response.data