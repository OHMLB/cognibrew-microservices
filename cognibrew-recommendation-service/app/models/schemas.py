from pydantic import BaseModel, Field


class MenuItem(BaseModel):
    item_id: str
    name: str
    description: str = ""
    price: float
    category: str
    tags: list[str] = []
    available: bool = True
    order_count: int = 0


class RecommendationResponse(BaseModel):
    username: str = Field(..., description="Recognised customer")
    score: float = Field(..., description="Face recognition confidence score")
    items: list[MenuItem] = Field(..., description="Personalised menu recommendations")
    fetched_at: str = Field(..., description="UTC timestamp when recommendations were fetched")


class NoRecommendationResponse(BaseModel):
    username: str
    message: str = "No recommendation available yet — waiting for a recognised face"
