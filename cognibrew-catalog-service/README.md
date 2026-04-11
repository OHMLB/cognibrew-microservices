# CogniBrew Catalog Service

In-memory menu catalog for the CogniBrew platform. Provides full CRUD for menu items, a personalised recommendation engine, and an order-recording endpoint that feeds the recommendation history.

## Architecture

```
API Gateway
     │
     ▼
Catalog Service  (:8000)
  ├── GET/POST/PATCH/DELETE  /api/v1/menu/         — Menu item CRUD
  ├── GET  /api/v1/recommendation/{username}       — Personalised recommendations
  └── POST /api/v1/order/                          — Record customer orders
```

Menu data is kept **entirely in memory** and seeded at startup from a JSON file. There is no external database dependency, which makes the service lightweight and easy to run locally.

## API Endpoints

All routes are prefixed with `/api/v1`.

### Menu  (`/api/v1/menu`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/menu/` | List all menu items. Optional query params: `category`, `available_only` (default `true`) |
| `GET` | `/menu/{item_id}` | Get a single menu item by ID |
| `POST` | `/menu/` | Create a new menu item |
| `PATCH` | `/menu/{item_id}` | Partially update a menu item (only provided fields are changed) |
| `DELETE` | `/menu/{item_id}` | Remove a menu item (returns `204 No Content`) |

**List menu example:**
```bash
curl "http://localhost:8000/api/v1/menu/?category=Hot&available_only=true"
```

**Create menu item example:**
```bash
curl -X POST http://localhost:8000/api/v1/menu/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Caffe Latte",
    "description": "Espresso with steamed milk",
    "price": 120.0,
    "category": "Hot",
    "tags": ["sweet", "dairy"],
    "available": true
  }'
```

### MenuItem Schema

| Field | Type | Description |
|---|---|---|
| `item_id` | `string` | Auto-generated unique identifier (e.g. `caffe-latte-hot`) |
| `name` | `string` | Display name |
| `description` | `string` | Short description |
| `price` | `float` | Price in THB |
| `category` | `string` | `Hot` / `Cold` / `Blended` / `Food` / etc. |
| `tags` | `list[string]` | Flavour / diet tags (e.g. `sweet`, `dairy-free`) |
| `available` | `bool` | Whether the item is currently available (default `true`) |
| `order_count` | `int` | Total times ordered — used for popularity ranking |

### Recommendation  (`/api/v1/recommendation`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/recommendation/{username}` | Return up to `limit` personalised menu items for a recognised customer |

Query params: `limit` (default `5`, range `1–20`).

**Recommendation strategy (in priority order):**
1. Items the customer has previously ordered, ranked by frequency.
2. Globally popular items the customer has not yet tried, ranked by `order_count`.
3. Any available item, sorted by `order_count`.

All returned items are guaranteed to be currently available.

```bash
curl "http://localhost:8000/api/v1/recommendation/alice?limit=5"
```

### Order  (`/api/v1/order`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/order/` | Record that a customer ordered a menu item |
| `GET` | `/order/history/{username}` | Return the customer's ordered `item_id` list (oldest first) |

Each recorded order increments the item's `order_count` and appends to the customer's personalised history, which directly feeds future recommendations.

**Record order example:**
```bash
curl -X POST http://localhost:8000/api/v1/order/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "item_id": "caffe-latte-hot", "device_id": "edge-device-01"}'
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `local` | `local` uses test seed data; `staging` / `production` use the real seed file |
| `API_PREFIX_STR` | `/api/v1` | URL prefix for all routes |
| `DEFAULT_RECOMMENDATION_LIMIT` | `5` | Default number of recommendations returned |
| `MENU_SEED_FILE` | *(auto)* | Path to JSON seed file — resolved automatically from `ENVIRONMENT` |

### Seed file paths

| Environment | Seed file |
|---|---|
| `local` | `data_test/menu_seed_test.json` |
| `staging` / `production` | `data/menu_seed.json` |

## Deployment

### Docker Compose (full stack)

```bash
docker compose -f docker-compose.test.yml up --build catalog-service
```

The service is exposed at **http://localhost:8000** and has no external dependencies.

### Local development

```bash
pip install -r requirements.txt
ENVIRONMENT=local uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Verification

```bash
# List all available menu items
curl http://localhost:8000/api/v1/menu/

# Get a recommendation for a user
curl http://localhost:8000/api/v1/recommendation/alice
```

## Tech Stack

| Component | Version |
|---|---|
| Python | 3.10 |
| FastAPI | 0.115 |
| Uvicorn | 0.34 |
| pydantic | 2.11 |
