"""
Recommendation Service entry point.

Starts two concurrent components:
  1. RecommendationConsumer  — background daemon thread
     Subscribes to RabbitMQ face.recognized events, fetches recommendations
     from the Catalog Service, and stores them in the in-memory store.

  2. FastAPI HTTP server  — main thread (via uvicorn)
     Exposes GET /recommendation/{device_id} so the Frontend can poll
     for the latest recommendation at any time.
"""

import logging
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.main import api_router
from src.consumer import RecommendationConsumer
from src.core.config import settings
from src.core.db import init_db
from src.core.logger import setup_logging
from src.core.store import load_from_db

setup_logging()
logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


def _start_consumer() -> None:
    """Run the RabbitMQ consumer with exponential-backoff retry."""
    import time
    delay = 2
    max_delay = 30
    while True:
        try:
            consumer = RecommendationConsumer()
            consumer.start()
        except Exception:
            logger.exception(
                "RecommendationConsumer crashed — retrying in %ss", delay
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # 1. Ensure SQLite schema exists
    init_db()
    # 2. Warm up in-memory store from SQLite (survive restarts)
    load_from_db()
    logger.info("Recommendation store warmed up from SQLite")

    if settings.DEBUG:
        logger.info("DEBUG mode — skipping RabbitMQ consumer (use POST /trigger instead)")
    else:
        logger.info("Starting RecommendationConsumer thread...")
        thread = threading.Thread(target=_start_consumer, daemon=True, name="recommendation-consumer")
        thread.start()
    logger.info("CogniBrew Recommendation Service ready")
    yield
    logger.info("CogniBrew Recommendation Service shutting down")


app = FastAPI(
    title="CogniBrew Recommendation Service",
    description=(
        "Edge-side service that listens for face.recognized events, "
        "fetches personalised menu recommendations from the Catalog Service, "
        "and exposes them via HTTP for the Barista Frontend."
    ),
    version="0.1.0",
    openapi_url=f"{settings.API_PREFIX_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX_STR)
