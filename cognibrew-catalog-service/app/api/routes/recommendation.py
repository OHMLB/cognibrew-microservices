"""
Recommendation routes.

When the recognition-service fires ``face.recognized``, the Frontend calls
GET /recommendation/{username} to fetch personalised menu suggestions for
the identified customer.
"""

import logging

from fastapi import APIRouter, Query

from app.core.config import settings
from app.crud import store
from app.models.schemas import MenuItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.get("/{username}", response_model=list[MenuItem])
async def get_recommendation(
    username: str,
    limit: int = Query(
        settings.DEFAULT_RECOMMENDATION_LIMIT,
        ge=1,
        le=20,
        description="Max number of items to return",
    ),
) -> list[MenuItem]:
    """Return personalised menu recommendations for a recognised customer.

    Recommendation strategy (in order):
    1. Items the customer has ordered before (ranked by frequency).
    2. Globally popular items the customer has not yet tried.
    3. Any available item, sorted by order count.

    All returned items are guaranteed to be currently available.
    """
    items = store.get_recommendations(username=username, limit=limit)
    logger.info(
        "Recommendation for username=%s → %d items returned",
        username,
        len(items),
    )
    return items
