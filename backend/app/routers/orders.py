"""Checkout y pedidos: creación (usuario o invitado), consulta y seguimiento."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..database import get_db, serialize
from ..models import CheckoutIn, OrderLookupIn
from ..security import get_current_user, get_optional_user, parse_object_id
from .cart import build_summary

router = APIRouter(prefix="/orders", tags=["Pedidos"])

STATUS_FLOW = ["confirmado", "en_preparacion", "en_camino", "entregado"]


async def _next_order_number() -> str:
    """Genera números tipo TEC-2026-001 con un contador atómico por año."""
    year = datetime.now(timezone.utc).year
    counter = await get_db().counters.find_one_and_update(
        {"_id": f"orders-{year}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return f"TEC-{year}-{counter['seq']:03d}"


@router.post(
    "/checkout",
    status_code=status.HTTP_201_CREATED,
    summary="Crear un pedido (checkout)",
    description=(
        "Cierra la compra y genera el pedido. Es el paso *Pago → Confirmación* del "
        "checkout.\n\n"
        "**Funciona con y sin cuenta.** El token es opcional: si se envía, el pedido queda "
        "asociado al usuario y se le vacía el carrito; si no, se registra como pedido de "
        "**invitado** (por eso `email` es obligatorio siempre — es el correo con el que "
        "luego podrá consultar su pedido).\n\n"
        "**Qué hace, en orden:**\n"
        "1. Valida que cada producto exista, esté activo y tenga stock suficiente.\n"
        "2. Recalcula precios **en el servidor** (nunca confía en los totales del "
        "frontend) y aplica el cupón si se envió.\n"
        "3. Genera el número correlativo del pedido (`TEC-2026-001`) con un contador "
        "atómico por año.\n"
        "4. Descuenta el stock de cada producto.\n"
        "5. Deja el pedido en estado `confirmado` con su primer registro en la línea de "
        "tiempo.\n\n"
        "**Métodos de pago** (`payment_method`): `card`, `paypal`, `bitcoin`, `yappy`. "
        "El cobro está **simulado**: el pedido nace con `payment_status: pagado`; "
        "aquí se integraría la pasarela real.\n\n"
        "**Errores:** `404` producto inexistente · `409` stock insuficiente · "
        "`400` cupón inválido."
    ),
    responses={
        404: {"description": "Producto no encontrado"},
        409: {"description": "Stock insuficiente para algún producto"},
        400: {"description": "Cupón inválido o expirado"},
    },
)
async def checkout(data: CheckoutIn, user: dict | None = Depends(get_optional_user)):
    db = get_db()

    # Validar stock de todos los items antes de crear el pedido
    for item in data.items:
        product = await db.products.find_one(
            {"_id": parse_object_id(item.product_id, "producto"), "active": True}
        )
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Producto {item.product_id} no encontrado")
        if item.quantity > product.get("stock", 0):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Stock insuficiente para '{product['name']}' (disponible: {product.get('stock', 0)})",
            )

    summary = await build_summary(
        [i.model_dump() for i in data.items], data.coupon_code
    )
    if data.coupon_code and summary["coupon_code"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cupón inválido o expirado")

    now = datetime.now(timezone.utc)
    order = {
        "order_number": await _next_order_number(),
        "user_id": str(user["_id"]) if user else None,
        "email": data.email,
        "guest": user is None,
        "items": summary["items"],
        "shipping_address": data.shipping_address.model_dump(),
        "shipping_method": data.shipping_method,
        "payment_method": data.payment_method,
        "payment_status": "pagado",  # pago simulado: se confirma al crear el pedido
        "subtotal": summary["subtotal"],
        "shipping": summary["shipping"],
        "coupon_code": summary["coupon_code"],
        "discount": summary["discount"],
        "total": summary["total"],
        "status": "confirmado",
        "tracking_number": None,
        "status_history": [{"status": "confirmado", "timestamp": now}],
        "created_at": now,
    }
    await db.orders.insert_one(order)

    # Descontar stock
    for item in data.items:
        await db.products.update_one(
            {"_id": parse_object_id(item.product_id, "producto")},
            {"$inc": {"stock": -item.quantity}},
        )

    # Vaciar carrito del usuario autenticado
    if user:
        await db.carts.update_one(
            {"user_id": str(user["_id"])}, {"$set": {"items": [], "coupon_code": None}}
        )

    return serialize(order)


@router.get(
    "/mine",
    summary="Mis pedidos",
    description=(
        "Pantalla **Mis pedidos** del área de cliente. Devuelve todos los pedidos del "
        "usuario autenticado, del más reciente al más antiguo.\n\n"
        "Un arreglo vacío es la señal para mostrar el estado *«Todavía no tienes pedidos»*.\n\n"
        "🔒 Requiere token."
    ),
)
async def my_orders(user: dict = Depends(get_current_user)):
    cursor = get_db().orders.find({"user_id": str(user["_id"])}).sort("created_at", -1)
    return [serialize(doc) async for doc in cursor]


@router.post(
    "/lookup",
    summary="Consultar un pedido sin cuenta (invitado)",
    description=(
        "Permite a quien compró como invitado rastrear su pedido: *«Puedes consultar el "
        "estado de tu pedido usando el número de pedido y tu correo electrónico»*.\n\n"
        "Exige **ambos datos** (`order_number` + `email`) y deben coincidir, de modo que "
        "un número de pedido adivinado no basta para ver los datos de otra persona.\n\n"
        "**No requiere token. Errores:** `404` si la combinación no coincide."
    ),
    responses={404: {"description": "Pedido no encontrado"}},
)
async def lookup_order(data: OrderLookupIn):
    """Consulta de pedido para invitados: número de pedido + correo."""
    order = await get_db().orders.find_one(
        {"order_number": data.order_number, "email": data.email}
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return serialize(order)


@router.get(
    "/{order_number}",
    summary="Detalle y seguimiento de un pedido",
    description=(
        "Pantalla **Pedido TEC-2026-001**: información de envío, productos, resumen de "
        "totales y `tracking_number` (número de guía del courier).\n\n"
        "El campo `status_history` trae cada estado con su fecha y hora, que es lo que "
        "dibuja la línea de tiempo *Pedido confirmado → En preparación → En camino → "
        "Entregado*.\n\n"
        "**Visibilidad:** un `cliente` solo puede ver sus propios pedidos; los roles "
        "internos pueden consultar cualquiera.\n\n"
        "🔒 Requiere token. **Errores:** `404` si no existe o no te pertenece."
    ),
    responses={404: {"description": "Pedido no encontrado"}},
)
async def get_order(
    order_number: str = Path(description="Número del pedido. Ej. «TEC-2026-001»"),
    user: dict = Depends(get_current_user),
):
    query: dict = {"order_number": order_number}
    if user["role"] == "cliente":
        query["user_id"] = str(user["_id"])  # un cliente solo ve sus pedidos
    order = await get_db().orders.find_one(query)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return serialize(order)
