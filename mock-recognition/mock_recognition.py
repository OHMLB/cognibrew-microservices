#!/usr/bin/env python3
"""
Mock Recognition Service
Publishes FaceRecognized protobuf messages to RabbitMQ
mimicking the real edge recognition service.

Flow:
  mock_recognition.py
      → RabbitMQ (cognibrew.inference / face.recognized)
      → Recommendation Service consumer
      → Catalog Service (fetch recommendations)
      → Store in memory/SQLite
      → Gateway SSE stream

Usage:
  # Send once:
  python mock_recognition.py --username alice --score 0.92

  # Loop every 5 seconds, 3 times:
  python mock_recognition.py --username alice --score 0.92 --count 3 --interval 5

  # Interactive mode (pick random user each time):
  python mock_recognition.py --random --count 10 --interval 4
"""

import argparse
import random
import time
import struct

import pika

# ─── Inline protobuf serializer (no generated pb2 needed) ──────────────────
# FaceRecognized { repeated int32 bbox=1; string username=2; float score=3; }

def _encode_varint(value: int) -> bytes:
    bits = value & 0x7F
    value >>= 7
    result = b""
    while value:
        result += bytes([0x80 | bits])
        bits = value & 0x7F
        value >>= 7
    result += bytes([bits])
    return result


def _encode_field_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def encode_face_recognized(
    bbox: list[int],
    username: str,
    score: float,
    embedding: list[float] | None = None,
    face_id: str = "",
) -> bytes:
    """Manually encode FaceRecognized protobuf (wire format).

    Fields (matches face_result.proto):
      1: repeated int32  bbox
      2: string          username
      3: float           score
      4: repeated float  embedding
      5: string          face_id
    """
    out = b""

    # field 1: repeated int32 bbox (wire type 0 = varint, one per element)
    for b in bbox:
        out += _encode_field_tag(1, 0)
        out += _encode_varint(b)

    # field 2: string username (wire type 2 = length-delimited)
    encoded_name = username.encode("utf-8")
    out += _encode_field_tag(2, 2)
    out += _encode_varint(len(encoded_name))
    out += encoded_name

    # field 3: float score (wire type 5 = 32-bit fixed)
    out += _encode_field_tag(3, 5)
    out += struct.pack("<f", score)

    # field 4: repeated float embedding (packed, wire type 2)
    if embedding:
        packed = struct.pack(f"<{len(embedding)}f", *embedding)
        out += _encode_field_tag(4, 2)
        out += _encode_varint(len(packed))
        out += packed

    # field 5: string face_id (wire type 2 = length-delimited)
    if face_id:
        encoded_fid = face_id.encode("utf-8")
        out += _encode_field_tag(5, 2)
        out += _encode_varint(len(encoded_fid))
        out += encoded_fid

    return out


# ─── RabbitMQ publisher ────────────────────────────────────────────────────

EXCHANGE      = "cognibrew.inference"
ROUTING_KEY   = "face.recognized"
FAKE_USERS    = ["alice", "bob", "sukit", "charlie"]


def publish(
    username: str,
    score: float,
    host: str = "localhost",
    port: int = 5672,
    rabbit_user: str = "guest",
    rabbit_pass: str = "guest",
) -> None:
    credentials = pika.PlainCredentials(rabbit_user, rabbit_pass)
    connection  = pika.BlockingConnection(
        pika.ConnectionParameters(host=host, port=port, credentials=credentials)
    )
    channel = connection.channel()

    channel.exchange_declare(
        exchange=EXCHANGE,
        exchange_type="topic",
        durable=True,
    )

    # Generate a dummy embedding vector (128-dim, random unit-ish values)
    embedding = [round(random.uniform(-1.0, 1.0), 4) for _ in range(128)]
    face_id   = f"face-{username}-mock"

    body = encode_face_recognized(
        bbox=[100, 80, 220, 200],
        username=username,
        score=score,
        embedding=embedding,
        face_id=face_id,
    )

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=ROUTING_KEY,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/octet-stream",
        ),
    )
    connection.close()
    print(f"Published → username={username!r}  score={score:.3f}")


# ─── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Mock recognition service publisher")
    parser.add_argument("--username", default="alice",       help="Username to recognise")
    parser.add_argument("--score",    type=float, default=0.92, help="Cosine similarity score (0-1)")
    parser.add_argument("--random",   action="store_true",   help="Pick a random user each time")
    parser.add_argument("--count",    type=int,   default=1,    help="Number of messages to send")
    parser.add_argument("--interval", type=float, default=3.0,  help="Seconds between messages")
    parser.add_argument("--host",     default="rabbitmq",    help="RabbitMQ host")
    parser.add_argument("--port",     type=int,   default=5672, help="RabbitMQ port")
    parser.add_argument("--user",     default="guest",        help="RabbitMQ username")
    parser.add_argument("--password", default="guest",        help="RabbitMQ password")
    args = parser.parse_args()

    print(f"Mock Recognition Service")
    print(f"  RabbitMQ  : {args.host}:{args.port}")
    print(f"  Exchange  : {EXCHANGE}")
    print(f"  Routing   : {ROUTING_KEY}")
    print(f"  Messages  : {args.count}  (interval={args.interval}s)")
    print()

    for i in range(args.count):
        username = random.choice(FAKE_USERS) if args.random else args.username
        score    = round(random.uniform(0.75, 0.99), 3) if args.random else args.score

        print(f"[{i+1}/{args.count}] Sending face.recognized ...")
        try:
            publish(
                username=username,
                score=score,
                host=args.host,
                port=args.port,
                rabbit_user=args.user,
                rabbit_pass=args.password,
            )
        except Exception as exc:
            print(f"Failed: {exc}")

        if i < args.count - 1:
            time.sleep(args.interval)

    print("\nDone.")


if __name__ == "__main__":
    main()
