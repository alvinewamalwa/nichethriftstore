
# Application Architecture

## Overview

Niche Thrift Store is a server-rendered web application built with Flask and SQLite.

## Main components

- `app/__init__.py` — creates and configures the Flask application.
- `app/db.py` — manages SQLite connections and database initialisation.
- `app/schema.sql` — defines the database tables and constraints.
- `app/health.py` — provides the application health endpoint.
- `app/shop/` — contains public shop routes.
- `app/templates/` — contains HTML templates rendered by Flask.
- `app/static/css/` — contains the website stylesheet.
- `tests/` — contains automated application and database tests.

## Request flow

1. A browser sends an HTTP request to Flask.
2. Flask routes the request to the appropriate view.
3. The view may read or update data through the database module.
4. Flask returns an HTML page or a JSON health response.

## Database

SQLite stores product, order, order-item, and administrator records.

Foreign-key enforcement is enabled on database connections. The health endpoint checks that the database is available and that the expected schema exists.

## Initial scope

The initial milestone provides the application skeleton, homepage, database initialisation, and health check.

Future milestones will introduce the product catalogue, product details, session-based cart, order requests, and owner-only administration.

Online payment processing is excluded from the initial MVP.
