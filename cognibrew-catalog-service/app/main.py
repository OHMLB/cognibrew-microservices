from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.routing import APIRoute

import logging

from app.api.main import api_router
from app.core.config import settings
from app.core.logger import setup_logging
from app.crud.db import init_db
from app.crud.store import load_orders_from_db, load_seed, save_menu

setup_logging()
logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """On startup: init SQLite DB, seed menu, restore order history."""
    # 1. Ensure DB schema exists
    init_db()
    # 2. Seed menu from JSON file
    load_seed(settings.MENU_SEED_FILE)
    # 3. Restore order history from SQLite into the in-memory dict
    load_orders_from_db()
    logger.info("CogniBrew Catalog Service ready")
    yield
    save_menu(settings.MENU_SEED_FILE)
    logger.info("CogniBrew Catalog Service shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Manages the CogniBrew menu catalog. "
        "Provides menu CRUD, order recording, and personalised recommendations."
    ),
    version="0.1.0",
    openapi_url=f"{settings.API_PREFIX_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_PREFIX_STR)
