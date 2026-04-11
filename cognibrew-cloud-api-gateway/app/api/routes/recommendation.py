"""
Recommendation routes — proxy to Recommendation Service.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.api.deps import HttpClientDep, JWTDep
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendation", tags=["recommendation"])

_BASE = settings.RECOMMENDATION_SERVICE_URL


@router.get("/{username}", summary="Get latest recommendation for a customer")
async def get_recommendation(username: str, client: HttpClientDep, _: JWTDep) -> dict:
    try:
        resp = await client.get(f"{_BASE}/api/v1/recommendation/{username}")
        if resp.status_code == 404:
            return resp.json()
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        logger.error("Recommendation service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="Recommendation service unavailable")
