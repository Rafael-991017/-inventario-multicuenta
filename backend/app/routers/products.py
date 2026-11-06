import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from .. import schemas, auth
from ..database import collection, document_data, list_collection, next_id, get_db

router = APIRouter(prefix="/products", tags=["Productos"])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


@router.get("/catalog")
def list_catalog_with_availability(
    q: Optional[str] = None,
    category: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 5.0,
    db=Depends(get_db),
):
    """Devuelve todos los productos junto con su disponibilidad en tiendas en una sola petición rápida."""
    products = [
        product for product in list_collection("products")
        if (not q or q.lower() in product.get("name", "").lower())
        and (not category or product.get("category") == category)
    ]
    stores = {store["id"]: store for store in list_collection("stores")}
    avail_by_product = {}

    for item in list_collection("inventory"):
        pid = item.get("product_id")
        if not pid or item.get("stock", 0) <= 0:
            continue
        store = stores.get(item.get("store_id"))
        if not store:
            continue
        s_lat = store.get("latitude")
        s_lng = store.get("longitude")
        if lat is not None and lng is not None and s_lat is not None and s_lng is not None:
            if haversine_km(lat, lng, float(s_lat), float(s_lng)) > radius_km:
                continue
        avail_by_product.setdefault(pid, []).append({
            "store_id": store["id"],
            "store_name": store["name"],
            "address": ", ".join(filter(None, [store.get("address"), store.get("neighborhood"), store.get("municipality"), store.get("department")])),
            "latitude": s_lat,
            "longitude": s_lng,
            "offers_delivery": store.get("offers_delivery", True),
            "price": item["price"],
            "stock": item["stock"],
            "unit": item.get("unit", "unidad"),
        })

    return [
        {
            "product": p,
            "availability": avail_by_product.get(p["id"], []),
        }
        for p in products
    ]


@router.get("", response_model=List[schemas.ProductOut])
def list_products(q: Optional[str] = None, category: Optional[str] = None, db=Depends(get_db)):
    return [
        product for product in list_collection("products")
        if (not q or q.lower() in product.get("name", "").lower())
        and (not category or product.get("category") == category)
    ]


@router.post("", response_model=schemas.ProductOut, status_code=201)
def create_product(product_in: schemas.ProductCreate, db=Depends(get_db)):
    """Cualquier tienda puede dar de alta un producto nuevo en el catálogo
    global; luego cada tienda decide si lo tiene en su inventario o no."""
    product = {"id": next_id("products"), **product_in.model_dump()}
    collection("products").document(str(product["id"])).set(product)
    return product


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db=Depends(get_db)):
    product = document_data(collection("products").document(str(product_id)).get())
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    """Quita el producto de esta tienda y borra el catálogo si ya no se usa."""
    product_reference = collection("products").document(str(product_id))
    if not product_reference.get().exists:
        raise HTTPException(404, "Producto no encontrado")

    inventory_items = [
        item for item in list_collection("inventory")
        if item.get("product_id") == product_id
    ]
    store_item = next(
        (item for item in inventory_items if item.get("store_id") == current_store["id"]),
        None,
    )
    if store_item is None:
        raise HTTPException(404, "Ese producto no está en tu inventario")

    collection("inventory").document(str(store_item["id"])).delete()
    remaining_items = [item for item in inventory_items if item["id"] != store_item["id"]]
    catalog_deleted = not remaining_items
    if catalog_deleted:
        product_reference.delete()

    return {"catalog_deleted": catalog_deleted}


@router.patch("/{product_id}/image", response_model=schemas.ProductOut)
def update_product_image(
    product_id: int,
    image_in: schemas.ProductImageUpdate,
    current_store: dict = Depends(auth.get_current_store),
    db=Depends(get_db),
):
    reference = collection("products").document(str(product_id))
    product = document_data(reference.get())
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    reference.update({"image_url": image_in.image_url})
    product["image_url"] = image_in.image_url
    return product


@router.get("/{product_id}/availability", response_model=List[schemas.AvailabilityOut])
def product_availability(
    product_id: int,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 5.0,
    db=Depends(get_db),
):
    """El endpoint clave para la app del cliente: en qué tiendas hay este
    producto disponible, con precio y stock de cada una."""
    stores = {store["id"]: store for store in list_collection("stores")}
    results = []
    for item in list_collection("inventory"):
        if item.get("product_id") != product_id or item.get("stock", 0) <= 0:
            continue
        store = stores.get(item.get("store_id"))
        if not store:
            continue
        s_lat = store.get("latitude")
        s_lng = store.get("longitude")
        if lat is not None and lng is not None and s_lat is not None and s_lng is not None:
            if haversine_km(lat, lng, float(s_lat), float(s_lng)) > radius_km:
                continue
        results.append({
            "store_id": store["id"],
            "store_name": store["name"],
            "address": ", ".join(filter(None, [store.get("address"), store.get("neighborhood"), store.get("municipality"), store.get("department")])),
            "latitude": s_lat,
            "longitude": s_lng,
            "offers_delivery": store.get("offers_delivery", True),
            "price": item["price"],
            "stock": item["stock"],
            "unit": item.get("unit", "unidad"),
        })
    return results
