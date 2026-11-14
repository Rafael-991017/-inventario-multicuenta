from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routers import auth as auth_router
from .routers import stores as stores_router
from .routers import products as products_router
from .routers import orders as orders_router
from .routers import couriers as couriers_router
from .routers import admin as admin_router

app = FastAPI(
    title="API Inventario Multi-Tienda",
    description=(
        "API para gestionar ventas e inventario de tiendas, "
        "pedidos a domicilio, y consulta de disponibilidad de productos "
        "entre tiendas."
    ),
    version="1.1.3",
)


@app.on_event("startup")
def seed_default_admin():
    try:
        auth_router.ensure_default_admin()
    except Exception:
        pass

# Permite que cualquier navegador (PC, celular, GitHub Pages, Render, Android) se conecte a la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_html_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/app") or path.startswith("/panel-tienda") or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(auth_router.router)
app.include_router(stores_router.router)
app.include_router(products_router.router)
app.include_router(orders_router.router)
app.include_router(couriers_router.router)
app.include_router(admin_router.router)

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_CLIENTE_DIR = REPO_ROOT / "app-cliente"
PANEL_TIENDA_DIR = REPO_ROOT / "panel-tienda"


@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API de inventario funcionando. Entra a /app/perfiles.html para abrir Venta Fast."}


@app.get("/app")
def redirect_to_app():
    return RedirectResponse(url="/app/perfiles.html")


if APP_CLIENTE_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(APP_CLIENTE_DIR), html=True), name="app-cliente")
    app.mount("/app-cliente", StaticFiles(directory=str(APP_CLIENTE_DIR), html=True), name="app-cliente-compat")

if PANEL_TIENDA_DIR.exists():
    app.mount("/panel-tienda", StaticFiles(directory=str(PANEL_TIENDA_DIR), html=True), name="panel-tienda")
