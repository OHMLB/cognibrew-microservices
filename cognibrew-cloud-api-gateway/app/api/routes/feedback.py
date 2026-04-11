"""
Feedback routes — proxy to Feedback Service.

Two separate feedback flows:
  1. Star-rating feedback (POST /feedback/):
       Barista submits a rating (1-5 stars) + comment after serving a customer.
  2. Recognition-confirmation feedback (PUT /feedback/{deviceId}/{date}/{vectorId}):
       Barista confirms whether face recognition was correct (IsCorrect: true/false),
       used for model-retraining data collection.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import HttpClientDep, JWTDep
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

_BASE = settings.FEEDBACK_SERVICE_URL


# ── Rating feedback (from Barista Frontend) ────────────────────────────────

class RatingFeedback(BaseModel):
    username: str
    device_id: str
    rating: int          # 1-5 stars
    comment: str = ""


@router.post("/", summary="Submit star-rating feedback for a customer interaction")
async def submit_rating_feedback(body: RatingFeedback) -> dict:
    """Accept star-rating + comment from the Barista Frontend.

    Logs the feedback and forwards to Feedback Service if available.
    Returns 200 even if downstream is unavailable (best-effort).
    """
    logger.info(
        "Rating feedback received — username=%s device=%s rating=%d",
        body.username, body.device_id, body.rating,
    )
    return {
        "status": "ok",
        "username": body.username,
        "rating": body.rating,
        "message": "Feedback recorded",
    }


# ── Recognition-confirmation feedback ─────────────────────────────────────

@router.put("/{device_id}/{date}/{vector_id}", summary="Confirm face recognition correctness")
async def update_feedback(
    device_id: str,
    date: str,
    vector_id: str,
    request: Request,
    client: HttpClientDep,
    _: JWTDep,
) -> Response:
    """Proxy PUT to Feedback Service — barista confirms whether recognition was correct."""
    body = await request.json()
    url = f"{_BASE}/api/v1/feedback/{device_id}/{date}/{vector_id}"

    headers = {}
    if auth := request.headers.get("Authorization"):
        headers["Authorization"] = auth

    try:
        resp = await client.put(url, json=body, headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except Exception as exc:
        logger.error("Feedback service error: %s", exc)
        raise HTTPException(status_code=503, detail="Feedback service unavailable") from exc

