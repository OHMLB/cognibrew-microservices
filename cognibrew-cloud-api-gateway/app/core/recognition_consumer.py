"""
Recognition consumer — subscribes to RabbitMQ face.recognized events
and keeps the latest recognition result in memory for SSE streaming.

Message format: FaceRecognized protobuf (face_result.proto)
  - bbox:     repeated int32  [x1, y1, x2, y2]
  - username: string
  - score:    float (cosine similarity)
"""

import logging
import threading

import pika

from app.core.config import settings
from app.proto.face_result_pb2 import FaceRecognized  # type: ignore

logger = logging.getLogger(__name__)

_lock: threading.Lock = threading.Lock()
_latest: dict = {}


def get_latest() -> dict:
    with _lock:
        return _latest.copy()


def _on_message(ch, method, properties, body: bytes) -> None:
    msg = FaceRecognized()
    msg.ParseFromString(body)

    with _lock:
        _latest.clear()
        _latest.update({
            "bbox": list(msg.bbox),
            "username": msg.username,
            "score": round(msg.score, 4),
        })

    ch.basic_ack(delivery_tag=method.delivery_tag)
    logger.info(
        "Recognition event received: username=%s score=%.2f",
        msg.username,
        msg.score,
    )


def _start() -> None:
    credentials = pika.PlainCredentials(settings.RABBITMQ_USERNAME, settings.RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=credentials,
        )
    )
    channel = connection.channel()
    channel.exchange_declare(
        exchange="cognibrew.inference",
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(
        queue="cognibrew.gateway.face_recognized",
        durable=True,
    )
    channel.queue_bind(
        queue="cognibrew.gateway.face_recognized",
        exchange="cognibrew.inference",
        routing_key="face.recognized",
    )
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue="cognibrew.gateway.face_recognized",
        on_message_callback=_on_message,
    )
    logger.info(
        "Recognition consumer started — %s:%s",
        settings.RABBITMQ_HOST,
        settings.RABBITMQ_PORT,
    )
    channel.start_consuming()


def start_in_background() -> None:
    threading.Thread(
        target=_start,
        daemon=True,
        name="recognition-consumer",
    ).start()
