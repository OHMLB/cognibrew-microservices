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

# 2. Get a JWT token (login via User Management Service)
TOKEN=$(curl -s -X POST http://localhost:8003/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret"}' | jq -r '.access_token')

# 3. Fire a mock face recognition event
docker compose run --rm mock-recognition --username alice --score 0.95

# 4. Check the recommendation through the gateway (requires JWT)
curl http://localhost:8001/api/v1/catalog/recommendation/alice \
  -H "Authorization: Bearer $TOKEN"
# → 2 items: 1 beverage + 1 food

# 5. Record an order to test personalisation (requires JWT)
curl -X POST http://localhost:8001/api/v1/order/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"username": "alice", "item_id": "<item_id>", "device_id": "edge-device-01"}'

# 6. Check order history (requires JWT)
curl http://localhost:8001/api/v1/order/history/alice \
  -H "Authorization: Bearer $TOKEN"

# 7. Fire again — ordered item should now appear first in its category
docker compose run --rm mock-recognition --username alice --score 0.95
curl http://localhost:8001/api/v1/catalog/recommendation/alice \
  -H "Authorization: Bearer $TOKEN"

# 8. Submit feedback through the gateway
curl -X POST http://localhost:8001/api/v1/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "device_id": "edge-device-01", "rating": 5, "comment": "Great!"}'

# 9. Test multiple random users
docker compose run --rm mock-recognition --random --count 5 --interval 2
curl http://localhost:8002/api/v1/recommendation/
```

---

## Individual Service READMEs

- [API Gateway README](cognibrew-cloud-api-gateway/README.md)
- [Catalog Service README](cognibrew-catalog-service/README.md)
- [Recommendation Service README](cognibrew-recommendation-service/README.md)

---

## Full Loop Manual Test Guide

This guide walks through the complete customer journey end-to-end using `curl` and `websocat` against the running Docker stack.

> **Prerequisites:** Stack is up (`docker compose up --build`), `websocat` is installed (`brew install websocat`).

---

### Port Reference

| Service | Port | Notes |
|---|---|---|
| API Gateway | `8001` | Single entry point for all requests below |
| User Management | `60080` | Direct — register/login barista |
| Member Service | `5012` | Direct — register customer membership |
| RabbitMQ UI | `15672` | guest / guest |

---

### PHASE 1 — Barista Setup

First of all, please bring all service below to this repo

```bash 
- usermanagement service
- members service
- notification service
- feedback service
```

#### Step 1 — Register a Barista account

Barista accounts live in the User Management Service.

```bash
curl -s -X POST http://localhost:60080/user \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice",
    "surname": "Smith",
    "email": "alice@cognibrew.com",
    "role": "User",
    "pwd": "Alice@1234"
  }'
```

Expected: HTTP 200 (empty body = success). HTTP 400 = already registered.

#### Step 2 — Login and store JWT token

```bash
TOKEN=$(curl -s -X POST http://localhost:60080/token \
  -H "Content-Type: application/json" \
  -d '{"username":"alice@cognibrew.com","password":"Alice@1234"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:60}..."
```

> All subsequent requests that require auth use `-H "Authorization: Bearer $TOKEN"`.

---

### PHASE 2 — Customer Membership Registration

Customer data (name, rank, face image) lives in the **Member Service**, not in User Management.

#### Step 3 — Register customer membership (JSON + Base64 image)

```bash
curl -s -X POST http://localhost:5012/api/Member/upload \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "alice",
    "firstName": "Alice",
    "lastName": "Wonderland",
    "rank": "Gold",
    "points": 120,
    "imageBase64": ""
  }' \
  | python3 -m json.tool
