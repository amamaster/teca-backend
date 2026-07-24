"""Catálogo público de productos: filtros, orden, búsqueda, paginación y reseñas."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..database import get_db, serialize
from ..models import ReviewIn
from ..security import get_current_user, parse_object_id

router = APIRouter(prefix="/products", tags=["Catálogo"])

SORT_OPTIONS = {
    "price_asc": [("price", 1)],       # Precio de menor a mayor
    "price_desc": [("price", -1)],     # Precio de mayor a menor
    "newest": [("created_at", -1)],    # Más nuevos
    "relevance": [("rating_avg", -1), ("rating_count", -1)],  # Más relevantes
}


@router.get(
    "",
    summary="Listar productos del catálogo",
    description=(
        "Alimenta la pantalla **Catálogo de productos** con todos sus filtros de la barra "
        "lateral. Solo devuelve productos activos.\n\n"
        "**Filtros disponibles**\n"
        "- `search`: búsqueda de texto en nombre y descripción (la lupa del header).\n"
        "- `category` y `material`: aceptan **varios valores separados por coma** "
        "(`?category=sofa,silla`), tal como los checkboxes del filtro lateral.\n"
        "- `min_price` / `max_price`: el deslizador de precio.\n\n"
        "**Ordenamiento** (`sort`), igual que el desplegable *Ordenar por*:\n"
        "| Valor | Significado |\n|---|---|\n"
        "| `price_asc` | Precio de menor a mayor |\n"
        "| `price_desc` | Precio de mayor a menor |\n"
        "| `newest` | Más nuevos |\n"
        "| `relevance` | Más relevantes (mejor calificados) — por defecto |\n\n"
        "**Respuesta:** `items`, `total`, `page`, `page_size` y `total_pages`, "
        "para pintar el texto *«Mostrando 1-8 de 24 productos»* y la paginación."
    ),
)
async def list_products(
    search: str | None = Query(None, description="Búsqueda por texto en nombre y descripción"),
    category: str | None = Query(
        None, description="Categorías separadas por coma: sofa, silla, mesa, cama, lampara, espejo"
    ),
    material: str | None = Query(
        None, description="Materiales separados por coma: madera, tela, metal, vidrio"
    ),
    min_price: float | None = Query(None, ge=0, description="Precio mínimo en balboas (B/.)"),
    max_price: float | None = Query(None, ge=0, description="Precio máximo en balboas (B/.)"),
    sort: Literal["price_asc", "price_desc", "newest", "relevance"] = Query(
        "relevance",
        description="Orden: price_asc (menor a mayor), price_desc (mayor a menor), newest (más nuevos), relevance (más relevantes)",
    ),
    page: int = Query(1, ge=1, description="Número de página, empezando en 1"),
    page_size: int = Query(8, ge=1, le=50, description="Productos por página (máx. 50)"),
):
    db = get_db()
    query: dict = {"active": True}
    if search:
        query["$text"] = {"$search": search}
    if category:
        query["category"] = {"$in": [c.strip() for c in category.split(",")]}
    if material:
        query["material"] = {"$in": [m.strip() for m in material.split(",")]}
    if min_price is not None or max_price is not None:
        price: dict = {}
        if min_price is not None:
            price["$gte"] = min_price
        if max_price is not None:
            price["$lte"] = max_price
        query["price"] = price

    total = await db.products.count_documents(query)
    cursor = (
        db.products.find(query)
        .sort(SORT_OPTIONS[sort])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(doc) async for doc in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get(
    "/{product_id}",
    summary="Detalle de un producto",
    description=(
        "Datos completos para la ficha del producto: precio, descripción, material, color, "
        "stock, galería de imágenes (`images`) y las viñetas de *Detalles del producto* "
        "(`dimensions`, `structure`, `warranty`), además de `rating_avg` y `rating_count`.\n\n"
        "El campo `stock` es el que limita el selector de cantidad "
        "(*«No puedes seleccionar más de N unidades»*).\n\n"
        "**Errores:** `404` si no existe o está inactivo."
    ),
    responses={404: {"description": "Producto no encontrado"}},
)
async def get_product(
    product_id: str = Path(description="ID del producto devuelto por el catálogo"),
):
    product = await get_db().products.find_one(
        {"_id": parse_object_id(product_id, "producto"), "active": True}
    )
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return serialize(product)


# ---------------------------------------------------------------- Reseñas
@router.get(
    "/{product_id}/reviews",
    summary="Reseñas de un producto",
    description=(
        "Bloque **Reseñas del producto**. Devuelve:\n\n"
        "- `items`: reseñas paginadas (más recientes primero), cada una con nombre del "
        "autor, comentario, fecha y `verified_purchase` para la etiqueta *Compra verificada*.\n"
        "- `average`: promedio general (el número grande, ej. `4.2`).\n"
        "- `distribution`: cantidad de reseñas por estrella (`{\"5\": 22, \"4\": 10, ...}`) "
        "para dibujar las barras 5★–1★.\n"
        "- `total`: total de reseñas (*«Ver todas las reseñas (11)»*)."
    ),
)
async def list_reviews(
    product_id: str = Path(description="ID del producto"),
    page: int = Query(1, ge=1, description="Número de página, empezando en 1"),
    page_size: int = Query(10, ge=1, le=50, description="Reseñas por página (máx. 50)"),
):
    db = get_db()
    oid = parse_object_id(product_id, "producto")
    query = {"product_id": str(oid)}
    total = await db.reviews.count_documents(query)
    cursor = db.reviews.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = [serialize(doc) async for doc in cursor]

    # Distribución de calificaciones (para las barras 5★..1★)
    distribution = {str(i): 0 for i in range(1, 6)}
    async for row in db.reviews.aggregate(
        [{"$match": query}, {"$group": {"_id": "$rating", "count": {"$sum": 1}}}]
    ):
        distribution[str(row["_id"])] = row["count"]

    product = await db.products.find_one({"_id": oid})
    return {
        "items": items,
        "total": total,
        "page": page,
        "average": product.get("rating_avg", 0) if product else 0,
        "distribution": distribution,
    }


@router.post(
    "/{product_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    summary="Escribir una reseña",
    description=(
        "Botón *Escribir mi reseña*. Recibe `rating` (1 a 5) y `comment` (máx. 500 "
        "caracteres).\n\n"
        "La etiqueta **Compra verificada** se calcula sola: se marca `verified_purchase` "
        "en `true` si el usuario tiene un pedido **entregado** que incluye ese producto. "
        "Tras guardar, recalcula el promedio y el conteo del producto.\n\n"
        "🔒 Requiere token. **Errores:** `404` producto inexistente · "
        "`409` si ya reseñaste este producto (una reseña por usuario)."
    ),
    responses={
        404: {"description": "Producto no encontrado"},
        409: {"description": "Ya publicaste una reseña de este producto"},
    },
)
async def create_review(
    data: ReviewIn,
    product_id: str = Path(description="ID del producto a reseñar"),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    oid = parse_object_id(product_id, "producto")
    if await db.products.find_one({"_id": oid}) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    if await db.reviews.find_one({"product_id": str(oid), "user_id": str(user["_id"])}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya publicaste una reseña de este producto")

    # "Compra verificada": el usuario tiene un pedido entregado con este producto
    verified = (
        await db.orders.find_one(
            {
                "user_id": str(user["_id"]),
                "status": "entregado",
                "items.product_id": str(oid),
            }
        )
        is not None
    )

    review = {
        "product_id": str(oid),
        "user_id": str(user["_id"]),
        "user_name": user["name"],
        "rating": data.rating,
        "comment": data.comment,
        "verified_purchase": verified,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.reviews.insert_one(review)

    # Recalcular promedio del producto
    agg = [
        {"$match": {"product_id": str(oid)}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    stats = await db.reviews.aggregate(agg).to_list(1)
    if stats:
        await db.products.update_one(
            {"_id": oid},
            {"$set": {"rating_avg": round(stats[0]["avg"], 1), "rating_count": stats[0]["count"]}},
        )

    review["_id"] = result.inserted_id
    return serialize(review)
