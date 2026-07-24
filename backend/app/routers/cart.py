"""Carrito de compra del usuario autenticado (los invitados manejan el carrito
en el frontend y envían los items directamente al checkout)."""
from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..config import get_settings
from ..database import get_db
from ..models import CartItemIn, CouponApplyIn
from ..security import get_current_user, parse_object_id

router = APIRouter(prefix="/cart", tags=["Carrito"])


async def _get_cart(user_id: str) -> dict:
    db = get_db()
    cart = await db.carts.find_one({"user_id": user_id})
    if cart is None:
        cart = {"user_id": user_id, "items": [], "coupon_code": None}
        await db.carts.insert_one(cart)
    return cart


async def build_summary(items: list[dict], coupon_code: str | None) -> dict:
    """Calcula subtotal, envío, descuento y total. Reutilizado por el checkout."""
    db = get_db()
    settings = get_settings()
    detailed, subtotal = [], 0.0
    for item in items:
        product = await db.products.find_one({"_id": parse_object_id(item["product_id"], "producto")})
        if product is None or not product.get("active", True):
            continue
        line_total = round(product["price"] * item["quantity"], 2)
        subtotal += line_total
        detailed.append(
            {
                "product_id": item["product_id"],
                "name": product["name"],
                "price": product["price"],
                "material": product.get("material"),
                "image": (product.get("images") or [None])[0],
                "quantity": item["quantity"],
                "stock": product.get("stock", 0),
                "subtotal": line_total,
            }
        )

    subtotal = round(subtotal, 2)
    shipping = 0.0 if subtotal >= settings.free_shipping_threshold else settings.shipping_cost
    missing_for_free = max(0.0, round(settings.free_shipping_threshold - subtotal, 2))

    discount = 0.0
    coupon_valid = False
    if coupon_code:
        coupon = await db.coupons.find_one({"code": coupon_code.upper(), "active": True})
        if coupon:
            discount = round(subtotal * coupon["discount_percent"] / 100, 2)
            coupon_valid = True

    return {
        "items": detailed,
        "subtotal": subtotal,
        "shipping": shipping,
        "missing_for_free_shipping": missing_for_free,
        "coupon_code": coupon_code if coupon_valid else None,
        "discount": discount,
        "total": round(subtotal + shipping - discount, 2),
    }


@router.get(
    "",
    summary="Ver mi carrito",
    description=(
        "Pantalla **Carrito de compra**. Devuelve los items con datos frescos del producto "
        "(nombre, precio, material, imagen, stock y subtotal de línea) más el bloque "
        "*Resumen del pedido*:\n\n"
        "| Campo | Uso en la pantalla |\n|---|---|\n"
        "| `subtotal` | Suma de las líneas |\n"
        "| `shipping` | Envío (gratis al superar el umbral configurado) |\n"
        "| `missing_for_free_shipping` | *«Te faltan B/. XX.XX para envío gratis»* |\n"
        "| `discount` / `coupon_code` | Línea de descuento del cupón aplicado |\n"
        "| `total` | Total a pagar |\n\n"
        "Si el carrito no existe todavía, se crea vacío.\n\n🔒 Requiere token."
    ),
)
async def get_cart(user: dict = Depends(get_current_user)):
    cart = await _get_cart(str(user["_id"]))
    return await build_summary(cart["items"], cart.get("coupon_code"))


@router.post(
    "/items",
    summary="Agregar un producto al carrito",
    description=(
        "Botón *Agregar al carrito*. Si el producto ya estaba en el carrito, **suma** la "
        "cantidad en lugar de duplicar la línea.\n\n"
        "Valida el stock contra la cantidad resultante y devuelve el carrito completo ya "
        "recalculado, para que el frontend refresque el resumen con una sola llamada.\n\n"
        "🔒 Requiere token. **Errores:** `404` producto inexistente · "
        "`409` si se supera el stock disponible."
    ),
    responses={
        404: {"description": "Producto no encontrado"},
        409: {"description": "No puedes seleccionar más de N unidades"},
    },
)
async def add_item(data: CartItemIn, user: dict = Depends(get_current_user)):
    db = get_db()
    product = await db.products.find_one(
        {"_id": parse_object_id(data.product_id, "producto"), "active": True}
    )
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    cart = await _get_cart(str(user["_id"]))
    items = cart["items"]
    existing = next((i for i in items if i["product_id"] == data.product_id), None)
    new_qty = data.quantity + (existing["quantity"] if existing else 0)
    if new_qty > product.get("stock", 0):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No puedes seleccionar más de {product.get('stock', 0)} unidades",
        )
    if existing:
        existing["quantity"] = new_qty
    else:
        items.append({"product_id": data.product_id, "quantity": data.quantity})

    await db.carts.update_one({"user_id": str(user["_id"])}, {"$set": {"items": items}})
    return await build_summary(items, cart.get("coupon_code"))


