from typing import Callable

import pika
from pika.adapters.blocking_connection import BlockingChannel

import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


class MessageQueue:
    """Pika wrapper — subscribes to face.recognized events on the inference exchange."""

    def __init__(self) -> None:
        self._exchange = settings.RABBITMQ_INFERENCE_EXCHANGE_NAME
        self._queue = settings.RABBITMQ_RECOMMENDATION_QUEUE_NAME
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def connect(self) -> None:
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

        # Declare the same topic exchange as recognition-service (idempotent)
        self._channel.exchange_declare(
            exchange=self._exchange,
            exchange_type="topic",
            durable=True,
        )

        # Declare our own queue and bind to face.recognized routing key
        self._channel.queue_declare(queue=self._queue, durable=True)
        self._channel.queue_bind(
            queue=self._queue,
            exchange=self._exchange,
            routing_key=settings.RABBITMQ_FACE_RECOGNIZED_ROUTING_KEY,
        )
        logger.info(
            "RabbitMQ connected — exchange=%s queue=%s routing_key=%s",
            self._exchange,
            self._queue,
            settings.RABBITMQ_FACE_RECOGNIZED_ROUTING_KEY,
        )

    @property
    def channel(self) -> BlockingChannel:
        if self._channel is None or self._channel.is_closed:
            self.connect()
        assert self._channel is not None
        return self._channel

    def consume(self, callback: Callable[[bytes], None]) -> None:
        """Start consuming face.recognized messages. Blocks the calling thread."""

        def _on_message(
            ch: BlockingChannel,
            method: pika.spec.Basic.Deliver,
            properties: pika.BasicProperties,
            body: bytes,
        ) -> None:
            try:
                callback(body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("Error handling face.recognized message")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue=self._queue,
            on_message_callback=_on_message,
        )
        logger.info("Waiting for face.recognized messages on queue '%s'...", self._queue)
        self.channel.start_consuming()

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            logger.info("RabbitMQ connection closed")
