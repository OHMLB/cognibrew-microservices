"""
SQLite persistence for recommendation results.

Uses stdlib sqlite3 — no extra dependencies required.
DB file: cognibrew_recommendations.db  (created in the process working directory)

Tables
------
recommendations
    username   TEXT PK  — customer identifier (one row per customer, UPSERT)
    score      REAL     — face recognition confidence score
    items      TEXT     — JSON-encoded list of MenuItem dicts
    fetched_at TEXT     — UTC ISO timestamp of the last fetch
"""

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path("cognibrew_recommendations.db")


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the DB file and table if they do not exist yet."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                username   TEXT PRIMARY KEY,
                score      REAL NOT NULL,
                items      TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        con.commit()


# ── Write ─────────────────────────────────────────────────────────────────────

def upsert_recommendation(
    username: str,
    score: float,
    items: list[dict],
    fetched_at: str,
) -> None:
    """Insert or replace the latest recommendation for a username."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            """
            INSERT INTO recommendations (username, score, items, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                score      = excluded.score,
                items      = excluded.items,
                fetched_at = excluded.fetched_at
            """,
            (username, score, json.dumps(items), fetched_at),
        )
        con.commit()


# ── Read ──────────────────────────────────────────────────────────────────────

def load_recommendations() -> list[dict]:
    """Load all saved recommendations from DB.

    Returns a list of dicts with keys: username, score, items, fetched_at.
    Ready to be hydrated back into RecommendationResult objects.
    """
    with sqlite3.connect(_DB_PATH) as con:
        rows = con.execute(
            "SELECT username, score, items, fetched_at FROM recommendations"
        ).fetchall()

    return [
        {
            "username": username,
            "score": score,
            "items": json.loads(items_json),
            "fetched_at": fetched_at,
        }
        for username, score, items_json, fetched_at in rows
    ]
