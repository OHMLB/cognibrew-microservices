"""
Menu routes — full CRUD for menu items.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.crud import store
from app.models.schemas import MenuItem, MenuItemCreate, MenuItemUpdate, MenuListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/menu", tags=["menu"])

"""
Only raise HTTPException when the query parameters are invalid. 
If no items match the filters, return an empty list with total=0 instead of 404.
"""

@router.get("/", response_model=MenuListResponse)
async def list_menu(
    category: str | None = Query(None, description="Filter by category e.g. 'Hot', 'Cold'"),
    available_only: bool = Query(True, description="Return only currently available items"),
) -> MenuListResponse:
    """Return all menu items with optional filters."""
    items = store.get_all(category=category, available_only=available_only)
    return MenuListResponse(items=items, total=len(items))


@router.get("/{item_id}", response_model=MenuItem)
async def get_menu_item(item_id: str) -> MenuItem:
    """Return a single menu item by ID."""
    item = store.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Menu item '{item_id}' not found")
    return item


@router.post("/", response_model=MenuItem, status_code=201)
async def create_menu_item(payload: MenuItemCreate) -> MenuItem:
    """Create a new menu item. Returns the created item with its generated item_id."""
    item = store.create(payload)
    logger.info("POST /menu → created item_id=%s", item.item_id)
    return item


@router.patch("/{item_id}", response_model=MenuItem)
async def update_menu_item(item_id: str, payload: MenuItemUpdate) -> MenuItem:
    """Partially update an existing menu item (only provided fields are changed)."""
    item = store.update(item_id, payload)
    if not item:
        raise HTTPException(status_code=404, detail=f"Menu item '{item_id}' not found")
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_menu_item(item_id: str) -> None:
    """Remove a menu item from the catalog."""
    if not store.delete(item_id):
        raise HTTPException(status_code=404, detail=f"Menu item '{item_id}' not found")
