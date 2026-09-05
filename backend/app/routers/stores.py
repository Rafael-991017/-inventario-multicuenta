from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/stores", tags=["Tiendas"])


@router.get("", response_model=List[schemas.StoreOut])
def list_stores(db: Session = Depends(get_db)):
    """Lista pública de tiendas, para que la app del cliente pueda mostrarlas
    en un mapa o listado."""
    return db.query(models.Store).all()


@router.get("/me", response_model=schemas.StoreOut)
def get_my_store(current_store: models.Store = Depends(auth.get_current_store)):
    return current_store


@router.get("/{store_id}", response_model=schemas.StoreOut)
def get_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(404, "Tienda no encontrada")
    return store


# ---------- Inventario de la tienda autenticada ----------

@router.get("/me/inventory", response_model=List[schemas.InventoryOut])
def get_my_inventory(
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Inventory)
        .filter(models.Inventory.store_id == current_store.id)
        .all()
    )


@router.put("/me/inventory", response_model=schemas.InventoryOut)
def upsert_inventory_item(
    item_in: schemas.InventoryUpsert,
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    """Crea o actualiza el stock/precio de un producto para la tienda
    autenticada. Cada tienda solo puede tocar su propio inventario."""
    product = db.query(models.Product).filter(models.Product.id == item_in.product_id).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")

    item = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.store_id == current_store.id,
            models.Inventory.product_id == item_in.product_id,
        )
        .first()
    )
    if item:
        item.stock = item_in.stock
        item.price = item_in.price
    else:
        item = models.Inventory(
            store_id=current_store.id,
            product_id=item_in.product_id,
            stock=item_in.stock,
            price=item_in.price,
        )
        db.add(item)

    db.commit()
    db.refresh(item)
    return item


@router.post("/me/sales", response_model=schemas.OrderOut, status_code=201)
def create_store_sale(
    sale_in: schemas.SaleCreate,
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    """Registra una venta presencial y descuenta el stock de la tienda."""
    item = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.store_id == current_store.id,
            models.Inventory.product_id == sale_in.product_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(404, "Ese producto no está en tu inventario")
    if sale_in.quantity <= 0:
        raise HTTPException(400, "La cantidad debe ser mayor que cero")
    if item.stock < sale_in.quantity:
        raise HTTPException(400, "Stock insuficiente para esta venta")

    item.stock -= sale_in.quantity
    order = models.Order(
        store_id=current_store.id,
        customer_name="Venta presencial",
        customer_phone="N/A",
        status=models.OrderStatus.entregado,
        total=item.price * sale_in.quantity,
        items=[
            models.OrderItem(
                product_id=sale_in.product_id,
                quantity=sale_in.quantity,
                unit_price=item.price,
            )
        ],
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.delete("/me/inventory/{product_id}", status_code=204)
def remove_inventory_item(
    product_id: int,
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    item = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.store_id == current_store.id,
            models.Inventory.product_id == product_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(404, "Ese producto no está en tu inventario")
    db.delete(item)
    db.commit()
