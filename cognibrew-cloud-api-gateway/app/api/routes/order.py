"""
Order routes — proxies order requests to the Catalog Service.

Called by the Barista Frontend when a customer places an order.
Each recorded order updates the customer's history in the Catalog Service,
which feeds the recommendation engine for future visits.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import HttpClientDep, JWTDep
from app.core.config import settings
from app.models.schemas import OrderRecord, OrderResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/order", tags=["order"])

_BASE = settings.CATALOG_SERVICE_URL


@router.post("/", response_model=OrderResponse)
async def record_order(payload: OrderRecord, client: HttpClientDep, _: JWTDep) -> OrderResponse:
    """Record that a recognised customer ordered a menu item.

    Forwards the order to the Catalog Service which:
    - Increments the item's global order_count (used for popularity ranking)
    - Appends to the customer's order history (used for personalised recommendations)
    """
    try:
        resp = await client.post(
            f"{_BASE}/api/v1/order/",
            json=payload.model_dump(),
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error(
            "Order failed username=%s item_id=%s: %s",
            payload.username,
            payload.item_id,
            exc,
        )
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc

    logger.info("Order recorded username=%s item_id=%s", payload.username, payload.item_id)
    return OrderResponse(**resp.json())


@router.get("/history/{username}", response_model=list[str])
async def get_order_history(username: str, client: HttpClientDep, _: JWTDep) -> list[str]:
    """Return the order history for a recognised customer.

    Returns a list of item_ids ordered from oldest to newest.
    Useful for the Barista Frontend to show what the customer usually orders.
    """
    try:
        resp = await client.get(f"{_BASE}/api/v1/order/history/{username}")
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Order history failed for username=%s: %s", username, exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc

    return resp.json()
