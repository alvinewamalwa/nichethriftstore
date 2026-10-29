
"""Administrator authentication, dashboard, and product photo routes."""

from functools import wraps
from getpass import getpass
from pathlib import Path
import secrets

import click
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask.cli import with_appcontext
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..db import get_db


bp = Blueprint("admin", __name__, url_prefix="/admin")


def login_required(view):
    """Allow access only to authenticated administrators."""

    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("admin_id") is None:
            return redirect(url_for("admin.login", next=request.path))
        return view(**kwargs)

    return wrapped_view


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Authenticate an administrator."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = get_db().execute(
            """
            SELECT id, username, password_hash
            FROM admin_users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if admin is None or not check_password_hash(
            admin["password_hash"], password
        ):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]

            get_db().execute(
                """
                UPDATE admin_users
                SET last_login_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                WHERE id = ?
                """,
                (admin["id"],),
            )
            get_db().commit()

            destination = request.args.get("next", "")
            if (
                not destination.startswith("/admin/")
                or destination.startswith("//")
            ):
                destination = url_for("admin.dashboard")

            return redirect(destination)

    return render_template("admin/login.html")


@bp.get("/")
@login_required
def dashboard():
    """Display the administrator dashboard."""
    products = get_db().execute(
        """
        SELECT id, slug, name, price, status, image_filename
        FROM products
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()

    return render_template("admin/dashboard.html", products=products)


@bp.post("/logout")
@login_required
def logout():
    """End the administrator session."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin.login"))


@bp.get("/products/<int:product_id>/preview")
@login_required
def product_photo_preview(product_id):
    """Serve a product photo to authenticated administrators only."""
    product = get_db().execute(
        """
        SELECT image_filename
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()

    if product is None or not product["image_filename"]:
        abort(404)

    filename = product["image_filename"]

    # Never allow a database filename to escape the upload directory.
    if filename != Path(filename).name or filename != secure_filename(filename):
        abort(404)

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    photo_path = upload_folder / filename

    if not photo_path.is_file():
        abort(404)

    return send_from_directory(upload_folder, filename)


@bp.route(
    "/products/<int:product_id>/photo",
    methods=("GET", "POST"),
)
@login_required
def upload_product_photo(product_id):
    """Upload and validate a product photo."""
    db = get_db()

    product = db.execute(
        """
        SELECT id, name, image_filename
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    ).fetchone()

    if product is None:
        abort(404)

    if request.method == "POST":
        uploaded_file = request.files.get("photo")

        if uploaded_file is None or not uploaded_file.filename:
            flash("Choose a photo to upload.", "error")
            return redirect(
                url_for(
                    "admin.upload_product_photo",
                    product_id=product_id,
                )
            )

        upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
        upload_folder.mkdir(parents=True, exist_ok=True)

        destination = None

        try:
            with Image.open(uploaded_file.stream) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Unsupported image format.")
                image.verify()

            uploaded_file.stream.seek(0)

            with Image.open(uploaded_file.stream) as image:
                image_format = image.format
                image = ImageOps.exif_transpose(image)
                image.thumbnail((2000, 2000))

                extensions = {
                    "JPEG": ".jpg",
                    "PNG": ".png",
                    "WEBP": ".webp",
                }

                if image_format not in extensions:
                    raise ValueError("Unsupported image format.")

                filename = secrets.token_hex(16) + extensions[image_format]
                destination = upload_folder / filename

                if image_format == "JPEG":
                    image.convert("RGB").save(
                        destination,
                        format="JPEG",
                        quality=85,
                        optimize=True,
                    )
                elif image_format == "PNG":
                    if image.mode not in {"RGB", "RGBA", "L", "LA"}:
                        image = image.convert("RGBA")
                    image.save(
                        destination,
                        format="PNG",
                        optimize=True,
                    )
                else:
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA")
                    image.save(
                        destination,
                        format="WEBP",
                        quality=85,
                        method=6,
                    )

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ):
            if destination is not None:
                destination.unlink(missing_ok=True)

            flash(
                "Invalid image. Please upload a valid JPEG, PNG, or WebP.",
                "error",
            )
            return redirect(
                url_for(
                    "admin.upload_product_photo",
                    product_id=product_id,
                )
            )

        old_filename = product["image_filename"]

        try:
            db.execute(
                """
                UPDATE products
                SET image_filename = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                WHERE id = ?
                """,
                (filename, product_id),
            )
            db.commit()
        except Exception:
            if destination is not None:
                destination.unlink(missing_ok=True)
            db.rollback()
            raise

        if old_filename and old_filename != filename:
            old_path = upload_folder / secure_filename(old_filename)
            old_path.unlink(missing_ok=True)

        flash("Product photo uploaded successfully.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/upload_photo.html", product=product)


@click.command("create-admin")
@with_appcontext
def create_admin_command():
    """Create an administrator account interactively."""
    username = input("Admin username: ").strip()

    if not username:
        raise click.ClickException("Username cannot be empty.")

    password = getpass("Admin password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")

    if len(password) < 12:
        raise click.ClickException(
            "Password must be at least 12 characters."
        )

    if password != confirmation:
        raise click.ClickException("Passwords do not match.")

    db = get_db()

    try:
        db.execute(
            """
            INSERT INTO admin_users (username, password_hash)
            VALUES (?, ?)
            """,
            (username, generate_password_hash(password)),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise click.ClickException(
            "Could not create admin. Check whether that username already exists."
        ) from exc

    click.echo(f"Administrator '{username}' created successfully.")
