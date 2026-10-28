"""Shop blueprint. Only the homepage exists on Day 1."""

from flask import Blueprint, render_template

bp = Blueprint("shop", __name__)


@bp.get("/")
def index():
    return render_template("shop/index.html")