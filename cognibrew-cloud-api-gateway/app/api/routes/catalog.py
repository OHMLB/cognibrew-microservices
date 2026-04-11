"""
Catalog routes — proxies ALL requests to the Menu/Catalog Service.

Full CRUD for menu items is exposed here so the Gateway is the single
entry point for both the Barista Frontend and any admin tooling.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import HttpClientDep, JWTDep
from app.core.config import settings
from app.models.schemas import (
    MenuItem,
    MenuItemCreate,
    MenuItemDeleteResponse,
    MenuItemUpdate,
    MenuListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])

_BASE = settings.CATALOG_SERVICE_URL


# ── READ ──────────────────────────────────────────────────────────────────────

@router.get("/menu", response_model=MenuListResponse)
async def list_menu(
    client: HttpClientDep,
    category: str | None = Query(None, description="Filter by category e.g. Hot, Cold"),
    available_only: bool = Query(True, description="Return only available items"),
) -> JSONResponse:
    """Return the full menu list from the Catalog Service."""
    params: dict = {"available_only": available_only}
    if category:
        params["category"] = category
    try:
        resp = await client.get(f"{_BASE}/api/v1/menu/", params=params)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Catalog service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/menu/{item_id}", response_model=MenuItem)
async def get_menu_item(item_id: str, client: HttpClientDep) -> JSONResponse:
    """Return a single menu item by ID."""
    try:
        resp = await client.get(f"{_BASE}/api/v1/menu/{item_id}")
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Catalog get item failed item_id=%s: %s", item_id, exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ── CREATE ────────────────────────────────────────────────────────────────────

@router.post("/menu", response_model=MenuItem, status_code=201)
async def create_menu_item(payload: MenuItemCreate, client: HttpClientDep, _: JWTDep) -> JSONResponse:
    """Create a new menu item.

    The Catalog Service auto-generates the item_id and returns the full item.
    Typically called by admin tooling to add new drinks or food to the menu.
    """
    try:
        resp = await client.post(
            f"{_BASE}/api/v1/menu/",
            json=payload.model_dump(),
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Catalog create item failed: %s", exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    logger.info("Created menu item: %s", resp.json().get("item_id"))
    return JSONResponse(content=resp.json(), status_code=201)


# ── UPDATE ────────────────────────────────────────────────────────────────────

@router.patch("/menu/{item_id}", response_model=MenuItem)
async def update_menu_item(
    item_id: str,
    payload: MenuItemUpdate,
    client: HttpClientDep,
    _: JWTDep,
) -> JSONResponse:
    """Partially update an existing menu item.

    Only fields provided in the request body are changed.
    Useful for toggling availability (e.g. sold-out) or updating price.
    """
    try:
        resp = await client.patch(
            f"{_BASE}/api/v1/menu/{item_id}",
            json=payload.model_dump(exclude_none=True),
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Catalog update item failed item_id=%s: %s", item_id, exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    logger.info("Updated menu item item_id=%s", item_id)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ── DELETE ────────────────────────────────────────────────────────────────────

@router.delete("/menu/{item_id}", status_code=204)
async def delete_menu_item(item_id: str, client: HttpClientDep, _: JWTDep) -> Response:
    """Remove a menu item from the catalog permanently.

    Returns 204 No Content on success.
    Returns 404 if the item does not exist (forwarded from Catalog Service).
    """
    try:
        resp = await client.delete(f"{_BASE}/api/v1/menu/{item_id}")
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Catalog delete item failed item_id=%s: %s", item_id, exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    logger.info("Deleted menu item item_id=%s", item_id)
    return Response(status_code=204)


# ── RECOMMENDATION ────────────────────────────────────────────────────────────

@router.get("/recommendation/{username}", response_model=list[MenuItem])
async def get_recommendation(
    username: str,
    client: HttpClientDep,
    limit: int = Query(5, ge=1, le=20, description="Max number of recommendations"),
) -> JSONResponse:
    """Return personalised menu recommendations for a recognised customer."""
    try:
        resp = await client.get(
            f"{_BASE}/api/v1/recommendation/{username}",
            params={"limit": limit},
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Recommendation failed for username=%s: %s", username, exc)
        raise HTTPException(status_code=503, detail="Catalog service unavailable") from exc
    return JSONResponse(content=resp.json(), status_code=resp.status_code)