@router.put(
    "/items/{product_id}",
    summary="Cambiar la cantidad de un producto",
    description=(
        "Fija la cantidad exacta de una línea del carrito (selector `- 1 +`). "
        "A diferencia de `POST /cart/items`, **reemplaza** la cantidad en vez de sumarla.\n\n"
        "Devuelve el carrito recalculado.\n\n"
        "🔒 Requiere token. **Errores:** `404` si el producto no existe o no está en el "
        "carrito · `409` si la cantidad supera el stock."
    ),
    responses={
        404: {"description": "El producto no está en el carrito"},
        409: {"description": "No puedes seleccionar más de N unidades"},
    },
)
async def update_item(
    data: CartItemIn,
    product_id: str = Path(description="ID del producto que ya está en el carrito"),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    product = await db.products.find_one({"_id": parse_object_id(product_id, "producto")})
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    if data.quantity > product.get("stock", 0):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No puedes seleccionar más de {product.get('stock', 0)} unidades",
        )

    cart = await _get_cart(str(user["_id"]))
    items = cart["items"]
    existing = next((i for i in items if i["product_id"] == product_id), None)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El producto no está en el carrito")
    existing["quantity"] = data.quantity

    await db.carts.update_one({"user_id": str(user["_id"])}, {"$set": {"items": items}})
    return await build_summary(items, cart.get("coupon_code"))


@router.delete(
    "/items/{product_id}",
    summary="Quitar un producto del carrito",
    description=(
        "Icono de papelera de la fila. Elimina la línea completa sin importar la cantidad "
        "y devuelve el carrito recalculado. Es idempotente: si el producto ya no estaba, "
        "responde igual sin error.\n\n🔒 Requiere token."
    ),
)
async def remove_item(
    product_id: str = Path(description="ID del producto a quitar del carrito"),
    user: dict = Depends(get_current_user),
):
    cart = await _get_cart(str(user["_id"]))
    items = [i for i in cart["items"] if i["product_id"] != product_id]
    await get_db().carts.update_one({"user_id": str(user["_id"])}, {"$set": {"items": items}})
    return await build_summary(items, cart.get("coupon_code"))


@router.post(
    "/coupon",
    summary="Aplicar un cupón de descuento",
    description=(
        "Aplica un código de descuento al carrito (ej. `TECA10` = 10 %). "
        "El código no distingue mayúsculas.\n\n"
        "**Solo se admite un cupón a la vez:** si ya había uno aplicado, este lo reemplaza "
        "(el aviso *«Si aplicas otro, el cupón actual será reemplazado»*).\n\n"
        "Devuelve el carrito con la línea `discount` y el `total` actualizados.\n\n"
        "🔒 Requiere token. **Errores:** `404` si el cupón no existe o está inactivo."
    ),
    responses={404: {"description": "Cupón inválido o expirado"}},
)
async def apply_coupon(data: CouponApplyIn, user: dict = Depends(get_current_user)):
    """Aplica un cupón (solo uno a la vez; reemplaza el anterior)."""
    db = get_db()
    coupon = await db.coupons.find_one({"code": data.code.upper(), "active": True})
    if coupon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cupón inválido o expirado")
    cart = await _get_cart(str(user["_id"]))
    await db.carts.update_one(
        {"user_id": str(user["_id"])}, {"$set": {"coupon_code": coupon["code"]}}
    )
    return await build_summary(cart["items"], coupon["code"])


@router.delete(
    "/coupon",
    summary="Quitar el cupón aplicado",
    description=(
        "Botón *Eliminar* del recuadro «Código de cupón aplicado». Deja el descuento en 0 "
        "y devuelve el carrito recalculado.\n\n🔒 Requiere token."
    ),
)
async def remove_coupon(user: dict = Depends(get_current_user)):
    cart = await _get_cart(str(user["_id"]))
    await get_db().carts.update_one(
        {"user_id": str(user["_id"])}, {"$set": {"coupon_code": None}}
    )
    return await build_summary(cart["items"], None)
