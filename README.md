# CogniBrew Cloud Services — Overview

This document covers how the three core cloud services work together: **API Gateway**, **Catalog Service**, and **Recommendation Service**.

---

## Services at a Glance

| Service | Repo folder | Host Port | Role |
|---|---|---|---|
| API Gateway | `cognibrew-cloud-api-gateway` | `8001` | Single entry point for all frontend requests |
| Catalog Service | `cognibrew-catalog-service` | `8000` | Menu CRUD + recommendation data + order history |
| Recommendation Service | `cognibrew-recommendation-service` | `8002` | Consumes face recognition events → caches personalised menus |

---

## System Architecture

```
Recognition Service
        │
        │ face.recognized
        ▼
   ┌──────────┐
   │ RabbitMQ │◄── menu.recommended ── Recommendation Service (:8002)
   └──────────┘                                │
        │                                      │ HTTP GET /recommendation/{username}
        │ face.recognized                      ▼
        |                            ┌──────────────────┐
        │                            │  Catalog Service │
        │ face.recognized            │     (:8000)      │
        │ menu.recommended           │                  │
        ▼                            │ - Menu CRUD      │◄── HTTP proxy
   Notification Service              │ - Order history  │    from Gateway
   (WebSocket / SignalR only)        │ - Rec strategy   │
        │                            └──────────────────┘
        │ push via WebSocket / SignalR
        ▼
┌──────────────────────────────────────────────────────┐
│                  API Gateway  (:8001)                │
│                                                      │
│  /api/v1/auth     → User Management Service (:8003)  │
│  /api/v1/catalog  → Catalog Service (:8000)          │
│  /api/v1/order    → Catalog Service (:8000)          │
│  /api/v1/feedback → Feedback Service (:5001)         │
│  /api/v1/notification/ws  ← WebSocket push from Noti │
└──────────────────────────────┬───────────────────────┘
                               │ HTTP + WebSocket push
                               ▼
                    ┌─────────────────────┐
                    │   Barista Frontend  │
                    │   (localhost:3000)  │
                    └─────────────────────┘
```

---

## Request Flows

### 1. Barista browses the menu

```
Frontend → GET /api/v1/catalog/menu
         → API Gateway
         → Catalog Service GET /api/v1/menu/
         ← list of MenuItem[]
```

### 2. Customer is recognised — recommendation pushed to frontend

```
Recognition Service
  └─► RabbitMQ: face.recognized (protobuf)
        └─► Recommendation Service (background consumer)
              ├─► Catalog Service GET /api/v1/recommendation/{username}
              │     └─ returns personalised MenuItem[] (order history → popularity → any)
              ├─► in-memory cache update (keyed by username)
              └─► RabbitMQ: menu.recommended (protobuf)
                      └─► Notification Service (C# SignalR)
                              └─► API Gateway WebSocket bridge /api/v1/notification/ws/{device_id}
                                      └─► Frontend receives JSON event:
                                          {
                                            "event": "face_recognized",
                                            "username": "alice",
                                            "score": 0.92,
                                            "recommended_menu": ["Caffe Latte", "Cold Brew"]
                                          }
```

### 3. Frontend polls for the latest recommendation

```
Frontend → GET /api/v1/recommendation/{username}
         → API Gateway
         → Recommendation Service GET /api/v1/recommendation/{username}
         ← cached RecommendationResponse (username, score, items[], fetched_at)
```

### 4. Barista records a customer order

```
Frontend → POST /api/v1/catalog/order/
         → API Gateway (proxied — no auth required at gateway level)
         → Catalog Service POST /api/v1/order/
             ├─ increments item.order_count (popularity ranking)
             └─ appends item_id to customer order history (personalised recs)
```

---

## Data Ownership

| Data | Owned by | Storage |
|---|---|---|
| Menu items | Catalog Service | In-memory, seeded from JSON |
| Order history per customer | Catalog Service | In-memory |
| Item popularity (`order_count`) | Catalog Service | In-memory |
| Latest recommendation per customer | Recommendation Service | In-memory cache |
| JWT / user accounts | User Management Service | PostgreSQL via PgBouncer |

