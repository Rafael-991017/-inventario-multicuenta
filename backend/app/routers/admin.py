from typing import List
from fastapi import APIRouter, Depends, HTTPException

from .. import auth, schemas
from ..database import collection, list_collection, get_db

router = APIRouter(prefix="/admin", tags=["Administración"])


def _normalize_courier(c: dict) -> dict:
    status_val = c.get("approval_status")
    if not status_val:
        status_val = "aprobado" if c.get("approved", True) else "pendiente"
    return {
        "id": c["id"],
        "name": c.get("name", ""),
        "cedula": c.get("cedula") or "Sin registrar",
        "email": c.get("email", ""),
        "phone": c.get("phone", ""),
        "vehicle_type": c.get("vehicle_type", "moto"),
        "available": bool(c.get("available", False)),
        "approval_status": status_val,
        "approved": status_val == "aprobado",
    }


@router.get("/overview")
def get_admin_overview(
    current_admin: dict = Depends(auth.get_current_admin),
    db=Depends(get_db),
):
    stores = [
        {
            "id": s["id"],
            "name": s.get("name", ""),
            "email": s.get("email", ""),
            "address": s.get("address"),
            "neighborhood": s.get("neighborhood"),
            "municipality": s.get("municipality"),
            "department": s.get("department"),
            "phone": s.get("phone"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
            "offers_delivery": s.get("offers_delivery", True),
        }
        for s in list_collection("stores")
    ]
    customers = [
        {
            "id": c["id"],
            "name": c.get("name", ""),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "address": c.get("address"),
        }
        for c in list_collection("customers")
    ]
    couriers = [_normalize_courier(c) for c in list_collection("couriers")]
    return {
        "stores": stores,
        "customers": customers,
        "couriers": couriers,
    }


@router.get("/stores", response_model=List[schemas.StoreOut])
def list_all_stores(
    current_admin: dict = Depends(auth.get_current_admin),
    db=Depends(get_db),
):
    return list_collection("stores")


@router.get("/customers", response_model=List[schemas.CustomerOut])
def list_all_customers(
    current_admin: dict = Depends(auth.get_current_admin),
    db=Depends(get_db),
):
    return list_collection("customers")


@router.get("/couriers", response_model=List[schemas.CourierOut])
def list_all_couriers(
    current_admin: dict = Depends(auth.get_current_admin),
    db=Depends(get_db),
):
    return [_normalize_courier(c) for c in list_collection("couriers")]


@router.patch("/couriers/{courier_id}/approval", response_model=schemas.CourierOut)
def update_courier_approval(
    courier_id: int,
    body: schemas.CourierApprovalUpdate,
    current_admin: dict = Depends(auth.get_current_admin),
    db=Depends(get_db),
):
    allowed = {"aprobado", "rechazado", "pendiente"}
    new_status = (body.status or "").strip().lower()
    if new_status not in allowed:
        raise HTTPException(400, "Estado de aprobación no válido")

    ref = collection("couriers").document(str(courier_id))
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(404, "Domiciliario no encontrado")

    data = snap.to_dict()
    is_approved = new_status == "aprobado"
    updates = {
        "approval_status": new_status,
        "approved": is_approved,
    }
    if not is_approved:
        updates["available"] = False
    ref.update(updates)
    data.update(updates)
    data["id"] = courier_id
    return _normalize_courier(data)
