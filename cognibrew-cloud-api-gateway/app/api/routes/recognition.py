"""
Recognition routes — SSE stream of face.recognized events from RabbitMQ.

The recognition consumer runs as a background daemon thread and keeps
the latest recognition result in memory.  This endpoint streams it to
the Barista Frontend as Server-Sent Events (SSE).
"""

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings

if settings.DEBUG:
    from app.core.recognition_consumer_dummy import get_latest
else:
    from app.core.recognition_consumer import get_latest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognition", tags=["recognition"])


async def _recognition_stream():
    """Yield new recognition events as SSE whenever the latest result changes."""
    last_seen = None
    while True:
        data = get_latest()
        if data and data != last_seen:
            last_seen = data.copy()
            yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.5)


@router.get("/stream", summary="SSE stream of face recognition events")
async def stream_recognition():
    """Server-Sent Events endpoint for the Barista Frontend.

    Streams the latest face.recognized event in real-time.
    Each event is a JSON object:
    {
        "bbox":     [x1, y1, x2, y2],
        "username": "alice",
        "score":    0.87
    }
    """
    logger.info("SSE client connected to recognition stream")
    return StreamingResponse(
        _recognition_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
