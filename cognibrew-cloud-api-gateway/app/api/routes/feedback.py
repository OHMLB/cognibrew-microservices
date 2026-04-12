"""
Feedback routes — proxy to Feedback Service.

Flow: Barista Frontend → PUT /feedback/{vectorId} → Gateway → Feedback Service
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import HttpClientDep
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

_BASE = settings.FEEDBACK_SERVICE_URL


class FeedbackBody(BaseModel):
    feedback: str   # "true" or "false"


@router.put("/{vector_id}", summary="Submit feedback for a recognition result")
async def submit_feedback(vector_id: str, body: FeedbackBody, request: Request, client: HttpClientDep) -> Response:
    """Proxy PUT /api/v1/feedback/{vectorId} to Feedback Service.

    Called by the Barista Frontend to confirm or reject a face recognition result.
    feedback = "true"  → recognition was correct
    feedback = "false" → recognition was wrong
    """
    # Forward Authorization header so Feedback Service can validate JWT
    auth_header = request.headers.get("Authorization")
    headers = {"Authorization": auth_header} if auth_header else {}

    try:
        resp = await client.put(
            f"{_BASE}/api/v1/feedback/{vector_id}",
            json=body.model_dump(),
            headers=headers,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Feedback failed for vector_id=%s: %s", vector_id, exc)
        raise HTTPException(status_code=503, detail="Feedback service unavailable") from exc

    logger.info("Feedback submitted vector_id=%s feedback=%s", vector_id, body.feedback)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )
