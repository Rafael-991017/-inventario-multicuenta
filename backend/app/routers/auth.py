from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from .. import schemas, auth
from ..database import collection, find_by_field, list_collection, next_id, get_db

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _find_user_case_insensitive(collection_name: str, identifier: str):
    clean = (identifier or "").strip().lower()
    if not clean:
        return None
    exact = find_by_field(collection_name, "email", clean) or find_by_field(collection_name, "email", (identifier or "").strip())
    if exact:
        return exact
    for doc in list_collection(collection_name):
        doc_email = str(doc.get("email") or "").strip().lower()
        doc_name = str(doc.get("name") or "").strip().lower()
        if doc_email == clean or doc_name == clean:
            return doc
    return None


@router.post("/register", response_model=schemas.StoreOut, status_code=201)
def register_store(store_in: schemas.StoreCreate, db=Depends(get_db)):
    normalized_email = str(store_in.email).strip().lower()
    existing = _find_user_case_insensitive("stores", normalized_email)
    if existing and str(existing.get("email") or "").strip().lower() == normalized_email:
        raise HTTPException(400, "Ya existe una tienda registrada con ese correo")

    store = {
        "id": next_id("stores"),
        "name": store_in.name.strip(),
        "email": normalized_email,
        "hashed_password": auth.hash_password(store_in.password),
        "address": store_in.address,
        "neighborhood": store_in.neighborhood,
        "municipality": store_in.municipality,
        "department": store_in.department,
        "phone": store_in.phone,
        "latitude": store_in.latitude,
        "longitude": store_in.longitude,
        "offers_delivery": store_in.offers_delivery,
        "approval_status": "pendiente",
        "approved": False,
    }
    collection("stores").document(str(store["id"])).set(store)
    return store


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    store = _find_user_case_insensitive("stores", form_data.username)
    if not store or not auth.verify_password(form_data.password, store["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )
    approval_status = store.get("approval_status")
    if not approval_status:
        approval_status = "aprobado" if store.get("approved", True) else "pendiente"

    if approval_status == "pendiente" or store.get("approved") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud de tienda está pendiente de revisión y aprobación por el administrador.",
        )
    if approval_status == "rechazado":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud para crear esta tienda fue rechazada por el administrador.",
        )

    store["approval_status"] = approval_status
    store["approved"] = True
    token = auth.create_access_token({"sub": str(store["id"]), "role": "store"})
    return schemas.Token(access_token=token, store=store)


@router.post("/courier/register", response_model=schemas.CourierOut, status_code=201)
def register_courier(courier_in: schemas.CourierCreate, db=Depends(get_db)):
    cedula_clean = "".join(ch for ch in (courier_in.cedula or "") if ch.isdigit())
    if not (6 <= len(cedula_clean) <= 11):
        raise HTTPException(400, "Ingresa una Cédula de Ciudadanía válida de Colombia (entre 6 y 11 dígitos)")
    email_norm = str(courier_in.email).strip().lower()
    existing_courier = _find_user_case_insensitive("couriers", email_norm)
    if existing_courier and str(existing_courier.get("email") or "").strip().lower() == email_norm:
        raise HTTPException(400, "Ya existe un domiciliario registrado con ese correo")
    if find_by_field("couriers", "cedula", cedula_clean):
        raise HTTPException(400, "Ya existe un domiciliario registrado con esa Cédula de Ciudadanía")
    courier = {
        "id": next_id("couriers"),
        "name": courier_in.name.strip(),
        "cedula": cedula_clean,
        "email": email_norm,
        "hashed_password": auth.hash_password(courier_in.password),
        "phone": courier_in.phone.strip(),
        "vehicle_type": courier_in.vehicle_type,
        "available": False,
        "approval_status": "pendiente",
        "approved": False,
    }
    collection("couriers").document(str(courier["id"])).set(courier)
    return courier


