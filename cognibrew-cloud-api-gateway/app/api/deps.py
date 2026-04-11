from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from app.core.config import settings
from app.core.security import verify_jwt


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield a shared async HTTP client for proxying requests to downstream services."""
    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        yield client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

# Inject this into any route that requires a valid JWT.
# Usage: add `_: JWTDep` as a parameter — FastAPI will call verify_jwt automatically.
JWTDep = Annotated[dict, Depends(verify_jwt)]
