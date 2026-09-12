from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr

from .models import OrderStatus


# ---------- Store ----------
class StoreCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    address: Optional[str] = None
    neighborhood: Optional[str] = None
    municipality: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    offers_delivery: bool = True


class StoreOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    address: Optional[str]
    neighborhood: Optional[str]
    municipality: Optional[str]
    department: Optional[str]
    phone: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    offers_delivery: bool

    class Config:
        from_attributes = True


class StoreLogin(BaseModel):
    email: EmailStr
    password: str


class StoreUpdate(BaseModel):
    name: str
    address: Optional[str] = None
    neighborhood: Optional[str] = None
    municipality: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    offers_delivery: bool = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    store: StoreOut


class CourierCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    vehicle_type: str = "moto"


class CourierOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: str
    vehicle_type: str
    available: bool = False


class CourierToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    courier: CourierOut


# ---------- Product ----------
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None


class ProductImageUpdate(BaseModel):
    image_url: Optional[str] = None


class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    image_url: Optional[str]

    class Config:
        from_attributes = True


# ---------- Inventory ----------
class InventoryUpsert(BaseModel):
    product_id: int
    stock: float
    price: float
    unit: str = "unidad"


class InventoryOut(BaseModel):
    id: int
    product_id: int
    store_id: int
    stock: float
    price: float
    unit: str = "unidad"
    product: ProductOut

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    product_id: int
    quantity: float
    unit: str = "unidad"


class AvailabilityOut(BaseModel):
    """Para el cliente: en qué tiendas hay este producto, con precio y stock."""
    store_id: int
    store_name: str
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    offers_delivery: bool
    price: float
    stock: float
    unit: str = "unidad"

    class Config:
        from_attributes = True


# ---------- Orders ----------
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: float


class OrderCreate(BaseModel):
    store_id: int
    customer_name: str
    customer_phone: str
    delivery_address: Optional[str] = None  # None = recoge en tienda
    payment_method: str = "contra_entrega"
    items: List[OrderItemCreate]


class OrderItemOut(BaseModel):
    product_id: int
    quantity: float
    unit_price: float
    unit: str = "unidad"

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    store_id: int
    customer_name: str
    customer_phone: str
    delivery_address: Optional[str]
    status: OrderStatus
    total: float
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
