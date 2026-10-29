
"""Tests for administrator authentication and product photo security."""

import re
from io import BytesIO
from pathlib import Path

from PIL import Image
from werkzeug.security import generate_password_hash

from app.db import get_db


def create_test_admin(app):
    """Create an administrator for testing."""
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO admin_users (username, password_hash)
            VALUES (?, ?)
            """,
            ("testadmin", generate_password_hash("test-password-123")),
        )
        db.commit()


def create_test_product(app, status="available"):
    """Create a product and return its database ID."""
    with app.app_context():
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO products (
                slug, name, description, price, size,
                item_condition, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"test-product-{status}",
                "Test Product",
                "A product for testing photo uploads.",
                1000,
                "M",
                "excellent",
                status,
            ),
        )
        db.commit()
        return cursor.lastrowid


def get_csrf_token(client, page="/admin/login"):
    """Get a CSRF token from a page containing a form."""
    response = client.get(page)
    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response.get_data(as_text=True),
    )
    assert match is not None, "CSRF token was not found in the page."
    return match.group(1)


def login_test_admin(app, client):
    """Log in as the test administrator."""
    create_test_admin(app)
    token = get_csrf_token(client)

    response = client.post(
        "/admin/login",
        data={
            "csrf_token": token,
            "username": "testadmin",
            "password": "test-password-123",
        },
    )
    assert response.status_code == 302


def make_test_image():
    """Create a small valid PNG image in memory."""
    image_bytes = BytesIO()
    image = Image.new("RGB", (80, 60), color="green")
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)
    return image_bytes


def test_admin_login_page_loads(client):
    response = client.get("/admin/login")

    assert response.status_code == 200
    assert b"Administrator login" in response.data


def test_admin_dashboard_requires_login(client):
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_login_rejects_wrong_password(app, client):
    create_test_admin(app)
    token = get_csrf_token(client)

    response = client.post(
        "/admin/login",
        data={
            "csrf_token": token,
            "username": "testadmin",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 200
    assert b"Invalid username or password." in response.data


def test_admin_can_login_and_logout(app, client):
    create_test_admin(app)
    token = get_csrf_token(client)

    response = client.post(
        "/admin/login",
        data={
            "csrf_token": token,
            "username": "testadmin",
            "password": "test-password-123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Welcome, testadmin" in response.data

    token = get_csrf_token(client, "/admin/")

    response = client.post(
        "/admin/logout",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"You have been logged out." in response.data

    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_photo_preview_requires_login(app, client):
    product_id = create_test_product(app)

    response = client.get(
        f"/admin/products/{product_id}/preview"
    )

    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_can_upload_product_photo(app, client):
    login_test_admin(app, client)
    product_id = create_test_product(app)

    token = get_csrf_token(
        client,
        f"/admin/products/{product_id}/photo",
    )

    response = client.post(
        f"/admin/products/{product_id}/photo",
        data={
            "csrf_token": token,
            "photo": (make_test_image(), "test-photo.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product photo uploaded successfully." in response.data

    with app.app_context():
        db = get_db()
        product = db.execute(
            "SELECT image_filename FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        assert product["image_filename"].endswith(".png")

        photo_path = (
            Path(app.config["UPLOAD_FOLDER"])
            / product["image_filename"]
        )
        assert photo_path.is_file()

    preview = client.get(
        f"/admin/products/{product_id}/preview"
    )
    assert preview.status_code == 200
    assert preview.mimetype == "image/png"


def test_admin_upload_rejects_invalid_image(app, client):
    login_test_admin(app, client)
    product_id = create_test_product(app)

    token = get_csrf_token(
        client,
        f"/admin/products/{product_id}/photo",
    )

    response = client.post(
        f"/admin/products/{product_id}/photo",
        data={
            "csrf_token": token,
            "photo": (BytesIO(b"This is not an image"), "fake.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid image." in response.data

    with app.app_context():
        product = get_db().execute(
            "SELECT image_filename FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        assert product["image_filename"] is None


def test_admin_photo_preview_returns_404_without_photo(app, client):
    login_test_admin(app, client)
    product_id = create_test_product(app)

    response = client.get(
        f"/admin/products/{product_id}/preview"
    )

    assert response.status_code == 404


def test_admin_dashboard_displays_product_photo_controls(app, client):
    login_test_admin(app, client)
    create_test_product(app)

    response = client.get("/admin/")

    assert response.status_code == 200
    assert b"Test Product" in response.data
    assert b"Upload photo" in response.data
    assert b"No photo" in response.data
