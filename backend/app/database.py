"""Conexión a MongoDB con Motor (async) y creación de índices."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db]
    await _create_indexes(_db)


async def disconnect() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    assert _db is not None, "La base de datos no está conectada"
    return _db


async def _create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.users.create_index("email", unique=True)
    await db.products.create_index([("name", "text"), ("description", "text")])
    await db.products.create_index("category")
    await db.products.create_index("material")
    await db.products.create_index("price")
    await db.orders.create_index("order_number", unique=True)
    await db.orders.create_index("email")
    await db.reviews.create_index([("product_id", 1), ("user_id", 1)])
    await db.coupons.create_index("code", unique=True)
    await db.returns.create_index("return_number")
    await db.carts.create_index("user_id", unique=True)


def serialize(doc: dict | None) -> dict | None:
    """Convierte _id (ObjectId) en id (str) para las respuestas JSON."""
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    doc.pop("password_hash", None)  # nunca exponer hashes
    return doc
