from pydantic import BaseModel, Field

class MenuItem(BaseModel):
    """
    ... means the field is required, default value is not provided.
    and the other fields have default values, so they are optional when creating a new menu item.
    """

    item_id: str = Field(..., description="Unique menu item identifier e.g. 'latte-hot-m'")
    name: str = Field(..., description="Display name e.g. 'Caffe Latte'")
    description: str = Field("", description="Short description of the item")
    price: float = Field(..., ge=0, description="Price in THB")
    category: str = Field(..., description="Category: Hot, Cold, Blended, Food, etc.")
    tags: list[str] = Field(default_factory=list, description="Flavour/diet tags e.g. ['sweet','dairy-free']")
    available: bool = Field(True, description="Whether the item is currently available")
    order_count: int = Field(0, description="Total number of times ordered (used for popularity ranking)")


class MenuItemCreate(BaseModel):
    name: str
    description: str = ""
    price: float = Field(..., ge=0)
    category: str
    tags: list[str] = []
    available: bool = True


class MenuItemUpdate(BaseModel):
    """All fields are optional for updates, but if provided, they will be validated."""
    name: str | None = None
    description: str | None = None
    price: float | None = Field(None, ge=0)
    category: str | None = None
    tags: list[str] | None = None
    available: bool | None = None


class MenuListResponse(BaseModel):
    items: list[MenuItem]
    total: int


class OrderRecord(BaseModel):
    """Records that a customer ordered an item — used to drive recommendations."""
    username: str = Field(..., description="Customer username from face recognition")
    item_id: str = Field(..., description="Menu item that was ordered")
    device_id: str = Field("unknown", description="Edge device where the order happened")


class OrderResponse(BaseModel):
    status: str = "ok"
    username: str
    item_id: str
