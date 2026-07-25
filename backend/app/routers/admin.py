"""Panel de administración: usuarios internos, productos, pedidos, cupones,
devoluciones, auditoría, panel (dashboard) y finanzas."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..database import get_db, serialize
from ..models import (
    CouponIn,
    InternalUserIn,
    InternalUserUpdateIn,
    OrderStatusUpdateIn,
    ProductIn,
    ProductUpdateIn,
    ReturnStatusUpdateIn,
)
from ..security import (
    INTERNAL_ROLES,
    hash_password,
    log_audit,
    parse_object_id,
    require_admin,
    require_finance,
    require_product_editor,
    require_sales,
    require_staff,
)
from .uploads import eliminar_archivo

router = APIRouter(prefix="/admin", tags=["Administración"])

# Matriz de permisos por rol (pantalla "Permisos" del panel)
ROLE_PERMISSIONS = {
    "admin": ["usuarios", "roles", "productos", "pedidos", "cupones", "devoluciones", "finanzas", "auditoria", "configuracion"],
    "vendedor": ["pedidos", "productos:lectura"],
    "encargado": ["productos", "pedidos", "devoluciones"],
    "soporte": ["pedidos:lectura", "devoluciones"],
    "editor": ["productos"],
    "finanzas": ["finanzas", "pedidos:lectura"],
}


# ---------------------------------------------------------------- Usuarios internos
@router.get(
    "/users",
    summary="Listar usuarios internos",
    description=(
        "Tabla de la pantalla **Usuarios** (*«Gestiona los usuarios internos de la "
        "plataforma»*): nombre, correo, rol y estado activo/inactivo.\n\n"
        "Solo devuelve cuentas con rol interno — los clientes de la tienda no aparecen aquí.\n\n"
        "El parámetro `role` implementa el *Filtrado por Rol* (`?role=vendedor`).\n\n"
        "🔒 Rol requerido: **admin**."
    ),
)
async def list_internal_users(
    role: str | None = Query(
        None, description="Filtrar por rol: admin, vendedor, encargado, soporte, editor o finanzas"
    ),
    actor: dict = Depends(require_admin),
):
    query: dict = {"role": {"$in": list(INTERNAL_ROLES)}}
    if role:
        query["role"] = role.lower()
    cursor = get_db().users.find(query).sort("name", 1)
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario interno",
    description=(
        "Formulario **Nuevo Usuario Interno**: datos personales, rol asignado y contraseña "
        "temporal.\n\n"
        "- `must_change_password`: corresponde al switch *«El usuario deberá cambiarla en "
        "su primer ingreso»*. El login devuelve esta bandera para que el frontend fuerce "
        "el cambio.\n"
        "- `active`: switch *«Usuario activo — puede iniciar sesión inmediatamente»*.\n"
        "- El correo se marca como verificado (lo crea un administrador, no requiere "
        "confirmación).\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Rol requerido: **admin**. **Errores:** `409` si el correo ya existe."
    ),
    responses={409: {"description": "El correo ya está registrado"}},
)
async def create_internal_user(data: InternalUserIn, actor: dict = Depends(require_admin)):
    db = get_db()
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya está registrado")
    doc = {
        "name": data.name,
        "email": data.email,
        "description": data.description,
        "phone": data.phone,
        "role": data.role,
        "active": data.active,
        "email_verified": True,
        "password_hash": hash_password(data.temp_password),
        "must_change_password": data.must_change_password,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    await log_audit(actor, "crear", "usuario", f"{data.name} ({data.role})")
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.patch(
    "/users/{user_id}",
    summary="Editar un usuario interno",
    description=(
        "Modal **Editar Usuario** (nombre, correo, rol, estado). Es una actualización "
        "**parcial**: solo se modifican los campos enviados.\n\n"
        "También es el endpoint del switch Activo/Inactivo de la tabla — basta con enviar "
        "`{\"active\": false}`. Un usuario inactivo no puede iniciar sesión y sus tokens "
        "dejan de funcionar.\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Rol requerido: **admin**. **Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Usuario no encontrado"}},
)
async def update_internal_user(
    data: InternalUserUpdateIn,
    user_id: str = Path(description="ID del usuario interno a editar"),
    actor: dict = Depends(require_admin),
):
    db = get_db()
    updates = data.model_dump(exclude_none=True)
    result = await db.users.find_one_and_update(
        {"_id": parse_object_id(user_id, "usuario"), "role": {"$in": list(INTERNAL_ROLES)}},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    await log_audit(actor, "editar", "usuario", f"{result['name']}: {', '.join(updates)}")
    return serialize(result)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un usuario interno",
    description=(
        "Icono de papelera de la tabla de usuarios. Responde `204` sin cuerpo.\n\n"
        "**Protección:** no puedes eliminar tu propia cuenta (evita que un admin se "
        "quede fuera del sistema). Para retirar el acceso sin borrar el historial, "
        "conviene desactivar en vez de eliminar.\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Rol requerido: **admin**. **Errores:** `400` si intentas eliminarte a ti "
        "mismo · `404` si no existe."
    ),
    responses={
        400: {"description": "No puedes eliminar tu propia cuenta"},
        404: {"description": "Usuario no encontrado"},
    },
)
async def delete_internal_user(
    user_id: str = Path(description="ID del usuario interno a eliminar"),
    actor: dict = Depends(require_admin),
):
    oid = parse_object_id(user_id, "usuario")
    if oid == actor["_id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes eliminar tu propia cuenta")
    result = await get_db().users.find_one_and_delete(
        {"_id": oid, "role": {"$in": list(INTERNAL_ROLES)}}
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    await log_audit(actor, "eliminar", "usuario", result["name"])


@router.get(
    "/roles",
    summary="Matriz de roles y permisos",
    description=(
        "Pantalla **Permisos / Roles**. Devuelve cada rol interno con la lista de módulos "
        "que puede usar, para pintar la matriz de permisos y los chips de rol de los "
        "formularios.\n\n"
        "El sufijo `:lectura` indica acceso de solo lectura (ej. `pedidos:lectura`).\n\n"
        "🔒 Requiere cualquier rol interno."
    ),
)
async def list_roles(actor: dict = Depends(require_staff)):
    return [{"role": role, "permissions": perms} for role, perms in ROLE_PERMISSIONS.items()]


# ---------------------------------------------------------------- Productos
@router.get(
    "/products",
    summary="Listar productos (panel)",
    description=(
        "Tabla de la pantalla **Productos** del panel: nombre, categoría, precio y stock, "
        "con el pie *«Mostrando 6 de 12 productos»* y paginación.\n\n"
        "A diferencia del catálogo público, **incluye los productos inactivos**.\n\n"
        "**Filtros:** `search` (buscador por nombre), `category` y `low_stock=true` para "
        "ver solo lo que está por agotarse (stock < 5, la etiqueta *Bajo*).\n\n"
        "🔒 Requiere cualquier rol interno."
    ),
)
async def list_products_admin(
    search: str | None = Query(None, description="Buscar por nombre del producto"),
    category: str | None = Query(
        None, description="Categoría: sofa, silla, mesa, cama, lampara o espejo"
    ),
    low_stock: bool = Query(False, description="Solo productos con stock bajo (< 5)"),
    page: int = Query(1, ge=1, description="Número de página, empezando en 1"),
    page_size: int = Query(6, ge=1, le=50, description="Productos por página (máx. 50)"),
    actor: dict = Depends(require_staff),
):
    db = get_db()
    query: dict = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if category:
        query["category"] = category
    if low_stock:
        query["stock"] = {"$lt": 5}
    total = await db.products.count_documents(query)
    cursor = db.products.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    return {
        "items": [serialize(doc) async for doc in cursor],
        "total": total,
        "page": page,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un producto",
    description=(
        "Botón **+ Nuevo** de la pantalla Productos.\n\n"
        "Campos obligatorios: `name`, `price` (mayor que 0), `category` y `material`. "
        "Opcionales: descripción, color, stock, `images` (URLs de la galería) y las "
        "viñetas de la ficha (`dimensions`, `structure`, `warranty`).\n\n"
        "Nace con calificación en 0 y, si `active` es `true`, aparece de inmediato en el "
        "catálogo público. Queda registrado en la auditoría.\n\n"
        "🔒 Roles: **admin**, **editor**, **encargado**."
    ),
)
async def create_product(data: ProductIn, actor: dict = Depends(require_product_editor)):
    doc = data.model_dump() | {
        "rating_avg": 0,
        "rating_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_db().products.insert_one(doc)
    await log_audit(actor, "crear", "producto", data.name)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.patch(
    "/products/{product_id}",
    summary="Editar un producto",
    description=(
        "Icono de lápiz de la tabla. Actualización **parcial**: envía solo los campos que "
        "cambian.\n\n"
        "Es también la vía para reponer inventario (`{\"stock\": 20}`) o para ocultar un "
        "producto del catálogo sin borrarlo (`{\"active\": false}`).\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Roles: **admin**, **editor**, **encargado**. **Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Producto no encontrado"}},
)
async def update_product(
    data: ProductUpdateIn,
    product_id: str = Path(description="ID del producto a editar"),
    actor: dict = Depends(require_product_editor),
):
    updates = data.model_dump(exclude_none=True)
    oid = parse_object_id(product_id, "producto")

    # Se guardan las imágenes actuales para borrar del disco las que se quiten
    anterior = await get_db().products.find_one({"_id": oid}) if "images" in updates else None

    result = await get_db().products.find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    if anterior:
        for ruta in set(anterior.get("images") or []) - set(updates["images"]):
            eliminar_archivo(ruta)

    await log_audit(actor, "editar", "producto", f"{result['name']}: {', '.join(updates)}")
    return serialize(result)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un producto",
    description=(
        "Modal *«¿Eliminar este producto? Esta opción no se puede deshacer»*. "
        "Responde `204` sin cuerpo.\n\n"
        "Borra el producto del catálogo de forma permanente. Los pedidos anteriores no se "
        "ven afectados: guardan una copia de los datos del producto. Si solo quieres "
        "retirarlo de la tienda, usa `PATCH` con `active: false`.\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Roles: **admin**, **editor**, **encargado**. **Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Producto no encontrado"}},
)
async def delete_product(
    product_id: str = Path(description="ID del producto a eliminar"),
    actor: dict = Depends(require_product_editor),
):
    result = await get_db().products.find_one_and_delete(
        {"_id": parse_object_id(product_id, "producto")}
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    # Las imágenes del producto se borran del disco para no dejar archivos huérfanos
    for ruta in result.get("images") or []:
        eliminar_archivo(ruta)

    await log_audit(actor, "eliminar", "producto", result["name"])


# ---------------------------------------------------------------- Pedidos
@router.get(
    "/orders",
    summary="Listar todos los pedidos",
    description=(
        "Bandeja de pedidos del panel: todos los pedidos de la tienda (de clientes y de "
        "invitados), del más reciente al más antiguo, con paginación.\n\n"
        "Filtra por estado con `?status=confirmado` "
        "(`confirmado`, `en_preparacion`, `en_camino`, `entregado`, `cancelado`).\n\n"
        "🔒 Roles: **admin**, **vendedor**, **encargado**, **soporte**."
    ),
)
async def list_orders(
    order_status: str | None = Query(
        None,
        alias="status",
        description="Filtrar por estado: confirmado, en_preparacion, en_camino, entregado o cancelado",
    ),
    page: int = Query(1, ge=1, description="Número de página, empezando en 1"),
    page_size: int = Query(10, ge=1, le=50, description="Pedidos por página (máx. 50)"),
    actor: dict = Depends(require_sales),
):
    db = get_db()
    query: dict = {}
    if order_status:
        query["status"] = order_status
    total = await db.orders.count_documents(query)
    cursor = db.orders.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    return {
        "items": [serialize(doc) async for doc in cursor],
        "total": total,
        "page": page,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.patch(
    "/orders/{order_number}/status",
    summary="Cambiar el estado de un pedido",
    description=(
        "Avanza el pedido en su ciclo de vida y **agrega una entrada con fecha y hora a "
        "`status_history`**, que es lo que alimenta la línea de tiempo que ve el cliente.\n\n"
        "Flujo normal: `confirmado → en_preparacion → en_camino → entregado` "
        "(o `cancelado` en cualquier punto).\n\n"
        "Al pasar a `en_camino` conviene enviar también `tracking_number`, el número de "
        "guía del courier (ej. `GLE-88420193PA`).\n\n"
        "Se identifica el pedido por su número (`TEC-2026-001`), no por su id. "
        "Queda registrado en la auditoría.\n\n"
        "🔒 Roles: **admin**, **vendedor**, **encargado**, **soporte**. "
        "**Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Pedido no encontrado"}},
)
async def update_order_status(
    data: OrderStatusUpdateIn,
    order_number: str = Path(description="Número del pedido. Ej. «TEC-2026-001»"),
    actor: dict = Depends(require_sales),
):
    db = get_db()
    updates: dict = {"status": data.status}
    if data.tracking_number is not None:
        updates["tracking_number"] = data.tracking_number
    result = await db.orders.find_one_and_update(
        {"order_number": order_number},
        {
            "$set": updates,
            "$push": {
                "status_history": {"status": data.status, "timestamp": datetime.now(timezone.utc)}
            },
        },
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    await log_audit(actor, "actualizar-estado", "pedido", f"{order_number} → {data.status}")
    return serialize(result)


# ---------------------------------------------------------------- Devoluciones
@router.get(
    "/returns",
    summary="Listar todas las devoluciones",
    description=(
        "Bandeja de solicitudes de devolución de todos los clientes, de la más reciente a "
        "la más antigua.\n\n"
        "Filtra con `?status=en_revision` para ver únicamente lo pendiente de resolver.\n\n"
        "🔒 Roles: **admin**, **vendedor**, **encargado**, **soporte**."
    ),
)
async def list_all_returns(
    return_status: str | None = Query(
        None,
        alias="status",
        description="Filtrar por estado: en_revision, aprobado, rechazado o completado",
    ),
    actor: dict = Depends(require_sales),
):
    query: dict = {}
    if return_status:
        query["status"] = return_status
    cursor = get_db().returns.find(query).sort("created_at", -1)
    return [serialize(doc) async for doc in cursor]


@router.patch(
    "/returns/{return_id}/status",
    summary="Resolver una devolución",
    description=(
        "Cambia el estado de una solicitud de devolución. El cliente ve el resultado en "
        "*Mis devoluciones*.\n\n"
        "| Estado | Significado |\n|---|---|\n"
        "| `en_revision` | Recién solicitada, pendiente de evaluar |\n"
        "| `aprobado` | Se acepta la devolución |\n"
        "| `rechazado` | No procede |\n"
        "| `completado` | Devolución finalizada (producto recibido / reembolso hecho) |\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Roles: **admin**, **vendedor**, **encargado**, **soporte**. "
        "**Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Devolución no encontrada"}},
)
async def update_return_status(
    data: ReturnStatusUpdateIn,
    return_id: str = Path(description="ID de la solicitud de devolución"),
    actor: dict = Depends(require_sales),
):
    result = await get_db().returns.find_one_and_update(
        {"_id": parse_object_id(return_id, "devolución")},
        {"$set": {"status": data.status}},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Devolución no encontrada")
    await log_audit(actor, "actualizar-estado", "devolución", f"{result['return_number']} → {data.status}")
    return serialize(result)


# ---------------------------------------------------------------- Cupones
@router.get(
    "/coupons",
    summary="Listar cupones",
    description=(
        "Todos los códigos de descuento con su porcentaje y si están activos.\n\n"
        "🔒 Requiere cualquier rol interno."
    ),
)
async def list_coupons(actor: dict = Depends(require_staff)):
    cursor = get_db().coupons.find()
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/coupons",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un cupón",
    description=(
        "Crea un código de descuento porcentual (ej. `TECA10` con `discount_percent: 10`). "
        "El código se guarda **en mayúsculas** y debe ser único.\n\n"
        "Los clientes lo aplican desde el carrito con `POST /cart/coupon`. "
        "Poner `active: false` lo desactiva sin borrarlo.\n\n"
        "Queda registrado en la auditoría.\n\n"
        "🔒 Rol requerido: **admin**. **Errores:** `409` si el código ya existe."
    ),
    responses={409: {"description": "El cupón ya existe"}},
)
async def create_coupon(data: CouponIn, actor: dict = Depends(require_admin)):
    db = get_db()
    code = data.code.upper()
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(status.HTTP_409_CONFLICT, "El cupón ya existe")
    doc = {"code": code, "discount_percent": data.discount_percent, "active": data.active}
    result = await db.coupons.insert_one(doc)
    await log_audit(actor, "crear", "cupón", code)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.delete(
    "/coupons/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un cupón",
    description=(
        "Borra el cupón por su código. Responde `204` sin cuerpo.\n\n"
        "Los pedidos que ya lo usaron conservan el descuento aplicado. "
        "Queda registrado en la auditoría.\n\n"
        "🔒 Rol requerido: **admin**. **Errores:** `404` si no existe."
    ),
    responses={404: {"description": "Cupón no encontrado"}},
)
async def delete_coupon(
    code: str = Path(description="Código del cupón. Ej. «TECA10»"),
    actor: dict = Depends(require_admin),
):
    result = await get_db().coupons.delete_one({"code": code.upper()})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cupón no encontrado")
    await log_audit(actor, "eliminar", "cupón", code.upper())


# ---------------------------------------------------------------- Auditoría
@router.get(
    "/audit",
    summary="Registro de auditoría",
    description=(
        "Pantalla **Auditoría**: historial de acciones administrativas, de la más reciente "
        "a la más antigua.\n\n"
        "Cada entrada guarda **quién** (`actor_name`), **qué hizo** (`action`: crear, "
        "editar, eliminar, actualizar-estado), **sobre qué** (`entity`: usuario, producto, "
        "pedido, cupón, devolución), un `detail` legible y la fecha/hora.\n\n"
        "Es un registro de solo lectura: se escribe automáticamente y no se puede editar "
        "ni borrar desde la API.\n\n"
        "🔒 Rol requerido: **admin**."
    ),
)
async def audit_log(
    page: int = Query(1, ge=1, description="Número de página, empezando en 1"),
    page_size: int = Query(20, ge=1, le=100, description="Registros por página (máx. 100)"),
    actor: dict = Depends(require_admin),
):
    db = get_db()
    total = await db.audit_log.count_documents({})
    cursor = db.audit_log.find().sort("timestamp", -1).skip((page - 1) * page_size).limit(page_size)
    return {
        "items": [serialize(doc) async for doc in cursor],
        "total": total,
        "page": page,
        "total_pages": max(1, -(-total // page_size)),
    }


# ---------------------------------------------------------------- Panel y finanzas
@router.get(
    "/dashboard",
    summary="Métricas del panel",
    description=(
        "Tarjetas de la pantalla **Panel**. Una sola llamada devuelve todos los "
        "indicadores:\n\n"
        "| Campo | Significado |\n|---|---|\n"
        "| `total_orders` | Pedidos realizados (excluye cancelados) |\n"
        "| `total_revenue` | Ingresos acumulados en B/. |\n"
        "| `total_products` | Productos en el catálogo |\n"
        "| `low_stock_products` | Productos con stock bajo (< 5) — alerta de reposición |\n"
        "| `total_customers` | Clientes registrados |\n"
        "| `pending_returns` | Devoluciones en revisión, pendientes de resolver |\n\n"
        "🔒 Requiere cualquier rol interno."
    ),
)
async def dashboard(actor: dict = Depends(require_staff)):
    db = get_db()
    revenue = await db.orders.aggregate(
        [
            {"$match": {"status": {"$ne": "cancelado"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}},
        ]
    ).to_list(1)
    return {
        "total_orders": revenue[0]["count"] if revenue else 0,
        "total_revenue": round(revenue[0]["total"], 2) if revenue else 0,
        "total_products": await db.products.count_documents({}),
        "low_stock_products": await db.products.count_documents({"stock": {"$lt": 5}}),
        "total_customers": await db.users.count_documents({"role": "cliente"}),
        "pending_returns": await db.returns.count_documents({"status": "en_revision"}),
    }


@router.get(
    "/finance/summary",
    summary="Resumen financiero",
    description=(
        "Pantalla **Finanzas**. Agrega las ventas (excluyendo pedidos cancelados) en dos "
        "cortes:\n\n"
        "- `monthly`: por mes (`YYYY-MM`) con ingresos, cantidad de pedidos, descuentos "
        "otorgados y cobros de envío — ideal para la gráfica de evolución.\n"
        "- `by_payment_method`: ingresos y pedidos por método de pago "
        "(`card`, `paypal`, `bitcoin`, `yappy`) — ideal para la gráfica de distribución.\n\n"
        "Los montos vienen redondeados a 2 decimales, en balboas.\n\n"
        "🔒 Roles: **admin**, **finanzas**."
    ),
)
async def finance_summary(actor: dict = Depends(require_finance)):
    db = get_db()
    by_month = await db.orders.aggregate(
        [
            {"$match": {"status": {"$ne": "cancelado"}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "revenue": {"$sum": "$total"},
                    "orders": {"$sum": 1},
                    "discounts": {"$sum": "$discount"},
                    "shipping": {"$sum": "$shipping"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    ).to_list(None)
    by_method = await db.orders.aggregate(
        [
            {"$match": {"status": {"$ne": "cancelado"}}},
            {"$group": {"_id": "$payment_method", "revenue": {"$sum": "$total"}, "orders": {"$sum": 1}}},
        ]
    ).to_list(None)
    return {
        "monthly": [
            {"month": r["_id"], "revenue": round(r["revenue"], 2), "orders": r["orders"],
             "discounts": round(r["discounts"], 2), "shipping": round(r["shipping"], 2)}
            for r in by_month
        ],
        "by_payment_method": [
            {"method": r["_id"], "revenue": round(r["revenue"], 2), "orders": r["orders"]}
            for r in by_method
        ],
    }
