from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/orders", tags=["Pedidos"])


@router.post("", status_code=201)
def create_order(order_in: schemas.OrderCreate, db: Session = Depends(get_db)):
    """El cliente crea un pedido (recoger en tienda o a domicilio). Se valida
    y descuenta el stock de ESA tienda específica."""
    store = db.query(models.Store).filter(models.Store.id == order_in.store_id).first()
    if not store:
        raise HTTPException(404, "Tienda no encontrada")
    if order_in.delivery_address and not store.offers_delivery:
        raise HTTPException(400, "Esta tienda no ofrece servicio a domicilio")
    if not order_in.items:
        raise HTTPException(400, "El pedido no tiene productos")

    order = models.Order(
        store_id=store.id,
        customer_name=order_in.customer_name,
        customer_phone=order_in.customer_phone,
        delivery_address=order_in.delivery_address,
    )
    order.id = (db.query(func.max(models.Order.id)).scalar() or 0) + 1
    total = 0.0
    order_items = []

    for item in order_in.items:
        inv = (
            db.query(models.Inventory)
            .filter(
                models.Inventory.store_id == store.id,
                models.Inventory.product_id == item.product_id,
            )
            .first()
        )
        if not inv:
            raise HTTPException(400, f"El producto {item.product_id} no está disponible en esta tienda")
        if inv.stock < item.quantity:
            raise HTTPException(400, f"Stock insuficiente para el producto {item.product_id}")

        inv.stock -= item.quantity
        total += float(inv.price) * item.quantity
        order_item = models.OrderItem(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=inv.price,
        )
        order_item.id = (db.query(func.max(models.OrderItem.id)).scalar() or 0) + len(order_items) + 1
        order_items.append(order_item)

    order.total = total
    order.items = order_items
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"No se pudo guardar el pedido: {exc}") from exc
    return {
        "id": order.id,
        "store_id": order.store_id,
        "status": order.status,
        "total": order.total,
    }


@router.get("/me", response_model=List[schemas.OrderOut])
def list_my_orders(
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    """Pedidos recibidos por la tienda autenticada."""
    return (
        db.query(models.Order)
        .filter(models.Order.store_id == current_store.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.patch("/{order_id}/status", response_model=schemas.OrderOut)
def update_order_status(
    order_id: int,
    status_in: schemas.OrderStatusUpdate,
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.store_id == current_store.id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Pedido no encontrado")
    order.status = status_in.status
    db.commit()
    db.refresh(order)
    return order
