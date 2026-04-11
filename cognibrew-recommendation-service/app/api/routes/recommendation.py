"""
HTTP API for the Frontend to query the latest recommendation.

The Frontend calls GET /recommendation/{device_id} after receiving
a face.recognized WebSocket event (or on a polling interval).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models.schemas import NoRecommendationResponse, RecommendationResponse
from src.consumer import RecommendationConsumer
from src.core.store import get_all, get_recommendation

router = APIRouter(prefix="/recommendation", tags=["recommendation"])

_consumer = RecommendationConsumer()


class TriggerRequest(BaseModel):
    username: str
    score: float


@router.post("/trigger", summary="Manually trigger a recommendation (debug only)")
async def trigger_recommendation(body: TriggerRequest) -> dict:
    """Simulate a face.recognized event without RabbitMQ.
    Used for local testing with the dummy recognition consumer.
    """
    from src.schemas.proto.face_result_pb2 import FaceRecognized  # type: ignore

    proto = FaceRecognized(username=body.username, score=body.score, bbox=[])
    _consumer._on_face_recognized(proto.SerializeToString())
    return {"status": "ok", "username": body.username}


@router.get(
    "/{username}",
    response_model=RecommendationResponse,
    responses={404: {"model": NoRecommendationResponse}},
)
async def get_latest_recommendation(username: str) -> JSONResponse:
    """Return the latest personalised recommendation for a given customer.

    Returns 200 with the recommendation if one exists.
    Returns 404 with a message if no recognition has occurred yet.
    """
    result = get_recommendation(username)

    if result is None:
        body = NoRecommendationResponse(username=username)
        return JSONResponse(status_code=404, content=body.model_dump())

    response = RecommendationResponse(
        username=result.username,
        score=result.score,
        items=result.items,
        fetched_at=result.fetched_at,
    )
    return JSONResponse(status_code=200, content=response.model_dump())


@router.get("/", response_model=list[RecommendationResponse])
async def get_all_recommendations() -> list[dict]:
    """Return the latest recommendation for all users (for debugging)."""
    results = get_all()
    return [
        RecommendationResponse(
            username=r.username,
            score=r.score,
            items=r.items,
            fetched_at=r.fetched_at,
        ).model_dump()
        for r in results
    ]
