"""
CogniBrew Full Loop Simulation
================================
Simulates: Login → Face Recognition → Notification → Recommendation → Order → Feedback

Usage:
    pip install httpx websockets
    python test_full_loop.py
"""

import asyncio
import json
import os
import struct
import subprocess
import sys
import httpx
import websockets

# ── Config ────────────────────────────────────────────────────────────────────
import os

GATEWAY       = os.getenv("GATEWAY",  "http://localhost:8001")
USERMGMT      = os.getenv("USERMGMT", "http://localhost:60080")
CATALOG       = os.getenv("CATALOG",  "http://localhost:8000")

EMAIL         = os.getenv("EMAIL",    "alice@cognibrew.com")
PASSWORD      = os.getenv("PASSWORD", "Alice@1234")
USERNAME      = os.getenv("USERNAME", "alice")   # used for recognition / recommendation
DEVICE_ID     = os.getenv("DEVICE_ID", "edge-001")

# ── Helpers ───────────────────────────────────────────────────────────────────
def section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)

def ok(msg):   print(f"  ✅  {msg}")
def fail(msg): print(f"  ❌  {msg}"); sys.exit(1)
def info(msg): print(f"  ℹ️   {msg}")


# ── Step 0: Create User ───────────────────────────────────────────────────────
def step_create_user():
    section("STEP 0 — Create User (skip if exists)")
    r = httpx.post(f"{USERMGMT}/user",
                   json={
                       "name": "Alice",
                       "surname": "Smith",
                       "email": EMAIL,
                       "role": "User",
                       "pwd": PASSWORD,
                   }, timeout=10)
    if r.status_code == 200:
        ok(f"User created: {EMAIL}")
    elif r.status_code == 400 and "duplicate" in r.text.lower():
        info(f"User already exists — skipping")
    else:
        info(f"Create user response {r.status_code}: {r.text} — continuing anyway")


# ── Step 1: Login ─────────────────────────────────────────────────────────────
def step_login() -> str:
    section("STEP 1 — Login")
    r = httpx.post(f"{USERMGMT}/token",
                   json={"username": EMAIL, "password": PASSWORD}, timeout=10)
    if r.status_code != 200:
        fail(f"Login failed {r.status_code}: {r.text}")
    token = r.json().get("access_token")
    if not token:
        fail(f"No access_token in response: {r.text}")
    ok(f"Logged in as '{EMAIL}'")
    info(f"Token: {token[:40]}...")
    return token


