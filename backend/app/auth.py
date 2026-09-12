from datetime import datetime, timedelta
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from .database import find_by_field, get_db

# En producción, mueve esto a una variable de entorno.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cambia-esta-clave-solo-para-desarrollo")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 día

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_store(
    token: str = Depends(oauth2_scheme), db=Depends(get_db)
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        store_id: Optional[str] = payload.get("sub")
        if store_id is None or payload.get("role") != "store":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    store = find_by_field("stores", "id", int(store_id))
    if store is None:
        raise credentials_exception
    return store


def get_current_courier(
    token: str = Depends(oauth2_scheme), db=Depends(get_db)
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la sesión del domiciliario",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        courier_id = payload.get("sub")
        if courier_id is None or payload.get("role") != "courier":
            raise credentials_exception
    except (JWTError, ValueError):
        raise credentials_exception
    courier = find_by_field("couriers", "id", int(courier_id))
    if courier is None:
        raise credentials_exception
    return courier
