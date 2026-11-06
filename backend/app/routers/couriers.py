from fastapi import APIRouter, Depends, HTTPException

from .. import auth, schemas
from ..database import collection, find_by_field, list_collection, get_db

router = APIRouter(prefix="/couriers", tags=["Domiciliarios"])


def _ensure_courier_approved(courier: dict) -> None:
    status_val = courier.get("approval_status")
    if not status_val:
        status_val = "aprobado" if courier.get("approved", True) else "pendiente"
    if status_val != "aprobado":
        raise HTTPException(
            status_code=403,
            detail="Tu cuenta de domiciliario aún no ha sido aprobada por el administrador.",
        )


@router.get("/me", response_model=schemas.CourierOut)
def get_my_courier(current_courier: dict = Depends(auth.get_current_courier)):
    return current_courier


@router.patch("/me/availability", response_model=schemas.CourierOut)
def update_availability(
    available: bool,
    current_courier: dict = Depends(auth.get_current_courier),
    db=Depends(get_db),
):
    _ensure_courier_approved(current_courier)
    reference = collection("couriers").document(str(current_courier["id"]))
    reference.update({"available": available})
    return {**current_courier, "available": available}


@router.patch("/me/location")
def update_location(
    latitude: float,
    longitude: float,
    current_courier: dict = Depends(auth.get_current_courier),
    db=Depends(get_db),
):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise HTTPException(400, "Coordenadas no válidas")
    reference = collection("couriers").document(str(current_courier["id"]))
    reference.update({"latitude": latitude, "longitude": longitude})
    return {"latitude": latitude, "longitude": longitude}


@router.get("/me/orders")
def available_orders(current_courier: dict = Depends(auth.get_current_courier), db=Depends(get_db)):
    """Pedidos a domicilio libres para aceptar y pedidos ya aceptados por este domiciliario."""
    _ensure_courier_approved(current_courier)
    result = []
    stores_map = {s["id"]: s for s in list_collection("stores")}
    for order in list_collection("orders"):
        if not order.get("delivery_address"):
            continue
        if order.get("status") in {"entregado", "cancelado"}:
            continue
        is_accepted = bool(order.get("courier_accepted")) or order.get("status") == "en_camino"
        is_mine = is_accepted and order.get("courier_id") == current_courier["id"]
        is_open = not is_accepted and order.get("status") in {"pendiente", "confirmado"}
        if is_open or is_mine:
            store = stores_map.get(order.get("store_id"))
            result.append({
                **order,
                "courier_id": current_courier["id"] if is_mine else None,
                "courier_accepted": is_mine,
                "store_name": store.get("name") if store else "Tienda",
            })
    return sorted(result, key=lambda order: order.get("created_at"), reverse=True)


@router.post("/me/orders/{order_id}/accept")
def accept_order(
    order_id: int,
    current_courier: dict = Depends(auth.get_current_courier),
    db=Depends(get_db),
):
    _ensure_courier_approved(current_courier)
    reference = collection("orders").document(str(order_id))
    snapshot = reference.get()
    if not snapshot.exists:
        raise HTTPException(404, "Pedido no encontrado")
    order = snapshot.to_dict()
    if not order.get("delivery_address"):
        raise HTTPException(400, "Este pedido no requiere domicilio")
    already_accepted = bool(order.get("courier_accepted")) or order.get("status") == "en_camino"
    if already_accepted and order.get("courier_id") not in (None, current_courier["id"]):
        raise HTTPException(409, "Este pedido ya fue aceptado por otro domiciliario")

    updates = {
        "courier_id": current_courier["id"],
        "courier_accepted": True,
        "courier_name": current_courier.get("name"),
        "courier_phone": current_courier.get("phone"),
        "courier_vehicle": current_courier.get("vehicle_type", "moto"),
        "status": "en_camino",
    }
    reference.update(updates)
    return {**order, "id": order_id, **updates}


@router.patch("/me/orders/{order_id}/status")
def update_delivery_status(
    order_id: int,
    status: str,
    current_courier: dict = Depends(auth.get_current_courier),
    db=Depends(get_db),
):
    _ensure_courier_approved(current_courier)
    allowed = {"en_camino", "entregado", "cancelado"}
    if status not in allowed:
        raise HTTPException(400, "Estado de entrega no válido")
    reference = collection("orders").document(str(order_id))
    snapshot = reference.get()
    if not snapshot.exists or snapshot.to_dict().get("courier_id") != current_courier["id"]:
        raise HTTPException(404, "Entrega no encontrada")
    reference.update({"status": status})
    return {"id": order_id, "status": status}
