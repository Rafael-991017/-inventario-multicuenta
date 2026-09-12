from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from .. import schemas, auth
from ..database import collection, find_by_field, list_collection, next_id, get_db

router = APIRouter(prefix="/orders", tags=["Pedidos"])


@router.post("", status_code=201)
def create_order(order_in: schemas.OrderCreate, db=Depends(get_db)):
    store = find_by_field("stores", "id", order_in.store_id)
    if not store:
        raise HTTPException(404, "Tienda no encontrada")
    if order_in.delivery_address and not store.get("offers_delivery", True):
        raise HTTPException(400, "Esta tienda no ofrece servicio a domicilio")
    if not order_in.items:
        raise HTTPException(400, "El pedido no tiene productos")
    if order_in.payment_method not in {"contra_entrega"}:
        raise HTTPException(400, "Método de pago no disponible")

    total = 0.0
    order_items = []
    inventory_changes = []
    for item_in in order_in.items:
        item = find_by_field("inventory", "key", f"{order_in.store_id}:{item_in.product_id}")
        if not item:
            raise HTTPException(400, f"El producto {item_in.product_id} no está disponible en esta tienda")
        if item.get("stock", 0) < item_in.quantity:
            raise HTTPException(400, f"Stock insuficiente para el producto {item_in.product_id}")
        item["stock"] -= item_in.quantity
        inventory_changes.append(item)
        total += float(item["price"]) * item_in.quantity
        order_items.append({"product_id": item_in.product_id, "quantity": item_in.quantity,
                    "unit_price": item["price"], "unit": item.get("unit", "unidad")})

    for item in inventory_changes:
        collection("inventory").document(str(item["id"])).set(item)
    assigned_courier = None
    if order_in.delivery_address:
        assigned_courier = next((courier for courier in list_collection("couriers") if courier.get("available")), None)
    order = {"id": next_id("orders"), "store_id": order_in.store_id,
             "customer_name": order_in.customer_name, "customer_phone": order_in.customer_phone,
             "delivery_address": order_in.delivery_address,
             "payment_method": order_in.payment_method,
             "status": "confirmado" if assigned_courier else "pendiente",
             "courier_id": assigned_courier["id"] if assigned_courier else None,
             "total": total, "created_at": datetime.utcnow(), "items": order_items}
    collection("orders").document(str(order["id"])).set(order)
    return {"id": order["id"], "store_id": order["store_id"],
            "status": order["status"], "total": order["total"]}


@router.get("/me", response_model=List[schemas.OrderOut])
def list_my_orders(current_store: dict = Depends(auth.get_current_store), db=Depends(get_db)):
    orders = [order for order in list_collection("orders")
              if order.get("store_id") == current_store["id"]]
    return sorted(orders, key=lambda order: order.get("created_at", datetime.min), reverse=True)


@router.get("/track/{order_id}")
def track_order(order_id: int, phone: str, db=Depends(get_db)):
    """Consulta pública protegida por el teléfono usado al crear el pedido."""
    order = find_by_field("orders", "id", order_id)
    if not order or order.get("customer_phone") != phone:
        raise HTTPException(404, "No encontramos un pedido con esos datos")
    store = find_by_field("stores", "id", order.get("store_id"))
    courier = find_by_field("couriers", "id", order.get("courier_id")) if order.get("courier_id") else None
    return {
        "id": order["id"],
        "status": order.get("status", "pendiente"),
        "customer_name": order.get("customer_name"),
        "delivery_address": order.get("delivery_address"),
        "store_name": store.get("name") if store else None,
        "store_address": store.get("address") if store else None,
        "store_latitude": store.get("latitude") if store else None,
        "store_longitude": store.get("longitude") if store else None,
        "courier_latitude": courier.get("latitude") if courier else None,
        "courier_longitude": courier.get("longitude") if courier else None,
    }


@router.get("/history")
def order_history(phone: str, db=Depends(get_db)):
    """Devuelve el historial básico de pedidos asociados a un teléfono."""
    stores = {store["id"]: store for store in list_collection("stores")}
    orders = []
    for order in list_collection("orders"):
        if order.get("customer_phone") != phone:
            continue
        store = stores.get(order.get("store_id"))
        orders.append({
            "id": order["id"],
            "status": order.get("status", "pendiente"),
            "total": order.get("total", 0),
            "created_at": order.get("created_at"),
            "store_name": store.get("name") if store else "Tienda",
        })
    return sorted(orders, key=lambda order: order.get("created_at") or datetime.min, reverse=True)


@router.patch("/{order_id}/status", response_model=schemas.OrderOut)
def update_order_status(
    order_id: int,
    status_in: schemas.OrderStatusUpdate,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    reference = collection("orders").document(str(order_id))
    order = reference.get()
    if not order.exists:
        raise HTTPException(404, "Pedido no encontrado")
    data = order.to_dict()
    if data.get("store_id") != current_store["id"]:
        raise HTTPException(404, "Pedido no encontrado")
    data["id"] = order_id
    data["status"] = status_in.status.value
    reference.update({"status": data["status"]})
    return data