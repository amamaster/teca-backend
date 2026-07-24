"""Carga datos de ejemplo en MongoDB (productos del mockup, admin y cupón TECA10).

Uso:  python seed.py
Es idempotente: no duplica datos si ya existen.
"""
import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.security import hash_password

PRODUCTS = [
    {"name": "Silla moderna", "price": 29.99, "category": "silla", "material": "madera", "color": "Gris", "stock": 15},
    {"name": "Lámpara de pie", "price": 49.99, "category": "lampara", "material": "metal", "color": "Blanco", "stock": 20},
    {"name": "Espejo redondo", "price": 69.99, "category": "espejo", "material": "vidrio", "color": "Plateado", "stock": 10},
    {"name": "Mesa auxiliar", "price": 149.99, "category": "mesa", "material": "madera", "color": "Roble", "stock": 8},
    {"name": "Mesa de comedor", "price": 199.99, "category": "mesa", "material": "madera", "color": "Nogal", "stock": 5},
    {"name": "Sofá moderno de sala", "price": 299.99, "category": "sofa", "material": "tela", "color": "Gris",
     "stock": 7, "dimensions": "200 cm x 85 cm", "structure": "Madera", "warranty": "6 meses"},
    {"name": "Cama queen", "price": 349.99, "category": "cama", "material": "madera", "color": "Beige", "stock": 4},
    {"name": "Sofá cama", "price": 399.99, "category": "sofa", "material": "tela", "color": "Azul", "stock": 3},
]


async def main() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db]

    for product in PRODUCTS:
        exists = await db.products.find_one({"name": product["name"]})
        if exists:
            continue
        await db.products.insert_one(
            product
            | {
                "description": f"{product['name']} de alta calidad, fabricado con materiales duraderos.",
                "images": [],
                "active": True,
                "rating_avg": 0,
                "rating_count": 0,
                "created_at": datetime.now(timezone.utc),
            }
        )
        print(f"Producto creado: {product['name']}")

    if not await db.users.find_one({"email": "admin@teca.com"}):
        await db.users.insert_one(
            {
                "name": "Administrador",
                "email": "admin@teca.com",
                "password_hash": hash_password("Admin1234!"),
                "role": "admin",
                "active": True,
                "email_verified": True,
                "must_change_password": False,
                "created_at": datetime.now(timezone.utc),
            }
        )
        print("Admin creado: admin@teca.com / Admin1234!")

    if not await db.coupons.find_one({"code": "TECA10"}):
        await db.coupons.insert_one({"code": "TECA10", "discount_percent": 10, "active": True})
        print("Cupón creado: TECA10 (10%)")

    client.close()
    print("Seed completado.")


if __name__ == "__main__":
    asyncio.run(main())
