from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=schemas.StoreOut, status_code=201)
def register_store(store_in: schemas.StoreCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Store).filter(models.Store.email == store_in.email).first()
    if existing:
        raise HTTPException(400, "Ya existe una tienda registrada con ese correo")

    store = models.Store(
        name=store_in.name,
        email=store_in.email,
        hashed_password=auth.hash_password(store_in.password),
        address=store_in.address,
        phone=store_in.phone,
        latitude=store_in.latitude,
        longitude=store_in.longitude,
        offers_delivery=store_in.offers_delivery,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    store = db.query(models.Store).filter(models.Store.email == form_data.username).first()
    if not store or not auth.verify_password(form_data.password, store.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )
    token = auth.create_access_token({"sub": str(store.id)})
    return schemas.Token(access_token=token, store=store)