@router.post("/courier/login", response_model=schemas.CourierToken)
def login_courier(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    courier = _find_user_case_insensitive("couriers", form_data.username)
    if not courier or not auth.verify_password(form_data.password, courier["hashed_password"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    approval_status = courier.get("approval_status")
    if not approval_status:
        approval_status = "aprobado" if courier.get("approved", True) else "pendiente"

    if approval_status == "pendiente" or courier.get("approved") is False:
        raise HTTPException(
            status_code=403,
            detail="Tu cuenta está pendiente de revisión y aprobación por el administrador.",
        )
    if approval_status == "rechazado":
        raise HTTPException(
            status_code=403,
            detail="Tu solicitud de cuenta como domiciliario fue rechazada por el administrador.",
        )

    courier["approval_status"] = approval_status
    courier["approved"] = True
    token = auth.create_access_token({"sub": str(courier["id"]), "role": "courier"})
    return {"access_token": token, "courier": courier}


def ensure_default_admin() -> dict:
    existing_admins = list(list_collection("admins"))
    if existing_admins:
        return existing_admins[0]
    admin_id = next_id("admins")
    admin_doc = {
        "id": admin_id,
        "name": "Administrador General",
        "email": auth.ADMIN_EMAIL.strip().lower(),
        "password": auth.ADMIN_PASSWORD,
        "hashed_password": auth.hash_password(auth.ADMIN_PASSWORD),
        "role": "admin",
    }
    collection("admins").document(str(admin_id)).set(admin_doc)
    return admin_doc


@router.post("/admin/login", response_model=schemas.AdminToken)
def login_admin(form_data: OAuth2PasswordRequestForm = Depends()):
    ensure_default_admin()
    email_input = form_data.username.strip().lower()
    password_input = form_data.password

    matched_admin = _find_user_case_insensitive("admins", email_input)
    if matched_admin:
        plain_stored = matched_admin.get("password")
        hashed_stored = matched_admin.get("hashed_password")
        password_ok = False
        if plain_stored is not None and password_input == str(plain_stored):
            password_ok = True
        elif hashed_stored and auth.verify_password(password_input, hashed_stored):
            password_ok = True
        if password_ok:
            admin_email = str(matched_admin.get("email") or email_input).strip().lower()
            admin_name = matched_admin.get("name") or "Administrador General"
            token = auth.create_access_token({"sub": admin_email, "role": "admin"})
            return {
                "access_token": token,
                "admin": {"email": admin_email, "name": admin_name},
            }

    if email_input == auth.ADMIN_EMAIL.lower() and password_input == auth.ADMIN_PASSWORD:
        token = auth.create_access_token({"sub": auth.ADMIN_EMAIL.lower(), "role": "admin"})
        return {
            "access_token": token,
            "admin": {"email": auth.ADMIN_EMAIL.lower(), "name": "Administrador General"},
        }

    raise HTTPException(status_code=401, detail="Credenciales de administrador incorrectas")


@router.post("/customer/register", response_model=schemas.CustomerOut, status_code=201)
def register_customer(customer_in: schemas.CustomerCreate, db=Depends(get_db)):
    normalized_email = str(customer_in.email).strip().lower()
    if find_by_field("customers", "email", normalized_email):
        raise HTTPException(400, "Ya existe un cliente registrado con ese correo")
    customer = {
        "id": next_id("customers"),
        "name": customer_in.name.strip(),
        "email": normalized_email,
        "hashed_password": auth.hash_password(customer_in.password),
        "phone": customer_in.phone.strip(),
        "department": customer_in.department.strip() if customer_in.department else None,
        "municipality": customer_in.municipality.strip() if customer_in.municipality else None,
        "neighborhood": customer_in.neighborhood.strip() if customer_in.neighborhood else None,
        "address": customer_in.address.strip() if customer_in.address else None,
    }
    collection("customers").document(str(customer["id"])).set(customer)
    return customer


@router.post("/customer/login", response_model=schemas.CustomerToken)
def login_customer(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    customer = _find_user_case_insensitive("customers", form_data.username)
    if not customer or not auth.verify_password(form_data.password, customer["hashed_password"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = auth.create_access_token({"sub": str(customer["id"]), "role": "customer"})
    return {"access_token": token, "customer": customer}


@router.get("/customer/me", response_model=schemas.CustomerOut)
def get_my_customer(current_customer: dict = Depends(auth.get_current_customer)):
    return current_customer


def _digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


@router.post("/reset-password")
def reset_store_password(body: schemas.PasswordResetRequest, db=Depends(get_db)):
    store = _find_user_case_insensitive("stores", str(body.email))
    if not store:
        raise HTTPException(404, "No se encontró ninguna tienda con ese correo o nombre")
    input_digits = _digits_only(body.verification)
    store_digits = _digits_only(store.get("phone") or "")
    if not input_digits or input_digits != store_digits:
        raise HTTPException(400, "El teléfono ingresado no coincide con el registrado en la tienda")
    if len(body.new_password or "") < 4:
        raise HTTPException(400, "La nueva contraseña debe tener al menos 4 caracteres")
    new_hash = auth.hash_password(body.new_password)
    collection("stores").document(str(store["id"])).update({"hashed_password": new_hash})
    return {"message": "Contraseña de la tienda restablecida correctamente"}


@router.post("/customer/reset-password")
def reset_customer_password(body: schemas.PasswordResetRequest, db=Depends(get_db)):
    customer = _find_user_case_insensitive("customers", str(body.email))
    if not customer:
        raise HTTPException(404, "No se encontró ningún cliente con ese correo")
    input_digits = _digits_only(body.verification)
    customer_digits = _digits_only(customer.get("phone") or "")
    if not input_digits or input_digits != customer_digits:
        raise HTTPException(400, "El teléfono ingresado no coincide con el registrado en tu cuenta")
    if len(body.new_password or "") < 4:
        raise HTTPException(400, "La nueva contraseña debe tener al menos 4 caracteres")
    new_hash = auth.hash_password(body.new_password)
    collection("customers").document(str(customer["id"])).update({"hashed_password": new_hash})
    return {"message": "Contraseña restablecida correctamente"}


@router.post("/courier/reset-password")
def reset_courier_password(body: schemas.PasswordResetRequest, db=Depends(get_db)):
    courier = _find_user_case_insensitive("couriers", str(body.email))
    if not courier:
        raise HTTPException(404, "No se encontró ningún domiciliario con ese correo")
    input_digits = _digits_only(body.verification)
    cedula_digits = _digits_only(courier.get("cedula") or "")
    phone_digits = _digits_only(courier.get("phone") or "")
    if not input_digits or input_digits not in {cedula_digits, phone_digits}:
        raise HTTPException(400, "La Cédula de Ciudadanía o teléfono no coincide con el registrado")
    if len(body.new_password or "") < 4:
        raise HTTPException(400, "La nueva contraseña debe tener al menos 4 caracteres")
    new_hash = auth.hash_password(body.new_password)
    collection("couriers").document(str(courier["id"])).update({"hashed_password": new_hash})
    return {"message": "Contraseña de domiciliario restablecida correctamente"}

