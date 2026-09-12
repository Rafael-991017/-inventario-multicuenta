from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from .. import schemas, auth
from ..database import collection, document_data, find_by_field, list_collection, next_id, get_db

router = APIRouter(prefix="/stores", tags=["Tiendas"])


@router.get("", response_model=List[schemas.StoreOut])
def list_stores(db=Depends(get_db)):
    """Lista pública de tiendas, para que la app del cliente pueda mostrarlas
    en un mapa o listado."""
    return list(list_collection("stores"))


@router.get("/me", response_model=schemas.StoreOut)
def get_my_store(current_store: dict = Depends(auth.get_current_store)):
    return current_store


@router.put("/me", response_model=schemas.StoreOut)
def update_my_store(
    store_in: schemas.StoreUpdate,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    reference = collection("stores").document(str(current_store["id"]))
    data = store_in.model_dump()
    reference.update(data)
    return {**current_store, **data}


@router.get("/{store_id}", response_model=schemas.StoreOut)
def get_store(store_id: int, db=Depends(get_db)):
    store = find_by_field("stores", "id", store_id)
    if not store:
        raise HTTPException(404, "Tienda no encontrada")
    return store


# ---------- Inventario de la tienda autenticada ----------

@router.get("/me/inventory", response_model=List[schemas.InventoryOut])
def get_my_inventory(
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    products = {product["id"]: product for product in list_collection("products")}
    return [
        {**item, "product": products[item["product_id"]]}
        for item in list_collection("inventory")
        if item.get("store_id") == current_store["id"] and item.get("product_id") in products
    ]


@router.get("/me/summary")
def get_store_summary(current_store: dict = Depends(auth.get_current_store), db=Depends(get_db)):
    orders = [order for order in list_collection("orders") if order.get("store_id") == current_store["id"]]
    delivered = [order for order in orders if order.get("status") == "entregado"]
    pending = [order for order in orders if order.get("status") in {"pendiente", "confirmado", "en_camino"}]
    return {
        "sales_count": len(delivered),
        "sales_total": sum(float(order.get("total", 0)) for order in delivered),
        "pending_orders": len(pending),
    }


@router.put("/me/inventory", response_model=schemas.InventoryOut)
def upsert_inventory_item(
    item_in: schemas.InventoryUpsert,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    """Crea o actualiza el stock/precio de un producto para la tienda
    autenticada. Cada tienda solo puede tocar su propio inventario."""
    product = document_data(collection("products").document(str(item_in.product_id)).get())
    if not product:
        raise HTTPException(404, "Producto no encontrado")

    item = find_by_field("inventory", "key", f"{current_store['id']}:{item_in.product_id}")
    if item:
        item.update({"stock": item_in.stock, "price": item_in.price, "unit": item_in.unit})
    else:
        item = {"id": next_id("inventory"), "key": f"{current_store['id']}:{item_in.product_id}",
                "store_id": current_store["id"], "product_id": item_in.product_id,
                "stock": item_in.stock, "price": item_in.price, "unit": item_in.unit}
    collection("inventory").document(str(item["id"])).set(item)
    return {**item, "product": product}


@router.post("/me/sales", response_model=schemas.OrderOut, status_code=201)
def create_store_sale(
    sale_in: schemas.SaleCreate,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    """Registra una venta presencial y descuenta el stock de la tienda."""
    item = (
        find_by_field("inventory", "key", f"{current_store['id']}:{sale_in.product_id}")
    )
    if not item:
        raise HTTPException(404, "Ese producto no está en tu inventario")
    if sale_in.quantity <= 0:
        raise HTTPException(400, "La cantidad debe ser mayor que cero")
    if sale_in.unit != item.get("unit", "unidad"):
        raise HTTPException(400, "La unidad de venta no coincide con el inventario")
    if item["stock"] < sale_in.quantity:
        raise HTTPException(400, "Stock insuficiente para esta venta")

    item["stock"] -= sale_in.quantity
    collection("inventory").document(str(item["id"])).set(item)
    order = {"id": next_id("orders"), "store_id": current_store["id"],
             "customer_name": "Venta presencial", "customer_phone": "N/A",
             "delivery_address": None, "status": "entregado",
             "total": item["price"] * sale_in.quantity, "items": [{
                 "product_id": sale_in.product_id, "quantity": sale_in.quantity,
                 "unit_price": item["price"]}], "created_at": datetime.utcnow()}
    collection("orders").document(str(order["id"])).set(order)
    return order


@router.delete("/me/inventory/{product_id}", status_code=204)
def remove_inventory_item(
    product_id: int,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    item = (
        find_by_field("inventory", "key", f"{current_store['id']}:{product_id}")
    )
    if not item:
        raise HTTPException(404, "Ese producto no está en tu inventario")
    collection("inventory").document(str(item["id"])).delete()
