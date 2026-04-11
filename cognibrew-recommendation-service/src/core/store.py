"""
In-memory store for the latest recommendation per username.

When the consumer receives a face.recognized event it fetches recommendations
from the Catalog Service and writes the result here.
The HTTP API then reads from here so the Frontend can poll without
waiting for a new recognition event.

Persistence
-----------
Every write is also flushed to SQLite (cognibrew_recommendations.db) so that
the latest recommendations survive service restarts.
On startup the store is warmed up from SQLite automatically.

Structure:
    _latest: dict[username, RecommendationResult]
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.db import upsert_recommendation


@dataclass
class RecommendationResult:
    username: str
    score: float
    items: list[dict]           # list of MenuItem dicts from Catalog Service
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


_lock = threading.Lock()
_latest: dict[str, RecommendationResult] = {}   # username → latest result


def set_recommendation(result: RecommendationResult) -> None:
    """Overwrite the latest recommendation for a username (memory + SQLite)."""
    with _lock:
        _latest[result.username] = result
    # Persist outside the lock to avoid holding it during I/O
    upsert_recommendation(
        username=result.username,
        score=result.score,
        items=result.items,
        fetched_at=result.fetched_at,
    )


def load_from_db() -> None:
    """Warm up the in-memory store from SQLite on service startup."""
    from src.core.db import load_recommendations  # local import to avoid circular

    rows = load_recommendations()
    with _lock:
        for row in rows:
            _latest[row["username"]] = RecommendationResult(
                username=row["username"],
                score=row["score"],
                items=row["items"],
                fetched_at=row["fetched_at"],
            )


def get_recommendation(username: str) -> RecommendationResult | None:
    """Return the latest recommendation for a username, or None if not yet available."""
    with _lock:
        return _latest.get(username)


def get_all() -> list[RecommendationResult]:
    """Return latest recommendations for all users (for debugging)."""
    with _lock:
        return list(_latest.values())
