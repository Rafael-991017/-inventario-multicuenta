from datetime import datetime, timedelta, timezone
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
        {
            "cost_price": 0.0,
            "supplier": None,
            **item,
            "product": products[item["product_id"]],
        }
        for item in list_collection("inventory")
        if item.get("store_id") == current_store["id"] and item.get("product_id") in products
    ]


def _normalize_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            pass
    return datetime.min


@router.get("/me/summary")
def get_store_summary(
    period: Optional[str] = None,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    now = datetime.utcnow()
    cutoff = None
    if period == "day":
        cutoff = now - timedelta(days=1)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)

    products = {p["id"]: p.get("name", f"Producto #{p['id']}") for p in list_collection("products")}
    inv_costs = {
        item["product_id"]: float(item.get("cost_price", 0) or 0)
        for item in list_collection("inventory")
        if item.get("store_id") == current_store["id"]
    }

    orders = [order for order in list_collection("orders") if order.get("store_id") == current_store["id"]]
    delivered = [order for order in orders if order.get("status") == "entregado"]
    if cutoff:
        delivered = [o for o in delivered if _normalize_dt(o.get("created_at")) >= cutoff]
    pending = [order for order in orders if order.get("status") in {"pendiente", "confirmado", "en_camino"}]

    sales_total = 0.0
    cost_total = 0.0
    history = []

    for order in sorted(delivered, key=lambda o: _normalize_dt(o.get("created_at")), reverse=True):
        order_rev = float(order.get("total", 0) or 0)
        order_cost = 0.0
        item_labels = []
        for it in order.get("items", []):
            pid = it.get("product_id")
            qty = float(it.get("quantity", 0) or 0)
            unit = it.get("unit", "unidad")
            c_price = it.get("cost_price")
            if c_price is None or float(c_price) == 0:
                c_price = inv_costs.get(pid, 0.0)
            order_cost += float(c_price or 0) * qty
            pname = products.get(pid, f"Prod #{pid}")
            item_labels.append(f"{round(qty, 3):g} {unit} {pname}")
        order_cost = round(order_cost)
        order_profit = round(order_rev - order_cost)
        sales_total += order_rev
        cost_total += order_cost
        history.append({
            "id": order.get("id"),
            "customer_name": order.get("customer_name", "Cliente"),
            "created_at": order.get("created_at"),
            "items_summary": ", ".join(item_labels) if item_labels else "Venta",
            "total": round(order_rev),
            "cost": order_cost,
            "profit": order_profit,
        })

    return {
        "sales_count": len(delivered),
        "sales_total": round(sales_total),
        "cost_total": round(cost_total),
        "profit_total": round(sales_total - cost_total),
        "pending_orders": len(pending),
        "history": history,
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
    supplier_clean = item_in.supplier.strip() if item_in.supplier else None
    if item:
        item.update({
            "stock": item_in.stock,
            "price": item_in.price,
            "cost_price": item_in.cost_price,
            "supplier": supplier_clean,
            "unit": item_in.unit,
        })
    else:
        item = {
            "id": next_id("inventory"),
            "key": f"{current_store['id']}:{item_in.product_id}",
            "store_id": current_store["id"],
            "product_id": item_in.product_id,
            "stock": item_in.stock,
            "price": item_in.price,
            "cost_price": item_in.cost_price,
            "supplier": supplier_clean,
            "unit": item_in.unit,
        }
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

    item["stock"] = round(item["stock"] - sale_in.quantity, 4)
    collection("inventory").document(str(item["id"])).set(item)
    order = {"id": next_id("orders"), "store_id": current_store["id"],
             "customer_name": "Venta presencial", "customer_phone": "N/A",
             "delivery_address": None, "status": "entregado",
             "total": round(item["price"] * sale_in.quantity), "items": [{
                 "product_id": sale_in.product_id, "quantity": sale_in.quantity,
                 "unit_price": item["price"], "cost_price": float(item.get("cost_price", 0) or 0),
                 "unit": item.get("unit", "unidad")}], "created_at": datetime.utcnow()}
    collection("orders").document(str(order["id"])).set(order)
    return order


# ---------- Proveedores de la tienda autenticada ----------

@router.get("/me/suppliers", response_model=List[schemas.SupplierOut])
def get_my_suppliers(
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    return [
        s for s in list_collection("suppliers")
        if s.get("store_id") == current_store["id"]
    ]


@router.post("/me/suppliers", response_model=schemas.SupplierOut, status_code=201)
def create_supplier(
    supplier_in: schemas.SupplierCreate,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    name = supplier_in.name.strip()
    if not name:
        raise HTTPException(400, "El nombre del proveedor es obligatorio")
    supplier = {
        "id": next_id("suppliers"),
        "store_id": current_store["id"],
        "name": name,
        "contact_name": supplier_in.contact_name.strip() if supplier_in.contact_name else None,
        "phone": supplier_in.phone.strip() if supplier_in.phone else None,
        "email": supplier_in.email.strip() if supplier_in.email else None,
        "notes": supplier_in.notes.strip() if supplier_in.notes else None,
    }
    collection("suppliers").document(str(supplier["id"])).set(supplier)
    return supplier


@router.delete("/me/suppliers/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: int,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    ref = collection("suppliers").document(str(supplier_id))
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("store_id") != current_store["id"]:
        raise HTTPException(404, "Proveedor no encontrado")
    ref.delete()


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
