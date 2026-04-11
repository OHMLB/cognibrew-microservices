"""
Utility routes — health check for the gateway and all downstream services.
"""

import logging

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import GatewayHealthResponse, ServiceHealth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/utils", tags=["utils"])

# _DOWNSTREAM_SERVICES = {
#     "catalog-service": f"{settings.CATALOG_SERVICE_URL}/api/v1/utils/health-check/",
#     "feedback-service": f"{settings.FEEDBACK_SERVICE_URL}/api/v1/utils/health-check/",
#     "notification-service": f"{settings.NOTIFICATION_SERVICE_URL}/api/v1/utils/health-check/",
# }

_DOWNSTREAM_SERVICES = {
    "catalog-service": f"{settings.CATALOG_SERVICE_URL}/api/v1/utils/health-check/"
}


@router.get("/health-check/")
async def health_check() -> bool:
    return True


@router.get("/health/", response_model=GatewayHealthResponse)
async def full_health_check() -> GatewayHealthResponse:
    """Ping all downstream services and return their status.

    Returns a combined health report so the Frontend (or ops team) can see
    at a glance which services are up or down.

    Each service is probed with a GET to its ``/api/v1/utils/health-check/``
    endpoint with a 5-second timeout.
    """
    service_statuses: list[ServiceHealth] = []

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in _DOWNSTREAM_SERVICES.items():
            try:
                resp = await client.get(url)
                status = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
            except Exception as exc:
                logger.warning("Health check failed for %s: %s", name, exc)
                status = "unreachable"

            service_statuses.append(ServiceHealth(service=name, status=status))
            logger.info("Health check %s → %s", name, status)

    return GatewayHealthResponse(gateway="ok", services=service_statuses)
