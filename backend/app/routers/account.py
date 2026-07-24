"""Cuenta del cliente: direcciones, métodos de pago y devoluciones."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..database import get_db, serialize
from ..models import AddressIn, PaymentMethodIn, ReturnIn
from ..security import get_current_user, parse_object_id

router = APIRouter(prefix="/account", tags=["Mi cuenta"])


# ---------------------------------------------------------------- Direcciones
@router.get(
    "/addresses",
    summary="Listar mis direcciones",
    description=(
        "Pantalla **Direcciones**. Devuelve la libreta de direcciones del usuario; la que "
        "tenga `is_default: true` es la que el checkout debe preseleccionar.\n\n"
        "🔒 Requiere token."
    ),
)
async def list_addresses(user: dict = Depends(get_current_user)):
    cursor = get_db().addresses.find({"user_id": str(user["_id"])})
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/addresses",
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una dirección",
    description=(
        "Guarda una dirección de envío (nombre, teléfono, provincia, ciudad, dirección y "
        "referencia opcional).\n\n"
        "Si se envía `is_default: true`, el resto de direcciones dejan de ser la "
        "predeterminada automáticamente.\n\n🔒 Requiere token."
    ),
)
async def create_address(data: AddressIn, user: dict = Depends(get_current_user)):
    db = get_db()
    doc = data.model_dump() | {"user_id": str(user["_id"])}
    if data.is_default:
        await db.addresses.update_many(
            {"user_id": str(user["_id"])}, {"$set": {"is_default": False}}
        )
    result = await db.addresses.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.put(
    "/addresses/{address_id}",
    summary="Editar una dirección",
    description=(
        "Reemplaza todos los campos de la dirección (envía el objeto completo). "
        "Marcarla como predeterminada desmarca las demás.\n\n"
        "Solo puedes editar direcciones propias.\n\n"
        "🔒 Requiere token. **Errores:** `404` si no existe o no te pertenece."
    ),
    responses={404: {"description": "Dirección no encontrada"}},
)
async def update_address(
    data: AddressIn,
    address_id: str = Path(description="ID de la dirección a editar"),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    oid = parse_object_id(address_id, "dirección")
    if data.is_default:
        await db.addresses.update_many(
            {"user_id": str(user["_id"])}, {"$set": {"is_default": False}}
        )
    result = await db.addresses.find_one_and_update(
        {"_id": oid, "user_id": str(user["_id"])},
        {"$set": data.model_dump()},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dirección no encontrada")
    return serialize(result)


@router.delete(
    "/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una dirección",
    description=(
        "Borra la dirección de la libreta. Responde `204` sin cuerpo. "
        "Los pedidos ya realizados conservan su dirección: guardan una copia, no una "
        "referencia.\n\n"
        "🔒 Requiere token. **Errores:** `404` si no existe o no te pertenece."
    ),
    responses={404: {"description": "Dirección no encontrada"}},
)
async def delete_address(
    address_id: str = Path(description="ID de la dirección a eliminar"),
    user: dict = Depends(get_current_user),
):
    result = await get_db().addresses.delete_one(
        {"_id": parse_object_id(address_id, "dirección"), "user_id": str(user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dirección no encontrada")


# ---------------------------------------------------------------- Métodos de pago
# Solo se guardan etiquetas/último dígitos, nunca números completos de tarjeta.
@router.get(
    "/payment-methods",
    summary="Listar mis métodos de pago",
    description=(
        "Pantalla **Métodos de pago**. Devuelve las tarjetas y cuentas guardadas con su "
        "etiqueta (*«Visa terminada en 4821»*), vencimiento, titular y cuál es la "
        "**Principal** (`is_default`).\n\n🔒 Requiere token."
    ),
)
async def list_payment_methods(user: dict = Depends(get_current_user)):
    cursor = get_db().payment_methods.find({"user_id": str(user["_id"])})
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/payment-methods",
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un método de pago",
    description=(
        "Guarda un método de pago (`visa`, `mastercard` o `paypal`).\n\n"
        "⚠️ **Por diseño solo se almacenan datos no sensibles**: la etiqueta con los "
        "últimos 4 dígitos, el titular y el vencimiento. Nunca el número completo de "
        "tarjeta ni el CVV — eso corresponde al proveedor de pagos (tokenización).\n\n"
        "Marcarlo como principal desmarca los demás.\n\n🔒 Requiere token."
    ),
)
async def create_payment_method(data: PaymentMethodIn, user: dict = Depends(get_current_user)):
    db = get_db()
    doc = data.model_dump() | {"user_id": str(user["_id"])}
    if data.is_default:
        await db.payment_methods.update_many(
            {"user_id": str(user["_id"])}, {"$set": {"is_default": False}}
        )
    result = await db.payment_methods.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.put(
    "/payment-methods/{method_id}",
    summary="Editar un método de pago",
    description=(
        "Botón *Editar*. Reemplaza los datos del método (por ejemplo, actualizar el "
        "vencimiento o marcarlo como principal).\n\n"
        "🔒 Requiere token. **Errores:** `404` si no existe o no te pertenece."
    ),
    responses={404: {"description": "Método de pago no encontrado"}},
)
async def update_payment_method(
    data: PaymentMethodIn,
    method_id: str = Path(description="ID del método de pago a editar"),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    oid = parse_object_id(method_id, "método de pago")
    if data.is_default:
        await db.payment_methods.update_many(
            {"user_id": str(user["_id"])}, {"$set": {"is_default": False}}
        )
    result = await db.payment_methods.find_one_and_update(
        {"_id": oid, "user_id": str(user["_id"])},
        {"$set": data.model_dump()},
        return_document=True,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Método de pago no encontrado")
    return serialize(result)


@router.delete(
    "/payment-methods/{method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un método de pago",
    description=(
        "Botón *Eliminar*. Responde `204` sin cuerpo.\n\n"
        "🔒 Requiere token. **Errores:** `404` si no existe o no te pertenece."
    ),
    responses={404: {"description": "Método de pago no encontrado"}},
)
async def delete_payment_method(
    method_id: str = Path(description="ID del método de pago a eliminar"),
    user: dict = Depends(get_current_user),
):
    result = await get_db().payment_methods.delete_one(
        {"_id": parse_object_id(method_id, "método de pago"), "user_id": str(user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Método de pago no encontrado")


# ---------------------------------------------------------------- Devoluciones
async def _next_return_number() -> str:
    year = datetime.now(timezone.utc).year
    counter = await get_db().counters.find_one_and_update(
        {"_id": f"returns-{year}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return f"DEV-{year}-{counter['seq']:04d}"


@router.get(
    "/returns",
    summary="Listar mis devoluciones",
    description=(
        "Pantalla **Mis devoluciones**: *«Consulta el estado de tus solicitudes de "
        "devolución o cambio»*. Ordenadas de la más reciente a la más antigua.\n\n"
        "Cada solicitud trae su número (`DEV-2026-0001`), el producto, el motivo, la fecha "
        "y el `status`, que es la etiqueta de color de la tarjeta:\n\n"
        "| Estado | Etiqueta |\n|---|---|\n"
        "| `en_revision` | En revisión |\n| `aprobado` | Aprobado |\n"
        "| `rechazado` | Rechazado |\n| `completado` | Completado |\n\n"
        "🔒 Requiere token."
    ),
)
async def list_returns(user: dict = Depends(get_current_user)):
    cursor = get_db().returns.find({"user_id": str(user["_id"])}).sort("created_at", -1)
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/returns",
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar una devolución",
    description=(
        "Crea una solicitud de devolución o cambio para un producto de un pedido propio, "
        "indicando el motivo (ej. *«Producto dañado»*).\n\n"
        "Valida que el pedido sea tuyo y que el producto realmente pertenezca a ese pedido. "
        "Nace en estado `en_revision`; el equipo la resuelve desde el panel.\n\n"
        "🔒 Requiere token. **Errores:** `404` pedido inexistente o ajeno · "
        "`400` si el producto no pertenece a ese pedido."
    ),
    responses={
        404: {"description": "Pedido no encontrado"},
        400: {"description": "El producto no pertenece a este pedido"},
    },
)
async def create_return(data: ReturnIn, user: dict = Depends(get_current_user)):
    db = get_db()
    order = await db.orders.find_one(
        {"order_number": data.order_number, "user_id": str(user["_id"])}
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    item = next((i for i in order["items"] if i["product_id"] == data.product_id), None)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El producto no pertenece a este pedido")

    doc = {
        "return_number": await _next_return_number(),
        "user_id": str(user["_id"]),
        "order_number": data.order_number,
        "product_id": data.product_id,
        "product_name": item["name"],
        "reason": data.reason,
        "status": "en_revision",
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.returns.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)
