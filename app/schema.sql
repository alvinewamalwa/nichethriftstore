-- Niche Thrift Store schema (Day 1).
-- Safe to run repeatedly: every statement uses IF NOT EXISTS.
-- Money is stored as whole currency units (integers), never floats.
-- Timestamps are UTC, stored as ISO-8601 text.

CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY,
    slug           TEXT    NOT NULL UNIQUE CHECK (length(trim(slug)) > 0),
    name           TEXT    NOT NULL CHECK (length(trim(name)) > 0),
    description    TEXT    NOT NULL DEFAULT '',
    price          INTEGER NOT NULL CHECK (price >= 0),
    size           TEXT    NOT NULL DEFAULT '',
    item_condition TEXT    NOT NULL
                   CHECK (item_condition IN ('new_with_tags', 'excellent', 'good', 'fair')),
    status         TEXT    NOT NULL DEFAULT 'available'
                   CHECK (status IN ('available', 'reserved', 'sold', 'hidden')),
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY,
    public_ref    TEXT    NOT NULL UNIQUE,
    customer_name TEXT    NOT NULL CHECK (length(trim(customer_name)) > 0),
    contact       TEXT    NOT NULL CHECK (length(trim(contact)) > 0),
    delivery_area TEXT    NOT NULL DEFAULT '',
    note          TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'contacted', 'confirmed', 'completed', 'cancelled')),
    total         INTEGER NOT NULL CHECK (total >= 0),
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Each line of an order. The name and price are copied ("snapshot") so old
-- orders stay correct even if the product is later edited or deleted.
CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    unit_price   INTEGER NOT NULL CHECK (unit_price >= 0),
    UNIQUE (order_id, product_id)
);

CREATE TABLE IF NOT EXISTS admin_users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(trim(username)) > 0),
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_login_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);