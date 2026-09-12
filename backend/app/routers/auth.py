from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from .. import schemas, auth
from ..database import collection, find_by_field, next_id, get_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=schemas.StoreOut, status_code=201)
def register_store(store_in: schemas.StoreCreate, db=Depends(get_db)):
    existing = find_by_field("stores", "email", store_in.email)
    if existing:
        raise HTTPException(400, "Ya existe una tienda registrada con ese correo")

    store = {
        "id": next_id("stores"),
        "name": store_in.name,
        "email": str(store_in.email),
        "hashed_password": auth.hash_password(store_in.password),
        "address": store_in.address,
        "neighborhood": store_in.neighborhood,
        "municipality": store_in.municipality,
        "department": store_in.department,
        "phone": store_in.phone,
        "latitude": store_in.latitude,
        "longitude": store_in.longitude,
        "offers_delivery": store_in.offers_delivery,
    }
    collection("stores").document(str(store["id"])).set(store)
    return store


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    store = find_by_field("stores", "email", form_data.username)
    if not store or not auth.verify_password(form_data.password, store["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )
    token = auth.create_access_token({"sub": str(store["id"]), "role": "store"})
    return schemas.Token(access_token=token, store=store)


@router.post("/courier/register", response_model=schemas.CourierOut, status_code=201)
def register_courier(courier_in: schemas.CourierCreate, db=Depends(get_db)):
    if find_by_field("couriers", "email", str(courier_in.email)):
        raise HTTPException(400, "Ya existe un domiciliario registrado con ese correo")
    courier = {
        "id": next_id("couriers"),
        "name": courier_in.name,
        "email": str(courier_in.email),
        "hashed_password": auth.hash_password(courier_in.password),
        "phone": courier_in.phone,
        "vehicle_type": courier_in.vehicle_type,
        "available": False,
    }
    collection("couriers").document(str(courier["id"])).set(courier)
    return courier


@router.post("/courier/login", response_model=schemas.CourierToken)
def login_courier(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    courier = find_by_field("couriers", "email", form_data.username)
    if not courier or not auth.verify_password(form_data.password, courier["hashed_password"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = auth.create_access_token({"sub": str(courier["id"]), "role": "courier"})
    return {"access_token": token, "courier": courier}
