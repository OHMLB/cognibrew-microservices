# CogniBrew Cloud API Gateway

Central HTTP and WebSocket gateway for the CogniBrew platform. All requests from the Barista Frontend flow through this service before reaching downstream microservices.

## Architecture

```
Barista Frontend
     │
     ▼
API Gateway  (:8001 host / :8000 container)
  ├── REST proxy → User Management Service  (:5001)
  ├── REST proxy → Catalog Service          (:8000)
  ├── REST proxy → Feedback Service        (:8080)
  └── WebSocket bridge → Notification Service (SignalR hub /chatHub)
           ▲
     RabbitMQ consumer (face.recognized) — production mode only
```

The gateway also runs a background RabbitMQ consumer that listens to the `cognibrew.inference` exchange (`face.recognized` routing key). In **DEBUG mode** (local development) the consumer is replaced by a no-op dummy so RabbitMQ is not required.

## API Endpoints

All routes are prefixed with `/api/v1`.

### Auth  (`/api/v1/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/token` | — | Login — returns JWT access token |
| `POST` | `/auth/user` | — | Register a new barista / admin user |
| `GET` | `/auth/user` | JWT | List all users (Admin) or current user |
| `GET` | `/auth/user/{id}` | JWT | Get a specific user |
| `PATCH` | `/auth/user/{id}` | JWT | Partial update of a user |
| `PUT` | `/auth/user/{id}` | JWT | Full replacement of a user |
| `DELETE` | `/auth/user/{id}` | JWT | Delete a user |

**Login example:**
```bash
curl -X POST http://localhost:8001/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "test@cognibrew.com", "password": "Test1234!"}'
```

Response:
```json
{ "access_token": "<JWT>", "token_type": "Bearer", "expires_in": 7200 }
```

### Catalog  (`/api/v1/catalog`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/catalog/menu` | — | List menu items (filterable by category / availability) |
| `GET` | `/catalog/menu/{item_id}` | — | Get a single menu item |
| `POST` | `/catalog/menu` | JWT | Create a new menu item |
| `PATCH` | `/catalog/menu/{item_id}` | JWT | Partial update of a menu item |
| `DELETE` | `/catalog/menu/{item_id}` | JWT | Delete a menu item |
| `GET` | `/catalog/recommendation/{username}` | — | Personalised recommendations for a recognised customer |

### Feedback  (`/api/v1/feedback`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/feedback/` | — | Submit star-rating feedback (1–5) after serving a customer |
| `PUT` | `/feedback/{device_id}/{date}/{vector_id}` | JWT | Confirm face recognition correctness (`IsCorrect: true/false`) |

### Notification  (`/api/v1/notification`)

| Protocol | Path | Auth | Description |
|----------|------|------|-------------|
| WebSocket | `/notification/ws/{device_id}?access_token=<JWT>` | JWT (query param) | Real-time push events to the Barista Frontend |

The gateway bridges the Notification Service's SignalR hub to a plain WebSocket connection. Messages pushed by the hub (`face_recognized` / `face_unknown` events) are translated to a JSON envelope before forwarding to the frontend.

### Health  (`/api/v1/utils/health`)

```bash
GET /api/v1/utils/health
```

Returns the gateway status and reachability of all downstream services.

## Configuration

Copy `.env.example` to `.env` and adjust the values. All settings can also be passed as environment variables.

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `local` | `local` / `staging` / `production` — controls downstream service URLs |
| `DEBUG` | `true` | `true` = dummy RabbitMQ consumer (no broker needed) |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `API_PREFIX_STR` | `/api/v1` | URL prefix for all routes |
| `HTTP_TIMEOUT` | `30.0` | HTTP client timeout in seconds |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ AMQP port |
| `RABBITMQ_USERNAME` | `guest` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `guest` | RabbitMQ password |
| `JWT_SECRET_KEY` | — | **Required.** Must match User Management Service |
| `JWT_ISSUER` | — | JWT issuer claim (e.g. `semls-app-group`) |
| `JWT_AUDIENCE` | — | JWT audience claim (e.g. `semls-app-audience`) |
| `JWT_ALGORITHMS` | `HS256` | JWT signing algorithm |

### Downstream URL Resolution

In `production` mode service names resolve via Docker internal DNS. In `local` / `DEBUG` mode localhost ports are used:

| Service | Local | Production (Docker) |
|---|---|---|
| Catalog | `http://localhost:8000` | `http://catalog-service:8000` |
| Recommendation | `http://localhost:8002` | `http://recommendation-service:8000` |
| User Management | `http://localhost:8003` | `http://user-management-service:5001` |
| Feedback | `http://localhost:5086` | `http://feedback-service:8080` |
| Notification | `http://localhost:5019` | `http://notification-service:8080` |

## Deployment

### Docker Compose (from repo root)

```bash
cd cognibrew-gateway-catalog-recommendation
docker compose up --build
```

The gateway is exposed at **http://localhost:8001**. All dependent services start automatically.

### Local development

```bash
pip install -r requirements.txt
ENVIRONMENT=local uvicorn app.main:app --reload --port 8001
```

Interactive docs: http://localhost:8001/docs

## Verification

```bash
curl http://localhost:8001/api/v1/utils/health-check/
```

Expected response: `true`

## Tech Stack

| Component | Version |
|---|---|
| Python | 3.10 |
| FastAPI | 0.115 |
| Uvicorn | 0.34 |
| httpx | 0.28 |
| websockets | 14.2 |
| pika (RabbitMQ) | 1.3 |
| protobuf | 6.32 |
| PyJWT | 2.10 |
| pydantic | 2.11 |
