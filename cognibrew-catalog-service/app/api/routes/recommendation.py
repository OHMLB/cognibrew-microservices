"""
Recommendation routes.

When the recognition-service fires ``face.recognized``, the Frontend calls
GET /recommendation/{username} to fetch personalised menu suggestions for
the identified customer.

Always returns exactly 2 items (if available):
  [0] — best beverage (Hot / Cold / Blended)
  [1] — best food item (Food)
"""

import logging

from fastapi import APIRouter

from app.crud import store
from app.models.schemas import MenuItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.get("/{username}", response_model=list[MenuItem])
async def get_recommendation(username: str) -> list[MenuItem]:
    """Return 2 personalised recommendations for a recognised customer.

    Result is always ordered as:
      [0] best beverage (Hot / Cold / Blended) — personalised by order history, then popularity
      [1] best food item (Food)                — personalised by order history, then popularity

    A slot is omitted only if the menu has no available items in that category.
    """
    items = store.get_recommendations(username=username)
    logger.info(
        "Recommendation for username=%s → %d items returned",
        username,
        len(items),
    )
    return items
