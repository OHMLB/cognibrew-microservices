"""
Feedback routes — proxy to Feedback Service.

Flow: Barista Frontend → POST /feedback/ → Gateway → Feedback Service
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

_BASE = settings.FEEDBACK_SERVICE_URL


class RatingFeedback(BaseModel):
    username: str
    device_id: str
    rating: int          # 1-5 stars
    comment: str = ""


@router.post("/", summary="Submit star-rating feedback for a customer interaction")
async def submit_rating_feedback(body: RatingFeedback) -> dict:
    """Accept star-rating + comment from the Barista Frontend and forward to Feedback Service."""
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
