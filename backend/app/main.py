"""API de TECA — backend del e-commerce de muebles.

Ejecutar:  uvicorn app.main:app --reload
Docs:      http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from . import database
from .config import get_settings
from .routers import account, admin, auth, cart, orders, products


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.disconnect()


TAGS_METADATA = [
    {
        "name": "Autenticación",
        "description": (
            "Registro de clientes, verificación de correo, inicio de sesión (JWT), "
            "recuperación y cambio de contraseña, y perfil propio.\n\n"
            "**Cómo autenticarse:** llama a `POST /auth/login`, copia el `access_token` "
            "y pulsa el botón **Authorize** de esta página para enviarlo como "
            "`Authorization: Bearer <token>` en el resto de peticiones."
        ),
    },
    {
        "name": "Catálogo",
        "description": (
            "Endpoints **públicos** de la tienda: listado de productos con filtros "
            "(categoría, material, rango de precio), búsqueda por texto, ordenamiento "
            "y paginación; detalle del producto y reseñas."
        ),
    },
    {
        "name": "Carrito",
        "description": (
            "Carrito persistente del cliente autenticado. Valida stock en cada operación "
            "y devuelve siempre el resumen del pedido (subtotal, envío, descuento, total "
            "y cuánto falta para el envío gratis).\n\n"
            "Los **invitados** manejan el carrito en el frontend y envían los items "
            "directamente a `POST /orders/checkout`."
        ),
    },
    {
        "name": "Pedidos",
        "description": (
            "Checkout (con o sin cuenta), historial de pedidos y seguimiento del estado "
            "con línea de tiempo y número de guía."
        ),
    },
    {
        "name": "Mi cuenta",
        "description": (
            "Datos guardados del cliente: direcciones de envío, métodos de pago "
            "(solo etiquetas, nunca números completos de tarjeta) y solicitudes de devolución."
        ),
    },
    {
        "name": "Administración",
        "description": (
            "Panel interno. Cada endpoint exige uno de los roles internos: "
            "`admin`, `vendedor`, `encargado`, `soporte`, `editor`, `finanzas`. "
            "Las acciones administrativas quedan registradas en la auditoría."
        ),
    },
    {"name": "Salud", "description": "Verificación de que el servicio está en línea."},
]

DESCRIPTION = """
API del e-commerce de muebles **TECA — Para toda la vida**.

Cubre la tienda pública (catálogo, carrito, checkout de invitado o con cuenta),
el área del cliente (pedidos, direcciones, métodos de pago, devoluciones) y el
panel de administración (usuarios internos, productos, pedidos, cupones,
auditoría y finanzas).

### Autenticación
Todas las rutas protegidas usan **JWT Bearer**:

1. `POST /auth/login` con correo y contraseña.
2. Copia el `access_token` de la respuesta.
3. Pulsa **Authorize** (arriba a la derecha) y pégalo.

### Roles
| Rol | Alcance |
|---|---|
| `cliente` | Tienda: carrito, pedidos propios, cuenta, reseñas |
| `admin` | Acceso total al panel |
| `editor` | Productos |
| `encargado` | Productos, pedidos y devoluciones |
| `vendedor` | Pedidos (y lectura de productos) |
| `soporte` | Devoluciones y lectura de pedidos |
| `finanzas` | Reportes financieros |

### Convenciones
- Moneda: balboas (B/.), equivalente a USD.
- Los identificadores son `ObjectId` de Mongo expuestos como `id` (string).
- Errores en formato `{"detail": "mensaje"}` con el código HTTP correspondiente.
"""

app = FastAPI(
    title="TECA API",
    description=DESCRIPTION,
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(account.router)
app.include_router(admin.router)


# Los esquemas de error que genera FastAPI vienen en inglés; aquí se traducen.
ERROR_SCHEMAS = {
    "HTTPValidationError": {
        "title": "Error de validación",
        "fields": {"detail": "Detalle del error"},
    },
    "ValidationError": {
        "title": "Detalle de validación",
        "fields": {"loc": "Ubicación del campo", "msg": "Mensaje", "type": "Tipo de error"},
    },
}


def _rename_refs(node: Any, mapping: dict[str, str]) -> Any:
    """Reescribe las referencias $ref tras renombrar los esquemas."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            old = ref.rsplit("/", 1)[1]
            if old in mapping:
                node["$ref"] = f"#/components/schemas/{mapping[old]}"
        return {key: _rename_refs(value, mapping) for key, value in node.items()}
    if isinstance(node, list):
        return [_rename_refs(item, mapping) for item in node]
    return node


def custom_openapi() -> dict:
    """Genera el OpenAPI con los nombres de esquema en español.

    FastAPI nombra los esquemas con el nombre de la clase de Python (`RegisterIn`),
    y eso es lo que Swagger muestra en la sección *Schemas*. Aquí se sustituye por
    el título en español de cada modelo, reescribiendo las referencias.
    """
    if app.openapi_schema:
        return app.openapi_schema

    spec = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=app.openapi_tags,
        routes=app.routes,
    )
    schemas = spec.get("components", {}).get("schemas", {})

    # Traducir los esquemas de error que genera FastAPI
    for name, traduccion in ERROR_SCHEMAS.items():
        schema = schemas.get(name)
        if schema is None:
            continue
        schema["title"] = traduccion["title"]
        for field, titulo in traduccion["fields"].items():
            if field in schema.get("properties", {}):
                schema["properties"][field]["title"] = titulo

    # Renombrar cada esquema usando su título en español
    mapping: dict[str, str] = {}
    usados: set[str] = set()
    for name, schema in schemas.items():
        titulo = schema.get("title", name)
        if titulo == name or titulo in usados:
            continue
        mapping[name] = titulo
        usados.add(titulo)

    if mapping:
        spec["components"]["schemas"] = {
            mapping.get(name, name): schema for name, schema in schemas.items()
        }
        spec = _rename_refs(spec, mapping)

    app.openapi_schema = spec
    return spec


app.openapi = custom_openapi


@app.get(
    "/",
    tags=["Salud"],
    summary="Estado del servicio",
    description="Devuelve `{'status': 'ok'}` si la API está en línea. Útil para healthchecks.",
)
async def health():
    return {"status": "ok", "service": "TECA API"}
