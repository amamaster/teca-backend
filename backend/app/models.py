"""Esquemas Pydantic (entrada/salida de los endpoints).

Cada modelo lleva título, descripción de campos y ejemplo en español para que
la sección **Schemas** de Swagger sea legible sin leer el código.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ---------------------------------------------------------------- Auth
Role = Literal["admin", "vendedor", "encargado", "soporte", "editor", "finanzas", "cliente"]


class RegisterIn(BaseModel):
    model_config = ConfigDict(
        title="Registro de cliente",
        json_schema_extra={
            "example": {
                "name": "Aldair Gallardo",
                "email": "cliente@teca.com",
                "password": "MiClave123",
                "phone": "6000-0000",
            }
        },
    )

    name: str = Field(min_length=2, max_length=100, title="Nombre", description="Nombre completo del cliente")
    email: EmailStr = Field(title="Correo electrónico", description="Debe ser único en el sistema")
    password: str = Field(min_length=8, max_length=128, title="Contraseña", description="Mínimo 8 caracteres")
    phone: str | None = Field(default=None, title="Teléfono", description="Opcional, para contactar sobre el pedido")


class LoginIn(BaseModel):
    model_config = ConfigDict(
        title="Inicio de sesión",
        json_schema_extra={"example": {"email": "admin@teca.com", "password": "Admin1234!"}},
    )

    email: EmailStr = Field(title="Correo electrónico")
    password: str = Field(title="Contraseña")


class ForgotPasswordIn(BaseModel):
    model_config = ConfigDict(
        title="Solicitud de recuperación",
        json_schema_extra={"example": {"email": "cliente@teca.com"}},
    )

    email: EmailStr = Field(title="Correo electrónico", description="Correo de la cuenta a recuperar")


class ResetPasswordIn(BaseModel):
    model_config = ConfigDict(title="Restablecer contraseña")

    token: str = Field(title="Token de reseteo", description="El token recibido por correo (válido 1 hora)")
    new_password: str = Field(min_length=8, max_length=128, title="Contraseña nueva", description="Mínimo 8 caracteres")


class ChangePasswordIn(BaseModel):
    model_config = ConfigDict(title="Cambio de contraseña")

    current_password: str = Field(title="Contraseña actual")
    new_password: str = Field(min_length=8, max_length=128, title="Contraseña nueva", description="Mínimo 8 caracteres")


class ProfileUpdateIn(BaseModel):
    model_config = ConfigDict(
        title="Edición de perfil",
        json_schema_extra={"example": {"name": "Aldair Gallardo", "phone": "6000-0000"}},
    )

    name: str | None = Field(default=None, min_length=2, max_length=100, title="Nombre")
    phone: str | None = Field(default=None, title="Teléfono")


# ---------------------------------------------------------------- Productos
Category = Literal["sofa", "silla", "mesa", "cama", "lampara", "espejo"]
Material = Literal["madera", "tela", "metal", "vidrio"]


class ProductIn(BaseModel):
    model_config = ConfigDict(
        title="Producto (crear)",
        json_schema_extra={
            "example": {
                "name": "Sofá moderno de sala",
                "description": "Sofá de tres puestos, tapizado en tela resistente.",
                "price": 299.99,
                "category": "sofa",
                "material": "tela",
                "color": "Gris",
                "stock": 7,
                "images": [],
                "dimensions": "200 cm x 85 cm",
                "structure": "Madera",
                "warranty": "6 meses",
                "active": True,
            }
        },
    )

    name: str = Field(min_length=2, max_length=150, title="Nombre", description="Nombre visible en el catálogo")
    description: str = Field(default="", title="Descripción", description="Texto largo de la ficha del producto")
    price: float = Field(gt=0, title="Precio", description="Precio unitario en balboas (B/.)")
    category: Category = Field(title="Categoría", description="Categoría del filtro lateral del catálogo")
    material: Material = Field(title="Material", description="Material principal, usado como filtro")
    color: str | None = Field(default=None, title="Color", description="Ej. «Gris», «Roble»")
    stock: int = Field(ge=0, default=0, title="Stock", description="Unidades disponibles; limita la cantidad que se puede comprar")
    images: list[str] = Field(default=[], title="Imágenes", description="URLs de las vistas del producto (la primera es la principal)")
    dimensions: str | None = Field(default=None, title="Medidas", description="Ej. «200 cm x 85 cm»")
    structure: str | None = Field(default=None, title="Estructura", description="Ej. «Madera»")
    warranty: str | None = Field(default=None, title="Garantía", description="Ej. «6 meses»")
    active: bool = Field(default=True, title="Activo", description="Si es falso, no aparece en el catálogo público")


class ProductUpdateIn(BaseModel):
    model_config = ConfigDict(
        title="Producto (editar)",
        json_schema_extra={"example": {"price": 279.99, "stock": 12}},
    )

    name: str | None = Field(default=None, min_length=2, max_length=150, title="Nombre")
    description: str | None = Field(default=None, title="Descripción")
    price: float | None = Field(default=None, gt=0, title="Precio", description="En balboas (B/.)")
    category: Category | None = Field(default=None, title="Categoría")
    material: Material | None = Field(default=None, title="Material")
    color: str | None = Field(default=None, title="Color")
    stock: int | None = Field(default=None, ge=0, title="Stock", description="Usar para reponer inventario")
    images: list[str] | None = Field(default=None, title="Imágenes")
    dimensions: str | None = Field(default=None, title="Medidas")
    structure: str | None = Field(default=None, title="Estructura")
    warranty: str | None = Field(default=None, title="Garantía")
    active: bool | None = Field(default=None, title="Activo", description="Ponlo en falso para ocultarlo sin borrarlo")


# ---------------------------------------------------------------- Reseñas
class ReviewIn(BaseModel):
    model_config = ConfigDict(
        title="Reseña",
        json_schema_extra={
            "example": {"rating": 5, "comment": "El sofá llegó en perfecto estado y la entrega fue rápida."}
        },
    )

    rating: int = Field(ge=1, le=5, title="Calificación", description="Estrellas, de 1 a 5")
    comment: str = Field(max_length=500, title="Comentario", description="Máximo 500 caracteres")


# ---------------------------------------------------------------- Carrito
class CartItemIn(BaseModel):
    model_config = ConfigDict(
        title="Item del carrito",
        json_schema_extra={"example": {"product_id": "6650f1a2b3c4d5e6f7a8b9c0", "quantity": 1}},
    )

    product_id: str = Field(title="ID del producto", description="Identificador devuelto por el catálogo")
    quantity: int = Field(ge=1, title="Cantidad", description="No puede superar el stock disponible")


class CouponApplyIn(BaseModel):
    model_config = ConfigDict(
        title="Cupón a aplicar",
        json_schema_extra={"example": {"code": "TECA10"}},
    )

    code: str = Field(title="Código", description="No distingue mayúsculas. Ej. «TECA10»")


# ---------------------------------------------------------------- Pedidos
PaymentMethod = Literal["card", "paypal", "bitcoin", "yappy"]
OrderStatus = Literal["confirmado", "en_preparacion", "en_camino", "entregado", "cancelado"]


class ShippingAddressIn(BaseModel):
    model_config = ConfigDict(title="Dirección de envío")

    full_name: str = Field(title="Nombre de quien recibe")
    phone: str = Field(title="Teléfono de contacto")
    province: str = Field(title="Provincia", description="Ej. «Chiriquí»")
    city: str = Field(title="Ciudad o distrito", description="Ej. «David»")
    address_line: str = Field(title="Dirección", description="Calle, casa o edificio")
    reference: str | None = Field(default=None, title="Referencia", description="Punto de referencia para el repartidor")


class CheckoutItemIn(BaseModel):
    model_config = ConfigDict(title="Producto a comprar")

    product_id: str = Field(title="ID del producto")
    quantity: int = Field(ge=1, title="Cantidad")


class CheckoutIn(BaseModel):
    model_config = ConfigDict(
        title="Datos del checkout",
        json_schema_extra={
            "example": {
                "email": "cliente@teca.com",
                "items": [{"product_id": "6650f1a2b3c4d5e6f7a8b9c0", "quantity": 1}],
                "shipping_address": {
                    "full_name": "Aldair Gallardo",
                    "phone": "6000-0000",
                    "province": "Chiriquí",
                    "city": "David",
                    "address_line": "Ave. Álvarez, casa 12",
                    "reference": "Frente al parque",
                },
                "payment_method": "yappy",
                "coupon_code": "TECA10",
                "shipping_method": "envío estándar",
            }
        },
    )

    email: EmailStr = Field(
        title="Correo del comprador",
        description="Obligatorio también para invitados: es con lo que luego consultan su pedido",
    )
    items: list[CheckoutItemIn] = Field(min_length=1, title="Productos", description="Al menos un producto")
    shipping_address: ShippingAddressIn = Field(title="Dirección de envío")
    payment_method: PaymentMethod = Field(
        title="Método de pago",
        description="`card` (Visa/Mastercard), `paypal`, `bitcoin` o `yappy`",
    )
    coupon_code: str | None = Field(default=None, title="Código de cupón", description="Opcional")
    shipping_method: str = Field(default="envío estándar", title="Método de envío")


class OrderStatusUpdateIn(BaseModel):
    model_config = ConfigDict(
        title="Cambio de estado del pedido",
        json_schema_extra={"example": {"status": "en_camino", "tracking_number": "GLE-88420193PA"}},
    )

    status: OrderStatus = Field(
        title="Nuevo estado",
        description="`confirmado`, `en_preparacion`, `en_camino`, `entregado` o `cancelado`",
    )
    tracking_number: str | None = Field(
        default=None, title="Número de guía", description="Guía del courier; se envía al pasar a «en camino»"
    )


class OrderLookupIn(BaseModel):
    model_config = ConfigDict(
        title="Consulta de pedido (invitado)",
        json_schema_extra={"example": {"order_number": "TEC-2026-001", "email": "cliente@teca.com"}},
    )

    order_number: str = Field(title="Número de pedido", description="Ej. «TEC-2026-001»")
    email: EmailStr = Field(title="Correo del pedido", description="Debe coincidir con el usado al comprar")


# ---------------------------------------------------------------- Cuenta
class AddressIn(BaseModel):
    model_config = ConfigDict(
        title="Dirección guardada",
        json_schema_extra={
            "example": {
                "full_name": "Aldair Gallardo",
                "phone": "6000-0000",
                "province": "Chiriquí",
                "city": "David",
                "address_line": "Ave. Álvarez, casa 12",
                "reference": "Frente al parque",
                "is_default": True,
            }
        },
    )

    full_name: str = Field(title="Nombre de quien recibe")
    phone: str = Field(title="Teléfono de contacto")
    province: str = Field(title="Provincia")
    city: str = Field(title="Ciudad o distrito")
    address_line: str = Field(title="Dirección")
    reference: str | None = Field(default=None, title="Referencia")
    is_default: bool = Field(
        default=False, title="Predeterminada", description="Al marcarla, las demás dejan de serlo"
    )


class PaymentMethodIn(BaseModel):
    model_config = ConfigDict(
        title="Método de pago guardado",
        json_schema_extra={
            "example": {
                "type": "visa",
                "label": "Visa terminada en 4821",
                "holder_name": "Aldair Gallardo",
                "expires": "08/2028",
                "is_default": True,
            }
        },
    )

    type: Literal["visa", "mastercard", "paypal"] = Field(title="Tipo")
    label: str = Field(
        title="Etiqueta",
        description="Texto que ve el usuario. Ej. «Visa terminada en 4821». Nunca el número completo",
    )
    holder_name: str | None = Field(default=None, title="Titular")
    expires: str | None = Field(default=None, title="Vencimiento", description="Ej. «08/2028»")
    email: EmailStr | None = Field(default=None, title="Correo de PayPal", description="Solo para tipo `paypal`")
    is_default: bool = Field(default=False, title="Principal", description="Al marcarlo, los demás dejan de serlo")


ReturnStatus = Literal["en_revision", "aprobado", "rechazado", "completado"]


class ReturnIn(BaseModel):
    model_config = ConfigDict(
        title="Solicitud de devolución",
        json_schema_extra={
            "example": {
                "order_number": "TEC-2026-001",
                "product_id": "6650f1a2b3c4d5e6f7a8b9c0",
                "reason": "El producto llegó dañado en una esquina.",
            }
        },
    )

    order_number: str = Field(title="Número de pedido", description="Debe ser un pedido propio")
    product_id: str = Field(title="ID del producto", description="Debe pertenecer a ese pedido")
    reason: str = Field(min_length=5, max_length=500, title="Motivo", description="Ej. «Producto dañado»")


class ReturnStatusUpdateIn(BaseModel):
    model_config = ConfigDict(
        title="Resolución de la devolución",
        json_schema_extra={"example": {"status": "aprobado"}},
    )

    status: ReturnStatus = Field(
        title="Nuevo estado",
        description="`en_revision`, `aprobado`, `rechazado` o `completado`",
    )


# ---------------------------------------------------------------- Admin
class InternalUserIn(BaseModel):
    model_config = ConfigDict(
        title="Usuario interno (crear)",
        json_schema_extra={
            "example": {
                "name": "Usuario A",
                "email": "usuarioa@teca.com",
                "description": "Encargado de inventario",
                "phone": "6000-0000",
                "role": "encargado",
                "temp_password": "Temporal123",
                "must_change_password": True,
                "active": True,
            }
        },
    )

    name: str = Field(min_length=2, max_length=100, title="Nombre")
    email: EmailStr = Field(title="Correo electrónico", description="Debe ser único")
    description: str | None = Field(default=None, title="Descripción", description="Nota interna sobre el usuario")
    phone: str | None = Field(default=None, title="Teléfono")
    role: Literal["admin", "vendedor", "encargado", "soporte", "editor", "finanzas"] = Field(
        title="Rol asignado", description="Define a qué módulos del panel tiene acceso"
    )
    temp_password: str = Field(
        min_length=8, max_length=128, title="Contraseña temporal", description="Mínimo 8 caracteres"
    )
    must_change_password: bool = Field(
        default=True,
        title="Debe cambiar la contraseña",
        description="Obliga a cambiarla en el primer ingreso",
    )
    active: bool = Field(default=True, title="Activo", description="Si es falso, no puede iniciar sesión")


class InternalUserUpdateIn(BaseModel):
    model_config = ConfigDict(
        title="Usuario interno (editar)",
        json_schema_extra={"example": {"role": "soporte", "active": False}},
    )

    name: str | None = Field(default=None, title="Nombre")
    email: EmailStr | None = Field(default=None, title="Correo electrónico")
    description: str | None = Field(default=None, title="Descripción")
    phone: str | None = Field(default=None, title="Teléfono")
    role: Literal["admin", "vendedor", "encargado", "soporte", "editor", "finanzas"] | None = Field(
        default=None, title="Rol asignado"
    )
    active: bool | None = Field(
        default=None, title="Activo", description="Switch Activo/Inactivo de la tabla de usuarios"
    )


class CouponIn(BaseModel):
    model_config = ConfigDict(
        title="Cupón",
        json_schema_extra={"example": {"code": "TECA10", "discount_percent": 10, "active": True}},
    )

    code: str = Field(min_length=3, max_length=20, title="Código", description="Se guarda en mayúsculas y debe ser único")
    discount_percent: float = Field(gt=0, le=100, title="Descuento (%)", description="Porcentaje sobre el subtotal")
    active: bool = Field(default=True, title="Activo", description="Ponlo en falso para desactivarlo sin borrarlo")
