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

_BEVERAGE_CATEGORIES = {"hot", "cold", "blended"}
_FOOD_CATEGORIES = {"food"}


def _pick_best(
    candidates: dict[str, MenuItem],
    category_set: set[str],
    freq: Counter,
    exclude: set[str],
) -> MenuItem | None:
    """Return the single best available item from a category group.

    Priority:
    1. Customer's most-frequently ordered item in this category.
    2. Globally most popular item in this category not yet ordered by customer.
    3. Any available item in this category (sorted by order_count descending).
    """
    pool = [
        item for item in candidates.values()
        if item.category.lower() in category_set and item.item_id not in exclude
    ]
    if not pool:
        return None

    # Step 1 — personalised (ordered before, highest frequency first)
    ordered_in_pool = sorted(
        [item for item in pool if item.item_id in freq],
        key=lambda x: freq[x.item_id],
        reverse=True,
    )
    if ordered_in_pool:
        return ordered_in_pool[0]

    # Step 2 & 3 — most popular (unordered by customer, then any)
    return sorted(pool, key=lambda x: x.order_count, reverse=True)[0]


def get_recommendations(username: str, limit: int = 5) -> list[MenuItem]:
    """Return exactly 2 recommendations:
      [0] — best beverage (Hot / Cold / Blended)
      [1] — best food item (Food)

    Selection strategy per slot (in priority order):
    1. If username is unknown (empty) or has no order history
       → return the globally most popular item in each category.
    2. Item the customer has ordered most frequently in that category.
    3. Globally most popular item in that category the customer has not tried.
    4. Any available item in that category, sorted by order_count descending.

    If a slot has no available item (e.g. no Food items in the menu),
    it is omitted from the result — so the response may be 0, 1, or 2 items.
    """
    is_known = bool(username) and username not in ("unknown", "") and username in _orders
    freq: Counter = Counter(_orders[username]) if is_known else Counter()
    available = {i.item_id: i for i in get_all(available_only=True)}
    seen: set[str] = set()

    recommended: list[MenuItem] = []

    # Slot 1 — beverage
    beverage = _pick_best(available, _BEVERAGE_CATEGORIES, freq, seen)
    if beverage:
        recommended.append(beverage)
        seen.add(beverage.item_id)

    # Slot 2 — food
    food = _pick_best(available, _FOOD_CATEGORIES, freq, seen)
    if food:
        recommended.append(food)
        seen.add(food.item_id)

    logger.info(
        "Recommendations for username=%s → beverage=%s food=%s",
        username,
        recommended[0].item_id if len(recommended) > 0 else "none",
        recommended[1].item_id if len(recommended) > 1 else "none",
    )
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