> All in-memory state is reset on container restart. For production use, the catalog and recommendation stores should be persisted to a database.

---

## RabbitMQ Exchanges & Routing Keys

| Exchange | Type | Routing Key | Producer | Consumer |
|---|---|---|---|---|
| `cognibrew.inference` | topic | `face.recognized` | Recognition Service | Recommendation Service |
| `cognibrew.recommendation` | topic | `menu.recommended` | Recommendation Service | Notification Service |

---

## Environment Variables Quick Reference

### API Gateway

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | No | `local` / `production` — controls downstream URLs |
| `DEBUG` | No | `true` disables RabbitMQ consumer |
| `JWT_SECRET_KEY` | **Yes** | Must match User Management Service |
| `JWT_ISSUER` | **Yes** | e.g. `semls-app-group` |
| `JWT_AUDIENCE` | **Yes** | e.g. `semls-app-audience` |
| `RABBITMQ_HOST` | No | Default `localhost` |

### Catalog Service

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | No | Selects seed file (`local` → test data) |
| `DEFAULT_RECOMMENDATION_LIMIT` | No | Default `5` |

### Recommendation Service

| Variable | Required | Description |
|---|---|---|
| `DEBUG` | No | `true` skips RabbitMQ consumer |
| `DEVICE_ID` | No | Edge device identifier, default `edge-device-01` |
| `CATALOG_SERVICE_URL` | No | Default `http://catalog-service:8000` |
| `RABBITMQ_HOST` | No | Default `localhost` |

---

## Running the Full Stack

```bash
cd cognibrew-gateway-catalog-recommendation
docker compose up --build
```

| Service | URL |
|---|---|
| API Gateway (entry point) | http://localhost:8001 |
| API Gateway Swagger docs | http://localhost:8001/docs |
| Catalog Service (direct) | http://localhost:8000/docs |
| Recommendation Service (direct) | http://localhost:8002/docs |
| RabbitMQ Management UI | http://localhost:15672 (guest / guest) |

### Local Development (no Docker)

```bash
# Terminal 1 — Catalog Service
cd cognibrew-catalog-service
pip install -r requirements.txt
ENVIRONMENT=local uvicorn app.main:app --reload --port 8000

# Terminal 2 — Recommendation Service
cd cognibrew-recommendation-service
pip install -r requirements.txt
DEBUG=true CATALOG_SERVICE_URL=http://localhost:8000 uvicorn app.main:app --reload --port 8002

# Terminal 3 — API Gateway
cd cognibrew-cloud-api-gateway
pip install -r requirements.txt
ENVIRONMENT=local uvicorn app.main:app --reload --port 8001
```

---

## Testing the Flow End-to-End

```bash
# 1. Confirm services are up
curl http://localhost:8001/api/v1/utils/health-check/   # → true
curl http://localhost:8000/api/v1/menu/                 # → menu items
curl http://localhost:8002/api/v1/recommendation/       # → [] (empty at start)

# 2. Fire a mock face recognition event
docker compose run --rm mock-recognition --username alice --score 0.95

# 3. Check the recommendation (1 beverage + 1 food)
curl http://localhost:8002/api/v1/recommendation/alice

# 4. Record an order to test personalisation
curl -X POST http://localhost:8000/api/v1/order/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "item_id": "<item_id>", "device_id": "edge-device-01"}'

# 5. Fire again — ordered item should now appear first in its category
docker compose run --rm mock-recognition --username alice --score 0.95
curl http://localhost:8002/api/v1/recommendation/alice

# 6. Submit feedback through the gateway
curl -X POST http://localhost:8001/api/v1/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "device_id": "edge-device-01", "rating": 5, "comment": "Great!"}'

# 7. Test multiple random users
docker compose run --rm mock-recognition --random --count 5 --interval 2
curl http://localhost:8002/api/v1/recommendation/
```

---

## Individual Service READMEs

- [API Gateway README](cognibrew-cloud-api-gateway/README.md)
- [Catalog Service README](cognibrew-catalog-service/README.md)
- [Recommendation Service README](cognibrew-recommendation-service/README.md)
