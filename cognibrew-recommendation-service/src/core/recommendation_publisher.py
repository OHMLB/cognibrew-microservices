"""
RecommendationPublisher — publishes menu.recommended events to RabbitMQ.

After the RecommendationConsumer computes personalised recommendations it
calls this publisher so the Notification Service (C# SignalR) can push
them to the Barista Frontend via WebSocket.

Exchange : cognibrew.recommendation   (topic, durable)
Routing  : menu.recommended
Payload  : Recommendation protobuf  (username, recommended_menu[], face_id)
"""

import logging

import pika

from src.core.config import settings

logger = logging.getLogger(__name__)


class RecommendationPublisher:
    """Thin pika wrapper for publishing to the recommendation exchange."""

    def __init__(self) -> None:
        self._exchange = settings.RABBITMQ_RECOMMENDATION_EXCHANGE_NAME
        self._routing_key = settings.RABBITMQ_MENU_RECOMMENDED_ROUTING_KEY
        self._connection: pika.BlockingConnection | None = None
        self._channel = None

    def _ensure_connected(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            return

        credentials = pika.PlainCredentials(
            username=settings.RABBITMQ_USERNAME,
            password=settings.RABBITMQ_PASSWORD,
        )
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
        )
        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

        # Declare exchange — idempotent, must match what Notification Service expects
        self._channel.exchange_declare(
            exchange=self._exchange,
            exchange_type="topic",
            durable=True,
        )
        logger.info(
            "RecommendationPublisher connected — exchange=%s routing_key=%s",
            self._exchange,
            self._routing_key,
        )

    def publish(self, body: bytes) -> None:
        """Publish a serialised Recommendation protobuf message."""
        try:
            self._ensure_connected()
            self._channel.basic_publish(
                exchange=self._exchange,
                routing_key=self._routing_key,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type="application/octet-stream",
                ),
            )
            logger.info(
                "Published menu.recommended → exchange=%s routing_key=%s",
                self._exchange,
                self._routing_key,
            )
        except Exception as exc:
            logger.error("Failed to publish menu.recommended: %s", exc)
            # Reset so the next call will reconnect
            self._channel = None
            self._connection = None
            raise

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            logger.info("RecommendationPublisher connection closed")
