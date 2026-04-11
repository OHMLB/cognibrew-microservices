"""
Dummy recognition consumer — simulates face.recognized events without
needing RabbitMQ or a real edge device.

Used when DEBUG=True (local development / testing).
Fires a fake recognition event every INTERVAL seconds.
"""

import logging
import random
import threading
import time

import httpx

logger = logging.getLogger(__name__)

_lock: threading.Lock = threading.Lock()
_latest: dict = {}

FAKE_USERS             = ["alice", "bob", "sukit", "charlie"]
INTERVAL               = 8    # seconds between fake recognitions
RECOMMENDATION_TRIGGER = "http://localhost:8002/api/v1/recommendation/trigger"
DEVICE_ID              = "edge-device-01"


def get_latest() -> dict:
    with _lock:
        return _latest.copy()


def _call_trigger(username: str, score: float) -> None:
    try:
        httpx.post(
            RECOMMENDATION_TRIGGER,
            json={"username": username, "score": score, "device_id": DEVICE_ID},
            timeout=5.0,
        )
        logger.info("Triggered recommendation service for username=%s", username)
    except Exception as exc:
        logger.warning("Recommendation trigger failed (service not running?): %s", exc)


def _simulate() -> None:
    logger.info("Dummy recognition simulator started (interval=%ds)", INTERVAL)
    while True:
        time.sleep(INTERVAL)
        user  = random.choice(FAKE_USERS)
        score = round(random.uniform(0.70, 0.99), 3)
        with _lock:
            _latest.clear()
            _latest.update({
                "bbox":     [100, 80, 220, 200],
                "username": user,
                "score":    score,
            })
        logger.info("Dummy recognition: username=%s score=%.2f", user, score)
        _call_trigger(user, score)


def start_in_background() -> None:
    threading.Thread(
        target=_simulate,
        daemon=True,
        name="dummy-recognition-consumer",
    ).start()
