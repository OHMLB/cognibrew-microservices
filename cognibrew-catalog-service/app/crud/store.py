"""
In-memory store for menu items and order history.

Seeded from ``data/menu_seed.json`` on startup.
Order history is persisted to SQLite (cognibrew_catalog.db) so it survives
service restarts.  Menu items are still persisted via JSON (existing behaviour).

Structure:
    _menu:   dict[item_id, MenuItem]        – all menu items
    _orders: dict[username, list[item_id]]  – order history per customer
"""

import json
import uuid
from collections import Counter
from pathlib import Path

import logging

from app.models.schemas import MenuItem, MenuItemCreate, MenuItemUpdate
from app.crud.db import insert_order, load_orders

logger = logging.getLogger(__name__)

# ── In-memory stores ──────────────────────────────────────────────────────────
_menu: dict[str, MenuItem] = {}
_orders: dict[str, list[str]] = {}   # username → [item_id, ...]


# ── DB warm-up ────────────────────────────────────────────────────────────────

def load_orders_from_db() -> None:
    """Populate the in-memory _orders dict from SQLite on service startup."""
    global _orders
    _orders = load_orders()
    total = sum(len(v) for v in _orders.values())
    logger.info(
        "Loaded %d order records for %d customers from SQLite",
        total,
        len(_orders),
    )


# ── Seed ──────────────────────────────────────────────────────────────────────

def load_seed(path: str) -> None:
    """Load menu items from a JSON seed file into the in-memory store.

    The seed file is a JSON array of MenuItem-compatible dicts.
    Missing fields fall back to schema defaults.
    Skips the file silently if it does not exist.
    """
    seed_path = Path(path)
    if not seed_path.exists():
        logger.warning("Seed file not found at %s — starting with empty menu", path)
        return

    with seed_path.open() as f:
        items: list[dict] = json.load(f)

    for raw in items:
        item = MenuItem(**raw)
        _menu[item.item_id] = item

    logger.info("Loaded %d menu items from seed file %s", len(_menu), path)


# ── Menu CRUD ─────────────────────────────────────────────────────────────────

def get_all(
    category: str | None = None,
    available_only: bool = True,
) -> list[MenuItem]:
    """Return all menu items, optionally filtered by category and availability."""
    items = list(_menu.values())
    if available_only:
        items = [i for i in items if i.available]
    if category:
        items = [i for i in items if i.category.lower() == category.lower()]
    return items


def get_by_id(item_id: str) -> MenuItem | None:
    """Return a single menu item by its ID, or None if not found."""
    return _menu.get(item_id)


def create(payload: MenuItemCreate) -> MenuItem:
    """Create a new menu item with an auto-generated item_id."""
    item_id = f"{payload.name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
    item = MenuItem(item_id=item_id, **payload.model_dump())
    _menu[item_id] = item
    logger.info("Created menu item item_id=%s name=%s", item_id, item.name)
    return item


def update(item_id: str, payload: MenuItemUpdate) -> MenuItem | None:
    """Apply partial updates to an existing menu item.

    Only fields that are not None in the payload are updated.
    Returns the updated item, or None if item_id does not exist.
    """
    item = _menu.get(item_id)
    if not item:
        return None

    updated_data = item.model_dump()
    for field, value in payload.model_dump(exclude_none=True).items():
        updated_data[field] = value

    updated_item = MenuItem(**updated_data)
    _menu[item_id] = updated_item
    logger.info("Updated menu item item_id=%s", item_id)
    return updated_item


def delete(item_id: str) -> bool:
    """Remove a menu item. Returns True if deleted, False if not found."""
    if item_id not in _menu:
        return False
    del _menu[item_id]
    logger.info("Deleted menu item item_id=%s", item_id)
    return True


# ── Order history ─────────────────────────────────────────────────────────────

def record_order(username: str, item_id: str, device_id: str = "unknown") -> None:
    """Record that a customer ordered an item.

    Increments the item's order_count and appends to the customer's history.
    """
    if item_id not in _menu:
        logger.warning("record_order: unknown item_id=%s", item_id)
        return

    # Increment global order count on the menu item
    item = _menu[item_id]
    _menu[item_id] = item.model_copy(update={"order_count": item.order_count + 1})

    # Append to customer history (in-memory)
    _orders.setdefault(username, []).append(item_id)

    # Persist to SQLite
    insert_order(username, item_id, device_id)

    logger.info("Order recorded username=%s item_id=%s device_id=%s", username, item_id, device_id)


def get_order_history(username: str) -> list[str]:
    """Return the ordered list of item_ids for a customer (oldest first)."""
    return _orders.get(username, [])


# ── Recommendation ────────────────────────────────────────────────────────────

def get_recommendations(username: str, limit: int = 5) -> list[MenuItem]:
    """Return personalised menu recommendations for a recognised customer.

    Strategy (in priority order):
    1. Items the customer has ordered before, ranked by frequency (personalised).
    2. Fill remaining slots with globally popular items the customer has NOT ordered.
    3. If still not enough, fill with any available items sorted by order_count.

    All returned items must be currently available.
    """
    history = _orders.get(username, [])
    available = {i.item_id: i for i in get_all(available_only=True)}

    recommended: list[MenuItem] = []
    seen: set[str] = set()

    # Step 1 — personalised: items the customer ordered before, by frequency
    if history:
        freq = Counter(history)
        for item_id, _ in freq.most_common():
            if item_id in available and item_id not in seen:
                recommended.append(available[item_id])
                seen.add(item_id)
            if len(recommended) >= limit:
                return recommended

    # Step 2 — popular items the customer hasn't tried yet
    popular = sorted(available.values(), key=lambda x: x.order_count, reverse=True)
    for item in popular:
        if item.item_id not in seen:
            recommended.append(item)
            seen.add(item.item_id)
        if len(recommended) >= limit:
            return recommended

    return recommended

# ── Save ──────────────────────────────────────────────────────────────────────

def save_menu(path: str) -> None:
    """บันทึก menu items ลงไฟล์ JSON"""
    items = list(_menu.values())
    
    with open(path, 'w') as f:
        json.dump(
            [item.model_dump() for item in items],
            f,
            indent=2
        )
    
    logger.info("Saved %d menu items to %s", len(items), path)