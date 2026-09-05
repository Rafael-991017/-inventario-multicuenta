import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean, Text, BigInteger, Numeric, func
)
from sqlalchemy.orm import relationship

from .database import Base


class OrderStatus(str, enum.Enum):
    pendiente = "pendiente"
    confirmado = "confirmado"
    en_camino = "en_camino"
    entregado = "entregado"
    cancelado = "cancelado"


class Store(Base):
    """Una tienda. Cada tienda tiene su propio inventario independiente."""
    __tablename__ = "stores"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    offers_delivery = Column(Boolean, server_default='true')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inventory_items = relationship(
        "Inventory", back_populates="store", cascade="all, delete-orphan"
    )
    orders = relationship("Order", back_populates="store")


class Product(Base):
    """Catálogo global de productos. El precio y el stock viven en Inventory,
    porque cada tienda maneja su propio stock y puede tener su propio precio."""
    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inventory_items = relationship(
        "Inventory", back_populates="product", cascade="all, delete-orphan"
    )


class Inventory(Base):
    """Relación tienda-producto: cuánto stock tiene ESA tienda de ESE
    producto y a qué precio lo vende. Esto es lo que permite que cada
    tienda sea independiente."""
    __tablename__ = "inventory"

    id = Column(BigInteger, primary_key=True, index=True)
    store_id = Column(BigInteger, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stock = Column(Integer, server_default='0')
    price = Column(Numeric(10, 2), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    store = relationship("Store", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory_items")


class Order(Base):
    """Un pedido hecho por un cliente, ya sea para recoger en tienda o
    a domicilio."""
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, index=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    delivery_address = Column(Text, nullable=True)  # null = recoge en tienda
    status = Column(String(50), server_default='pendiente')
    total = Column(Numeric(10, 2), server_default='0')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    store = relationship("Store", back_populates="orders")
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(BigInteger, primary_key=True, index=True)
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
