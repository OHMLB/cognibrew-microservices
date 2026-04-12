# CogniBrew Recommendation Service

Event-driven recommendation service for the CogniBrew platform. Consumes face recognition events from RabbitMQ, fetches personalised menu suggestions from the Catalog Service, and caches the result so the Barista Frontend can retrieve it on demand.

## Architecture

```
Recognition Service
        │
        │ face.recognized (protobuf)
        ▼
    RabbitMQ
  (cognibrew.inference exchange)
        │
        ▼
Recommendation Service  (:8002 host / :8000 container)
  │
  ├── Background consumer thread
  │     ├── Deserialise FaceRecognized protobuf (username, score, face_id)
  │     ├── GET /recommendation/{username} → Catalog Service
  │     ├── Store result in in-memory cache (keyed by username)
  │     └── Publish Recommendation protobuf → cognibrew.recommendation exchange
  │                                               │
  │                                               ▼
  │                                     Notification Service
  │
  └── HTTP API  (polled by API Gateway / Frontend)
        └── GET /api/v1/recommendation/{username}  — returns cached result
```

The service runs a **background thread** that consumes `face.recognized` messages and keeps an in-memory recommendation cache. The HTTP API is stateless — it simply reads from this cache.

In **DEBUG mode** (`DEBUG=true`) the RabbitMQ consumer is skipped entirely, enabling local development without a broker. A `/recommendation/trigger` endpoint is available in this mode to simulate face recognition events.

## API Endpoints

All routes are prefixed with `/api/v1`.

### Recommendation  (`/api/v1/recommendation`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/recommendation/{username}` | Return the latest cached recommendation for a customer |
| `GET` | `/recommendation/` | Return the latest recommendation for all users (debug) |
| `POST` | `/recommendation/trigger` | Simulate a `face.recognized` event without RabbitMQ (debug only) |

**Get recommendation example:**
```bash
curl http://localhost:8002/api/v1/recommendation/alice
```

Response (`200 OK` — recommendation available):
```json
{
  "username": "alice",
  "score": 0.92,
  "items": [
    {
      "item_id": "caffe-latte-hot",
      "name": "Caffe Latte",
      "price": 120.0,
      "category": "Hot",
      ...
    }
  ],
  "fetched_at": "2026-04-11T10:00:00"
}
```

Response (`404` — no recognition yet):
```json
{ "username": "alice", "message": "No recommendation available" }
```

**Trigger recommendation manually (debug):**
```bash
curl -X POST http://localhost:8002/api/v1/recommendation/trigger \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "score": 0.95}'
```

## Message Flow

### Input — `face.recognized`

- **Exchange:** `cognibrew.inference`
- **Routing key:** `face.recognized`
- **Queue:** `cognibrew.inference.face_recognized`
- **Encoding:** Protobuf (`FaceRecognized`)

| Field | Type | Description |
|---|---|---|
| `username` | `string` | Recognised customer username (empty if unknown) |
| `score` | `float` | Recognition confidence score (0.0–1.0) |
| `face_id` | `string` | Unique face vector ID |
| `bbox` | `repeated float` | Bounding box coordinates |

Unknown faces (empty `username`) are silently skipped.

### Output — `menu.recommended`

- **Exchange:** `cognibrew.recommendation`
- **Routing key:** `menu.recommended`
- **Encoding:** Protobuf (`Recommendation`)
- **Consumer:** Notification Service (pushes to Barista Frontend via SignalR)

| Field | Type | Description |
|---|---|---|
| `username` | `string` | Recognised customer username |
| `recommended_menu` | `repeated string` | Item names of the recommended drinks |
| `face_id` | `string` | Echoed from the input event |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `true` | `true` = skip RabbitMQ consumer (local dev mode) |
| `API_PREFIX_STR` | `/api/v1` | URL prefix for all routes |
| `DEVICE_ID` | `edge-device-01` | Identifier for this edge device instance |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `RABBITMQ_USERNAME` | `guest` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `guest` | RabbitMQ password |
| `RABBITMQ_INFERENCE_EXCHANGE_NAME` | `cognibrew.inference` | Exchange to consume from |
| `RABBITMQ_RECOMMENDATION_QUEUE_NAME` | `cognibrew.inference.face_recognized` | Queue name |
| `RABBITMQ_FACE_RECOGNIZED_ROUTING_KEY` | `face.recognized` | Input routing key |
| `RABBITMQ_RECOMMENDATION_EXCHANGE_NAME` | `cognibrew.recommendation` | Exchange to publish to |
| `RABBITMQ_MENU_RECOMMENDED_ROUTING_KEY` | `menu.recommended` | Output routing key |
| `CATALOG_SERVICE_URL` | `http://catalog-service:8000` | Catalog Service base URL |
| `CATALOG_RECOMMENDATION_LIMIT` | `5` | Number of recommendations to request |
| `CATALOG_HTTP_TIMEOUT` | `10.0` | HTTP timeout when calling Catalog Service (seconds) |

## Deployment

### Docker Compose (from repo root)

```bash
cd cognibrew-gateway-catalog-recommendation
docker compose up --build
```

The service is exposed at **http://localhost:8002**. `rabbitmq` and `catalog-service` start automatically.

### Local development (no RabbitMQ)

```bash
pip install -r requirements.txt
DEBUG=true CATALOG_SERVICE_URL=http://localhost:8000 uvicorn app.main:app --reload --port 8002
```

Interactive docs: http://localhost:8002/docs

## Verification

```bash
# 1. Fire a mock face.recognized event
docker compose run --rm mock-recognition --username alice --score 0.95

# 2. Retrieve the cached recommendation
curl http://localhost:8002/api/v1/recommendation/alice

# 3. Check all cached recommendations
curl http://localhost:8002/api/v1/recommendation/
```

## Tech Stack

| Component | Version |
|---|---|
| Python | 3.10 |
| FastAPI | 0.115 |
| Uvicorn | 0.34 |
| httpx | 0.28 |
| pika (RabbitMQ) | 1.3 |
| protobuf | 6.32 |
| pydantic | 2.11 |
