"""
RecommendationConsumer — background thread.

Lifecycle:
  1. Connect to RabbitMQ and subscribe to face.recognized
  2. On each message:
     a. Deserialise FaceRecognized protobuf  → username, device_id, score
     b. Call Catalog Service GET /recommendation/{username}
     c. Store the result in the in-memory store (keyed by device_id)
  3. The HTTP API reads from the store so the Frontend can poll at any time.

NOTE: device_id is NOT in the FaceRecognized protobuf (it carries bbox,
username, score).  We inject it from the DEVICE_ID env var so each edge
device runs its own recommendation-service instance.
"""

import os
import threading

import httpx

import logging

from src.core.config import settings
from src.core.message_queue import MessageQueue
from src.core.recommendation_publisher import RecommendationPublisher
from src.core.store import RecommendationResult, set_recommendation
from src.schemas.proto.face_result_pb2 import FaceRecognized
from src.schemas.proto.recommendation_pb2 import Recommendation

logger = logging.getLogger(__name__)

# Each edge device has its own device_id, injected via environment variable
_DEVICE_ID = os.getenv("DEVICE_ID", "edge-device-01")


class RecommendationConsumer:
    """Consumes face.recognized messages and updates the recommendation store."""

    def __init__(self) -> None:
        self._mq = MessageQueue()
        self._publisher = RecommendationPublisher()
        self._catalog_url = settings.CATALOG_SERVICE_URL
        self._limit = settings.CATALOG_RECOMMENDATION_LIMIT
        self._timeout = settings.CATALOG_HTTP_TIMEOUT

    def start(self) -> None:
        """Connect to RabbitMQ and start consuming (blocks the calling thread)."""
        self._mq.connect()
        self._mq.consume(self._on_face_recognized)

    def _on_face_recognized(self, body: bytes) -> None:
        """Handle a single face.recognized protobuf message.

        Steps:
          1. Deserialise the FaceRecognized message.
          2. Skip unknown faces (empty username).
          3. Call Catalog Service for personalised recommendations.
          4. Store result so the HTTP API can serve it to the Frontend.
        """
        msg = FaceRecognized()
        msg.ParseFromString(body)

        username: str = msg.username
        score: float = msg.score
        face_id: str = msg.face_id

        if not username:
            logger.info("Skipping face.recognized — unknown face (no username)")
            return

        logger.info(
            "face.recognized username=%s score=%.3f device_id=%s",
            username,
            score,
            _DEVICE_ID,
        )

        items = self._fetch_recommendations(username)
        if items is None:
            return  # catalog unreachable — skip, keep old recommendation

        result = RecommendationResult(
            username=username,
            score=score,
            items=items,
        )
        set_recommendation(result)
        logger.info(
            "Stored %d recommendations for username=%s",
            len(items),
            username,
        )

        self._publish_recommendation(username=username, score=score, items=items, face_id=face_id)

    def _publish_recommendation(
        self, username: str, score: float, items: list[dict], face_id: str = ""
    ) -> None:
        """Publish a Recommendation protobuf to cognibrew.recommendation exchange.

        Skipped in DEBUG mode (no RabbitMQ available).
        The Notification Service consumes this and pushes via SignalR to the frontend.
        """
        if settings.DEBUG:
            logger.debug(
                "DEBUG mode — skipping RabbitMQ publish for username=%s", username
            )
            return

        # Build list of menu item names for the notification payload
        recommended_menu = [
            item.get("name") or item.get("item_id", "") for item in items
        ]

        rec = Recommendation(
            username=username,
            recommended_menu=recommended_menu,
            face_id=face_id or f"{username}-{int(__import__('time').time())}",
        )
        body = rec.SerializeToString()
        threading.Thread(
            target=self._do_publish,
            args=(body, username),
            daemon=True,
        ).start()

    def _do_publish(self, body: bytes, username: str) -> None:
        try:
            self._publisher.publish(body)
        except Exception as exc:
            logger.error(
                "menu.recommended publish failed for username=%s: %s", username, exc
            )

    def _fetch_recommendations(self, username: str) -> list[dict] | None:
        """Call Catalog Service and return list of MenuItem dicts, or None on error."""
        url = f"{self._catalog_url}/api/v1/recommendation/{username}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, params={"limit": self._limit})
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error(
                "Failed to fetch recommendations for username=%s: %s",
                username,
                exc,
            )
            return None
