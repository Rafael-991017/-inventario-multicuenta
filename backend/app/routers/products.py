from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("", response_model=List[schemas.ProductOut])
def list_products(q: Optional[str] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if q:
        query = query.filter(models.Product.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Product.category == category)
    return query.all()


@router.post("", response_model=schemas.ProductOut, status_code=201)
def create_product(product_in: schemas.ProductCreate, db: Session = Depends(get_db)):
    """Cualquier tienda puede dar de alta un producto nuevo en el catálogo
    global; luego cada tienda decide si lo tiene en su inventario o no."""
    product = models.Product(**product_in.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    return product


@router.patch("/{product_id}/image", response_model=schemas.ProductOut)
def update_product_image(
    product_id: int,
    image_in: schemas.ProductImageUpdate,
    current_store: models.Store = Depends(auth.get_current_store),
    db: Session = Depends(get_db),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    product.image_url = image_in.image_url
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}/availability", response_model=List[schemas.AvailabilityOut])
def product_availability(product_id: int, db: Session = Depends(get_db)):
    """El endpoint clave para la app del cliente: en qué tiendas hay este
    producto disponible, con precio y stock de cada una."""
    rows = (
        db.query(models.Inventory)
        .join(models.Store)
        .filter(models.Inventory.product_id == product_id, models.Inventory.stock > 0)
        .all()
    )
    return [
        schemas.AvailabilityOut(
            store_id=row.store.id,
            store_name=row.store.name,
            address=row.store.address,
            latitude=row.store.latitude,
            longitude=row.store.longitude,
            offers_delivery=row.store.offers_delivery,
            price=row.price,
            stock=row.stock,
        )
        for row in rows
    ]
