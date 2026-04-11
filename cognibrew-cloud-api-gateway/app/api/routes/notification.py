"""
Notification routes — SignalR bridge between Notification Service and Barista Frontend.

Flow:
  Recognition Service  →  RabbitMQ (face.recognized)
  Recommendation Svc   →  RabbitMQ (menu.recommended)
                       →  Notification Service (C# SignalR hub at /chatHub)
                       →  Gateway (bridges SignalR → plain WebSocket for Frontend)
                       →  Frontend (Barista UI)

The Notification Service pushes via SignalR method "Notify" with:
  { FaceId, Score, Username, RecommendedMenu[], Message }

JWT must be passed as query param ?access_token=<token> to authenticate with the hub.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notification", tags=["notification"])

_BASE = settings.NOTIFICATION_SERVICE_URL


def _build_hub_url(token: str | None) -> str:
    """Build the SignalR hub URL with optional JWT token as query param."""
    url = f"{_BASE.rstrip('/')}/chatHub"
    if token:
        url += f"?access_token={token}"
    return url


def _parse_signalr_message(raw: str | bytes) -> dict | None:
    """
    Parse a SignalR text protocol message.

    SignalR text protocol frames are JSON terminated with ASCII 0x1E (record separator).
    A "Notify" invocation looks like:
      {"type":1,"target":"Notify","arguments":[{...}]}\x1e
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    # Strip SignalR record separator
    raw = raw.rstrip("\x1e").strip()
    if not raw:
        return None

    try:
        frame = json.loads(raw)
    except json.JSONDecodeError:
        return None

    # type 1 = Invocation, type 6 = Ping — ignore pings
    if frame.get("type") != 1:
        return None

    if frame.get("target") != "Notify":
        return None

    args = frame.get("arguments", [])
    if not args:
        return None

    return args[0]  # { FaceId, Score, Username, RecommendedMenu, Message }


def _to_frontend_event(payload: dict) -> dict:
    """Map Notification Service message fields to frontend-friendly format."""
    username = payload.get("Username") or payload.get("username", "")
    return {
        "event": "face_recognized" if username else "face_unknown",
        "face_id": payload.get("FaceId", ""),
        "username": username,
        "score": payload.get("Score") or payload.get("score", 0.0),
        "recommended_menu": payload.get("RecommendedMenu") or [],
        "message": payload.get("Message") or payload.get("message", ""),
    }


@router.websocket("/ws/{device_id}")
async def notification_websocket(websocket: WebSocket, device_id: str) -> None:
    """WebSocket endpoint for the Barista Frontend.

    The frontend connects here and passes the JWT token as a query param:
      ws://gateway/api/v1/notification/ws/{device_id}?access_token=<JWT>

    The gateway connects upstream to the Notification Service SignalR hub at:
      ws://notification-service/chatHub?access_token=<JWT>

    Messages received from SignalR "Notify" are mapped and forwarded to the frontend.
    """
    # Extract JWT from frontend query param to pass upstream
    token = websocket.query_params.get("access_token")

    await websocket.accept()
    logger.info("Frontend WS connected device_id=%s", device_id)

    hub_url = _build_hub_url(token)

    try:
        import websockets  # stdlib-compatible, already in requirements.txt

        # SignalR text protocol handshake
        handshake = json.dumps({"protocol": "json", "version": 1}) + "\x1e"

        async with websockets.connect(hub_url) as upstream_ws:
            logger.info("Connected to SignalR hub at %s", hub_url.split("?")[0])

            # Send handshake
            await upstream_ws.send(handshake)
            # Receive handshake response ({""}  + \x1e) — discard
            await upstream_ws.recv()

            async for raw in upstream_ws:
                payload = _parse_signalr_message(raw)
                if payload is None:
                    continue

                event = _to_frontend_event(payload)
                await websocket.send_json(event)
                logger.info(
                    "Relayed notification: username=%s face_id=%s score=%.2f",
                    event["username"],
                    event["face_id"],
                    event["score"],
                )

    except WebSocketDisconnect:
        logger.info("Frontend disconnected device_id=%s", device_id)
    except Exception as exc:
        logger.error("Notification WS bridge error device_id=%s: %s", device_id, exc)
        try:
            await websocket.close(code=1011, reason="Notification service unavailable")
        except Exception:
            pass
