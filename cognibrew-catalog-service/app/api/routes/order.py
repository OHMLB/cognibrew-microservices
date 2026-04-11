"""
Order routes — record customer orders to build recommendation history.

Called by the barista UI (via the API Gateway) when a customer places an order.
Each recorded order increments the item's global order_count and appends to
the customer's personalised history, which feeds the recommendation engine.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.crud import store
from app.models.schemas import OrderRecord, OrderResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["order"])


@router.post("/", response_model=OrderResponse)
async def record_order(payload: OrderRecord) -> OrderResponse:
    """Record that a customer ordered a menu item.

    - Increments the item's ``order_count`` (used for popularity ranking).
    - Appends the item to the customer's order history (used for personalised recommendations).
    """
    if not store.get_by_id(payload.item_id):
        raise HTTPException(
            status_code=404,
            detail=f"Menu item '{payload.item_id}' not found",
        )

    store.record_order(
        username=payload.username,
        item_id=payload.item_id,
        device_id=payload.device_id,
    )
    return OrderResponse(status="ok", username=payload.username, item_id=payload.item_id)


@router.get("/history/{username}", response_model=list[str])
async def get_order_history(username: str) -> list[str]:
    """Return the ordered list of item_ids for a customer (oldest first).

    Useful for the barista UI to display what the customer usually orders.
    """
    history = store.get_order_history(username)
    logger.info("Order history for username=%s → %d records", username, len(history))
    return history
