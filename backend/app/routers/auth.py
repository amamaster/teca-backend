"""Autenticación de clientes: registro, login, verificación de correo y contraseña."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status

from ..config import get_settings
from ..database import get_db, serialize
from ..models import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    ProfileUpdateIn,
    RegisterIn,
    ResetPasswordIn,
)
from ..security import (
    CUSTOMER_ROLE,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un cliente nuevo",
    description=(
        "Crea una cuenta de cliente con rol `cliente` y correo **sin verificar**.\n\n"
        "Genera un token de verificación que en producción se enviaría por correo; "
        "con `DEV_MODE=true` se devuelve en la respuesta (`verification_token`) para "
        "poder probar el flujo sin servidor de correo.\n\n"
        "**Errores:** `409` si el correo ya está registrado."
    ),
    responses={409: {"description": "El correo ya está registrado"}},
)
async def register(data: RegisterIn):
    db = get_db()
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya está registrado")

    verification_token = secrets.token_urlsafe(32)
    result = await db.users.insert_one(
        {
            "name": data.name,
            "email": data.email,
            "phone": data.phone,
            "password_hash": hash_password(data.password),
            "role": CUSTOMER_ROLE,
            "active": True,
            "email_verified": False,
            "verification_token": verification_token,
            "must_change_password": False,
            "created_at": datetime.now(timezone.utc),
        }
    )
    response: dict = {
        "id": str(result.inserted_id),
        "message": "Usuario registrado. Verifica tu correo para continuar.",
    }
    if get_settings().dev_mode:
        # En producción este token se envía por correo, no en la respuesta
        response["verification_token"] = verification_token
    return response


@router.get(
    "/verify-email/{token}",
    summary="Verificar el correo electrónico",
    description=(
        "Marca la cuenta como verificada usando el token recibido en el registro. "
        "Corresponde a la pantalla *«Verifica tu correo para continuar»*.\n\n"
        "**Errores:** `400` si el token es inválido o ya fue usado."
    ),
    responses={400: {"description": "Token de verificación inválido"}},
)
async def verify_email(
    token: str = Path(description="Token de verificación recibido al registrarse"),
):
    db = get_db()
    user = await db.users.find_one({"verification_token": token})
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token de verificación inválido")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"verification_token": ""}},
    )
    return {"message": "Tu correo se ha verificado con éxito"}


@router.post(
    "/login",
    summary="Iniciar sesión y obtener el token JWT",
    description=(
        "Valida correo y contraseña y devuelve:\n\n"
        "- `access_token`: JWT para el header `Authorization: Bearer <token>`.\n"
        "- `must_change_password`: `true` cuando es un usuario interno con contraseña "
        "temporal, para que el frontend lo obligue a cambiarla en el primer ingreso.\n"
        "- `user`: datos básicos (id, nombre, correo, rol, correo verificado).\n\n"
        "Sirve tanto para clientes como para usuarios internos del panel; el rol viene "
        "dentro del token y en `user.role`.\n\n"
        "**Errores:** `401` credenciales incorrectas · `403` cuenta inactiva."
    ),
    responses={
        401: {"description": "Correo o contraseña incorrectos"},
        403: {"description": "La cuenta está inactiva"},
    },
)
async def login(data: LoginIn):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    if user is None or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    if not user.get("active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu cuenta está inactiva")

    return {
        "access_token": create_token(str(user["_id"]), user["role"]),
        "token_type": "bearer",
        "must_change_password": user.get("must_change_password", False),
        "user": serialize(
            {k: user[k] for k in ("_id", "name", "email", "role", "email_verified") if k in user}
        ),
    }


@router.post(
    "/forgot-password",
    summary="Solicitar recuperación de contraseña",
    description=(
        "Pantalla *«¿Olvidaste tu contraseña?»*. Genera un token de reseteo válido por "
        "**1 hora**.\n\n"
        "Por seguridad responde siempre el mismo mensaje, exista o no el correo, para no "
        "revelar qué cuentas están registradas. Con `DEV_MODE=true` se incluye el "
        "`reset_token` en la respuesta para poder probar el flujo."
    ),
)
async def forgot_password(data: ForgotPasswordIn):
    db = get_db()
    user = await db.users.find_one({"email": data.email})
    # Respuesta idéntica exista o no el correo (no revelar cuentas)
    response = {"message": "Si el correo existe, se enviaron instrucciones de recuperación"}
    if user:
        reset_token = secrets.token_urlsafe(32)
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "reset_token": reset_token,
                    "reset_expires": datetime.now(timezone.utc) + timedelta(hours=1),
                }
            },
        )
        if get_settings().dev_mode:
            response["reset_token"] = reset_token
    return response


@router.post(
    "/reset-password",
    summary="Restablecer la contraseña con el token",
    description=(
        "Define una contraseña nueva (mínimo 8 caracteres) usando el token enviado por "
        "correo. El token se invalida tras usarse.\n\n"
        "**Errores:** `400` si el token es inválido o pasó más de 1 hora."
    ),
    responses={400: {"description": "Token inválido o expirado"}},
)
async def reset_password(data: ResetPasswordIn):
    db = get_db()
    user = await db.users.find_one({"reset_token": data.token})
    if user is None or user.get("reset_expires", datetime.min.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token inválido o expirado")
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hash_password(data.new_password), "must_change_password": False},
            "$unset": {"reset_token": "", "reset_expires": ""},
        },
    )
    return {"message": "Contraseña actualizada correctamente"}


@router.post(
    "/change-password",
    summary="Cambiar la contraseña estando autenticado",
    description=(
        "Requiere la contraseña actual. También es el endpoint que usa el usuario interno "
        "para reemplazar su contraseña temporal (deja `must_change_password` en `false`).\n\n"
        "🔒 Requiere token. **Errores:** `400` si la contraseña actual no coincide."
    ),
    responses={400: {"description": "La contraseña actual es incorrecta"}},
)
async def change_password(data: ChangePasswordIn, user: dict = Depends(get_current_user)):
    if not verify_password(data.current_password, user.get("password_hash", "")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual es incorrecta")
    await get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(data.new_password), "must_change_password": False}},
    )
    return {"message": "Contraseña actualizada correctamente"}


@router.get(
    "/me",
    summary="Ver mi perfil",
    description=(
        "Datos del usuario dueño del token (pantalla *Mi cuenta*). "
        "Nunca incluye el hash de la contraseña.\n\n🔒 Requiere token."
    ),
)
async def me(user: dict = Depends(get_current_user)):
    return serialize(user)


@router.patch(
    "/me",
    summary="Editar mi perfil",
    description=(
        "Actualiza nombre y/o teléfono. Los campos omitidos o nulos se dejan intactos "
        "(actualización parcial).\n\n🔒 Requiere token."
    ),
)
async def update_profile(data: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    updates = data.model_dump(exclude_none=True)
    if updates:
        await get_db().users.update_one({"_id": user["_id"]}, {"$set": updates})
    return serialize(await get_db().users.find_one({"_id": user["_id"]}))
