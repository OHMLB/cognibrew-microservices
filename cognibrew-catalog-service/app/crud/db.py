"""
SQLite persistence for order history.

Uses stdlib sqlite3 — no extra dependencies required.
DB file: cognibrew_catalog.db  (created in the process working directory)

Tables
------
orders
    id        INTEGER PK AUTOINCREMENT
    username  TEXT    — customer identifier
    item_id   TEXT    — ordered item
    device_id TEXT    — edge device that processed the order
    ordered_at TEXT   — UTC ISO timestamp (filled by SQLite default)
"""

import sqlite3
from pathlib import Path

_DB_PATH = Path("cognibrew_catalog.db")


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the DB file and tables if they do not exist yet."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL,
                item_id    TEXT    NOT NULL,
                device_id  TEXT    NOT NULL DEFAULT 'unknown',
                ordered_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)
        con.commit()


# ── Write ─────────────────────────────────────────────────────────────────────

def insert_order(username: str, item_id: str, device_id: str = "unknown") -> None:
    """Persist a single order row."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            "INSERT INTO orders (username, item_id, device_id) VALUES (?, ?, ?)",
            (username, item_id, device_id),
        )
        con.commit()


# ── Read ──────────────────────────────────────────────────────────────────────

def load_orders() -> dict[str, list[str]]:
    """Load all order history from DB.

    Returns {username: [item_id, ...]} ordered oldest-first,
    ready to be merged into the in-memory _orders dict.
    """
    orders: dict[str, list[str]] = {}
    with sqlite3.connect(_DB_PATH) as con:
        rows = con.execute(
            "SELECT username, item_id FROM orders ORDER BY id ASC"
        ).fetchall()

    for username, item_id in rows:
        orders.setdefault(username, []).append(item_id)

    return orders