# ── Step 2: Fire Mock Face Recognition ───────────────────────────────────────
def step_fire_recognition():
    section("STEP 2 — Fire Mock Face Recognition")
    info(f"Sending face.recognized for username='{USERNAME}' score=0.95 ...")

    # Check if running inside Docker (no docker command available)
    in_docker = os.path.exists("/.dockerenv")

    if in_docker:
        # Publish directly to RabbitMQ via pika
        try:
            import pika
            RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            ch = conn.channel()
            ch.exchange_declare(exchange="cognibrew.inference", exchange_type="topic", durable=True)

            # Build minimal FaceRecognized protobuf manually (field 1=face_id, 2=username, 3=score)
            def encode_string(field_num, value):
                tag = (field_num << 3) | 2
                encoded = value.encode("utf-8")
                return bytes([tag, len(encoded)]) + encoded

            def encode_float(field_num, value):
                tag = (field_num << 3) | 5
                return bytes([tag]) + struct.pack("<f", value)

            import time, uuid
            face_id = f"test-{uuid.uuid4().hex[:8]}"
            body = encode_string(1, face_id) + encode_string(2, USERNAME) + encode_float(3, 0.95)

            ch.basic_publish(exchange="cognibrew.inference", routing_key="face.recognized", body=body)
            conn.close()
            ok("face.recognized published to RabbitMQ (via pika)")
        except ImportError:
            fail("pika not installed — run: pip install pika")
        except Exception as e:
            fail(f"RabbitMQ publish failed: {e}")
    else:
        # Running locally — use docker compose
        result = subprocess.run(
            ["docker", "compose", "--profile", "mock", "run", "--rm",
             "mock-recognition", "--username", USERNAME, "--score", "0.95"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            fail(f"mock-recognition failed:\n{result.stderr}")
        ok("face.recognized published to RabbitMQ")


# ── Step 3: Wait for Notification via WebSocket ───────────────────────────────
async def step_wait_notification(token: str) -> dict:
    section("STEP 3 — Wait for Notification (WebSocket)")
    ws_base = GATEWAY.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/api/v1/notification/ws/{DEVICE_ID}?access_token={token}"
    info(f"Connecting to {ws_url.split('?')[0]} ...")

    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            ok("WebSocket connected — waiting for Notify event (timeout 30s) ...")
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                event = json.loads(raw)
                customer = event.get("customer", {})
                ok(f"Notification received!")
                info(f"  event    : {event.get('event')}")
                info(f"  name     : {customer.get('name')}")
                info(f"  rank     : {customer.get('rank')}")
                info(f"  points   : {customer.get('points')}")
                info(f"  greeting : {customer.get('greeting')}")
                info(f"  image    : {'yes (base64)' if customer.get('image') else 'none'}")
                return event
            except asyncio.TimeoutError:
                fail("Timed out waiting for notification — is Notification Service running?")
    except Exception as e:
        fail(f"WebSocket error: {e}")
    return {}


# ── Step 4: Get Recommendation ────────────────────────────────────────────────
def step_get_recommendation(token: str) -> list:
    section("STEP 4 — Get Recommendation")
    r = httpx.get(
        f"{GATEWAY}/api/v1/catalog/recommendation/{USERNAME}",
        headers={"Authorization": f"Bearer {token}"}, timeout=10
    )
    if r.status_code != 200:
        fail(f"Recommendation failed {r.status_code}: {r.text}")
    items = r.json()
    ok(f"Got {len(items)} recommendation(s)")
    for i, item in enumerate(items):
        info(f"  [{i+1}] {item.get('name')} ({item.get('category')}) — ฿{item.get('price')}")
    return items


# ── Step 5: Place Order ───────────────────────────────────────────────────────
def step_place_order(token: str, items: list) -> str:
    section("STEP 5 — Place Order")
    if not items:
        fail("No items to order")

    item = items[0]
    item_id = item.get("item_id")
    info(f"Ordering '{item.get('name')}' (item_id={item_id}) ...")

    r = httpx.post(
        f"{GATEWAY}/api/v1/order/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"username": USERNAME, "item_id": item_id, "device_id": DEVICE_ID},
        timeout=10
    )
    if r.status_code != 200:
        fail(f"Order failed {r.status_code}: {r.text}")
    ok(f"Order placed — {r.json()}")
    return item_id


# ── Step 6: Submit Feedback ───────────────────────────────────────────────────
def step_submit_feedback(token: str, event: dict):
    section("STEP 6 — Submit Feedback")
    customer = event.get("customer", {})
    vector_id = customer.get("id") or customer.get("orderId")

    if not vector_id:
        info("No vectorId found in notification event — skipping feedback")
        return

    info(f"Submitting feedback=true for vectorId={vector_id} ...")
    r = httpx.put(
        f"{GATEWAY}/api/v1/feedback/{vector_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"feedback": "true"},
        timeout=10
    )
    if r.status_code == 200:
        ok(f"Feedback submitted: {r.json()}")
    else:
        info(f"Feedback response {r.status_code}: {r.text}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    print("\n🚀  CogniBrew Full Loop Simulation")
    print("    Gateway  :", GATEWAY)
    print("    Email    :", EMAIL)
    print("    Username :", USERNAME)

    # Step 0 — Create user
    step_create_user()

    # Step 1 — Login
    token = step_login()

    # Step 2 — Fire recognition (non-blocking, runs before WS connect)
    step_fire_recognition()

    # Step 3 — Wait for notification
    event = await step_wait_notification(token)

    # Step 4 — Get recommendation
    items = step_get_recommendation(token)

    # Step 5 — Place order
    if items:
        step_place_order(token, items)

    # Step 6 — Submit feedback
    step_submit_feedback(token, event)

    section("DONE 🎉")
    print("  Full loop completed successfully!\n")


if __name__ == "__main__":
    asyncio.run(main())