```

Expected: `{ "Message": "Member uploaded successfully.", "MemberId": "...", "Username": "alice" }`

> To register with an actual photo, use the `upload-with-image` endpoint (multipart form):
> ```bash
> curl -s -X POST http://localhost:5012/api/Member/upload-with-image \
>   -H "Authorization: Bearer $TOKEN" \
>   -F "username=alice" \
>   -F "firstName=Alice" \
>   -F "lastName=Wonderland" \
>   -F "rank=Gold" \
>   -F "points=120" \
>   -F "image=@/path/to/photo.jpg" \
>   | python3 -m json.tool
> ```

---

### PHASE 3 — Open WebSocket to Watch Notifications

Open a **new terminal** and keep it open throughout the test.

#### Step 4 — Connect WebSocket (paste the token literally)

```bash
websocat "ws://localhost:8001/api/v1/notification/ws/edge-001?access_token=$TOKEN"
```

Leave this terminal running. Events will appear here automatically.

---

### PHASE 4 — Face Recognition

#### Step 5 — Fire mock face recognition

Open another terminal:

```bash
docker compose --profile mock run --rm mock-recognition \
  --username alice --score 0.95
```

**Within seconds**, the WebSocket terminal (Step 4) receives two events:

```json
{"event":"face_recognized","customer":{"id":"face-alice-mock","name":"alice","usualOrder":"Espresso","upsell":"Butter Croissant",...}}
```

Note the `customer.id` value (e.g. `face-alice-mock`) — you will use it for feedback in Step 10.

---

### PHASE 5 — Browse the Menu

#### Step 6 — Get the full menu

```bash
curl -s "http://localhost:8001/api/v1/catalog/menu" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('items', []):
    print(item['item_id'], item['category'], item['name'])
"
```

---

### PHASE 6 — Recommendation

#### Step 7 — Get personalised recommendation for the customer

```bash
curl -s "http://localhost:8001/api/v1/catalog/recommendation/alice" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

Expected: 2 items — 1 beverage + 1 food. For a new/unknown customer this returns the most popular items.

---

### PHASE 7 — Place an Order

#### Step 8 — Record order (pick an `item_id` from Step 6 or 7)

```bash
ITEM_ID="Espresso"   # replace with real item_id from menu

curl -s -X POST http://localhost:8001/api/v1/order/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"alice\",\"item_id\":\"$ITEM_ID\",\"device_id\":\"edge-001\"}" \
  | python3 -m json.tool
```

Expected: `{ "username": "alice", "item_id": "...", "ordered_at": "..." }`

---

### PHASE 8 — Order History

#### Step 9 — View order history for the customer

```bash
curl -s "http://localhost:8001/api/v1/order/history/alice" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

Expected: list of `item_id` strings ordered from oldest to newest.

#### Step 9b — Verify recommendation updated (fire recognition again)

```bash
docker compose --profile mock run --rm mock-recognition \
  --username alice --score 0.95

curl -s "http://localhost:8001/api/v1/catalog/recommendation/alice" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

The item ordered in Step 8 should now appear first in its category.

---

### PHASE 9 — Submit Feedback

#### Step 10 — Confirm or reject the recognition result

Use the `customer.id` from the WebSocket event (Step 5):

```bash
VECTOR_ID="face-alice-mock"   # replace with customer.id from notification

curl -s -X PUT "http://localhost:8001/api/v1/feedback/$VECTOR_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"feedback":"true"}' \
  | python3 -m json.tool
```

`"feedback":"true"` = recognition was correct, `"false"` = recognition was wrong.

---

### Quick Summary Table

| Step | Action | Endpoint | Auth |
|---|---|---|---|
| 1 | Register barista | `POST http://localhost:60080/user` | No |
| 2 | Login → get TOKEN | `POST http://localhost:60080/token` | No |
| 3 | Register customer membership | `POST http://localhost:5012/api/Member/upload` | JWT |
| 4 | Open WebSocket (notification) | `ws://localhost:8001/api/v1/notification/ws/{device_id}` | JWT (query param) |
| 5 | Fire face recognition | `docker compose run mock-recognition` | — |
| 6 | Browse menu | `GET /api/v1/catalog/menu` | No |
| 7 | Get recommendation | `GET /api/v1/catalog/recommendation/{username}` | JWT |
| 8 | Place order | `POST /api/v1/order/` | JWT |
| 9 | View order history | `GET /api/v1/order/history/{username}` | JWT |
| 9b | Re-run recognition → check updated rec | `docker compose run mock-recognition` | — |
| 10 | Submit feedback | `PUT /api/v1/feedback/{vector_id}` | JWT |
