from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

import logging

from app.api.main import api_router
from app.core.config import settings
from app.core.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "CogniBrew Cloud API Gateway starting — env=%s", settings.ENVIRONMENT
    )
    logger.info("Catalog service → %s", settings.CATALOG_SERVICE_URL)
    logger.info(
        "RabbitMQ → %s:%s", settings.RABBITMQ_HOST, settings.RABBITMQ_PORT
    )
    start_in_background()
    yield
    logger.info("CogniBrew Cloud API Gateway shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Central API Gateway for the CogniBrew cloud. "
        "Routes HTTP requests to Menu/Catalog, Feedback services "
        "and bridges WebSocket connections to the Notification service."
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
