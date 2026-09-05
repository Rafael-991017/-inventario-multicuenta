# Inventario Multi-Tienda

Sistema con tres partes:

```
inventario-app/
├── backend/          → API central (FastAPI + base de datos)
├── panel-tienda/      → Panel para que cada tienda gestione su inventario y pedidos (tu "app de PC")
└── app-cliente/        → Vista para que el cliente compare precios y disponibilidad (base de tu app Android)
```

Cada tienda tiene su **propio stock independiente**: el mismo producto puede existir en varias tiendas, cada una con su propio precio y cantidad disponible.

## 1. Correr el backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

La API queda en `http://localhost:8000`. Ve a `http://localhost:8000/docs` para ver y probar todos los endpoints automáticamente (documentación interactiva incluida por FastAPI).

Usa SQLite por defecto (`inventario.db`, se crea solo). Para conectar PostgreSQL, define `DATABASE_URL` antes de iniciar la API:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/inventario"
uvicorn app.main:app --reload
```

El esquema SQL de PostgreSQL debe estar creado previamente. La aplicación usa las tablas `stores`, `products`, `inventory`, `orders` y `order_items`.

## 2. Abrir el panel de tienda

Abre `panel-tienda/index.html` directamente en el navegador (doble clic, o "Abrir con" tu navegador). Ahí puedes:
- Registrar una tienda nueva
- Agregar productos a tu inventario (precio + stock)
- Ver y actualizar el estado de tus pedidos

Si tu backend no está en `localhost:8000`, cámbialo en el campo "URL de la API" de la pantalla de login.

## 3. Abrir la vista de cliente

Abre `app-cliente/index.html`. Ahí un cliente puede:
- Buscar un producto
- Ver en qué tiendas está disponible, con precio y stock de cada una
- Agregar al carrito y pedir a domicilio o recoger en tienda

**Nota:** el carrito solo permite productos de una tienda a la vez, porque cada tienda gestiona sus pedidos por separado.

## Cómo probar el flujo completo

1. Corre el backend.
2. Abre el panel de tienda → registra "Tienda A" → agrega un producto con stock y precio.
3. Abre otra pestaña, registra "Tienda B" → agrega el mismo producto con otro precio.
4. Abre la vista de cliente → busca ese producto → verás ambas tiendas comparadas por precio.
5. Agrega al carrito y confirma el pedido → en el panel de la tienda correspondiente aparecerá en "Pedidos".

## Siguientes pasos: convertir esto en app de PC y app Android

Ya tienes la lógica funcionando como web, que es la parte que más tiempo toma. Empaquetarla es más rápido:

### App de escritorio (PC) con Tauri
```bash
npm create tauri-app@latest
# apunta el "frontend" de Tauri a la carpeta panel-tienda/
```
Esto genera un `.exe`/`.dmg` instalable que abre tu panel como app nativa, sin depender del navegador.

### App Android con Capacitor
```bash
npm install
npx cap sync android
npx cap open android
```
El proyecto Android ya está generado en `android/` y empaqueta `app-cliente/` como una app real, reutilizando exactamente el mismo código.

Durante las pruebas, la app usa `http://192.168.101.11:8001` para llegar al backend local desde el teléfono conectado a la misma red Wi-Fi. Si cambia la IP del PC, actualiza `API_URL` en `app-cliente/index.html`. Antes de publicar en Google Play, cambia esa dirección por la URL HTTPS pública de tu API.

### Backend en producción
Para que las apps empaquetadas funcionen fuera de tu computador, el backend necesita estar en un servidor accesible por internet (Render, Railway, un VPS, etc.), no en `localhost`. Ahí es donde cambias la URL de la API en ambos frontends.

## Modelo de datos (resumen)

| Tabla | Qué guarda |
|---|---|
| `stores` | Tiendas registradas (nombre, dirección, login) |
| `products` | Catálogo global de productos |
| `inventory` | Stock y precio de cada producto **por tienda** (aquí vive la independencia entre tiendas) |
| `orders` / `order_items` | Pedidos hechos por clientes, ligados a una tienda específica |

## Endpoints principales de la API

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/auth/register` | Registrar una tienda |
| POST | `/auth/login` | Iniciar sesión (devuelve token) |
| GET | `/products?q=` | Buscar productos en el catálogo |
| GET | `/products/{id}/availability` | En qué tiendas hay un producto, con precio y stock |
| PUT | `/stores/me/inventory` | Agregar/actualizar stock y precio (requiere login) |
| POST | `/orders` | Crear un pedido |
| GET | `/orders/me` | Ver pedidos de tu tienda (requiere login) |
| PATCH | `/orders/{id}/status` | Cambiar estado de un pedido (requiere login) |
