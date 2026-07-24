"""Autenticación: hashing de contraseñas, JWT y dependencias de rol."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .database import get_db

# Roles internos del panel de administración
INTERNAL_ROLES = {"admin", "vendedor", "encargado", "soporte", "editor", "finanzas"}
CUSTOMER_ROLE = "cliente"

_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def parse_object_id(value: str, entity: str = "recurso") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{entity} no encontrado")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Devuelve el usuario autenticado o lanza 401."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")

    user = await get_db().users.find_one({"_id": parse_object_id(payload["sub"], "usuario")})
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no existe")
    if not user.get("active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Como get_current_user pero devuelve None si no hay token (checkout invitado)."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_roles(*roles: str):
    """Dependencia que exige que el usuario tenga alguno de los roles dados."""

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permisos para esta acción")
        return user

    return checker


# Atajos comunes
require_admin = require_roles("admin")
require_staff = require_roles(*INTERNAL_ROLES)
require_product_editor = require_roles("admin", "editor", "encargado")
require_finance = require_roles("admin", "finanzas")
require_sales = require_roles("admin", "vendedor", "encargado", "soporte")


async def log_audit(actor: dict | None, action: str, entity: str, detail: str = "") -> None:
    """Registra una acción administrativa en la colección de auditoría."""
    await get_db().audit_log.insert_one(
        {
            "actor_id": str(actor["_id"]) if actor else None,
            "actor_name": actor.get("name") if actor else "sistema",
            "action": action,
            "entity": entity,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc),
        }
    )
