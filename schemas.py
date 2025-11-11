"""
Database Schemas for Vintage Clothier

Each Pydantic model represents a MongoDB collection. The collection name is the lowercase
of the class name (e.g., Product -> "product").
"""
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class Product(BaseModel):
    """
    Premium products we offer (suits, boots, shirts, hats, belts, trousers)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    category: str = Field(..., description="Category: suit, boots, shoes, hat, belt, shirt, trousers")
    base_price: float = Field(..., ge=0, description="Base price in USD")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    colors: List[str] = Field(default_factory=list)
    fabrics: List[str] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list)
    fits: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    in_stock: bool = Field(True)


class Measurement(BaseModel):
    height_cm: Optional[float] = Field(None, ge=100, le=230)
    weight_kg: Optional[float] = Field(None, ge=35, le=200)
    chest_cm: Optional[float] = Field(None, ge=60, le=150)
    waist_cm: Optional[float] = Field(None, ge=50, le=150)
    hips_cm: Optional[float] = Field(None, ge=60, le=160)
    sleeve_cm: Optional[float] = Field(None, ge=40, le=80)
    inseam_cm: Optional[float] = Field(None, ge=60, le=100)


class Customization(BaseModel):
    """A user's configured product"""
    product_id: Optional[str] = Field(None, description="Target product")
    category: str = Field(..., description="Category being customized")
    color: Optional[str] = None
    fabric: Optional[str] = None
    size: Optional[str] = None
    fit: Optional[str] = None
    pattern: Optional[str] = None
    preferences: Optional[str] = Field(None, description="Free text preferences")
    auto: bool = Field(False, description="If true, system will auto-complete best choices")
    measurements: Optional[Measurement] = None


class Order(BaseModel):
    user_name: str
    email: str
    customization: Customization
    total_price: float
    status: str = Field("pending")


class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class RecommendationRequest(BaseModel):
    purpose: Optional[str] = Field(None, description="Occasion/purpose e.g. wedding, business, casual")
    style: Optional[str] = Field(None, description="classic, vintage, modern, rugged")
    climate: Optional[str] = Field(None, description="hot, temperate, cold")
    budget: Optional[float] = Field(None, ge=0)
    category: Optional[str] = None
    colors: Optional[List[str]] = None


class Recommendation(BaseModel):
    product_id: Optional[str] = None
    title: str
    category: str
    suggested_config: Dict[str, Optional[str]]
    est_price: float
    rationale: str


class RecommendationResponse(BaseModel):
    recommendations: List[Recommendation]


# Note: The Flames database viewer reads these models via GET /schema.
