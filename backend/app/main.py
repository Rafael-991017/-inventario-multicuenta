from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import models
from .database import engine
from .routers import auth as auth_router
from .routers import stores as stores_router
from .routers import products as products_router
from .routers import orders as orders_router

# Crea las tablas si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API Inventario Multi-Tienda",
    description=(
        "API para gestionar ventas e inventario de tiendas, "
        "pedidos a domicilio, y consulta de disponibilidad de productos "
        "entre tiendas."
    ),
    version="1.0.0",
)

# Permite que el panel de tienda (PC) y la app de cliente (Android) hablen con la API.
# En producción, reemplaza "*" por los dominios/orígenes exactos que usarás.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(stores_router.router)
app.include_router(products_router.router)
app.include_router(orders_router.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno: {exc}"},
    )


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API de inventario funcionando. Ve a /docs para probarla."}
