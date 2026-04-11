from pydantic import BaseModel, Field


# ── Catalog ───────────────────────────────────────────────────────────────────

class MenuItem(BaseModel):
    item_id: str = Field(..., description="Unique menu item identifier")
    name: str = Field(..., description="Name of the menu item")
    description: str = Field("", description="Short description")
    price: float = Field(..., description="Price in local currency")
    category: str = Field("", description="e.g. Hot, Cold, Food")
    tags: list[str] = Field(default_factory=list, description="Flavour/diet tags")
    available: bool = Field(True, description="Whether the item is currently available")
    order_count: int = Field(0, description="Total number of times ordered")


class MenuListResponse(BaseModel):
    items: list[MenuItem]
    total: int


class MenuItemCreate(BaseModel):
    name: str = Field(..., description="Display name")
    description: str = Field("", description="Short description")
    price: float = Field(..., ge=0, description="Price in THB")
    category: str = Field(..., description="Category e.g. Hot, Cold, Food")
    tags: list[str] = Field(default_factory=list)
    available: bool = Field(True)


class MenuItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(None, ge=0)
    category: str | None = None
    tags: list[str] | None = None
    available: bool | None = None


class MenuItemDeleteResponse(BaseModel):
    status: str = "deleted"
    item_id: str


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderRecord(BaseModel):
    username: str = Field(..., description="Customer username from face recognition")
    item_id: str = Field(..., description="Menu item that was ordered")
    device_id: str = Field("unknown", description="Edge device where the order happened")


class OrderResponse(BaseModel):
    status: str = "ok"
    username: str
    item_id: str


# ── Feedback ──────────────────────────────────────────────────────────────────
# Feedback Service uses a simple PUT with { "IsCorrect": bool }
# No gateway-level schema needed — request/response are proxied as-is.


# ── Notification ──────────────────────────────────────────────────────────────

class NotificationEvent(BaseModel):
    event: str = Field(..., description="Event type e.g. face_recognized, face_unknown")
    username: str = Field("", description="Recognised username (empty if unknown)")
    device_id: str = Field(..., description="Source edge device")
    score: float = Field(0.0, description="Recognition confidence score")
    message: str = Field("", description="Human-readable message for barista")


# ── Health ────────────────────────────────────────────────────────────────────

class ServiceHealth(BaseModel):
    service: str
    status: str  # "ok" | "unreachable"


class GatewayHealthResponse(BaseModel):
    gateway: str = "ok"
    services: list[ServiceHealth]
