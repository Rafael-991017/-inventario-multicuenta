from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from .. import schemas, auth
from ..database import collection, document_data, list_collection, next_id, get_db

router = APIRouter(prefix="/products", tags=["Productos"])


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
def product_availability(product_id: int, db=Depends(get_db)):
    """El endpoint clave para la app del cliente: en qué tiendas hay este
    producto disponible, con precio y stock de cada una."""
    stores = {store["id"]: store for store in list_collection("stores")}
    return [
        {
            "store_id": store["id"], "store_name": store["name"],
            "address": ", ".join(filter(None, [store.get("address"), store.get("neighborhood"), store.get("municipality"), store.get("department")])), "latitude": store.get("latitude"),
            "longitude": store.get("longitude"),
            "offers_delivery": store.get("offers_delivery", True),
            "price": item["price"], "stock": item["stock"], "unit": item.get("unit", "unidad"),
        }
        for item in list_collection("inventory")
        if item.get("product_id") == product_id
        and item.get("stock", 0) > 0
        and (store := stores.get(item.get("store_id")))
    ]
