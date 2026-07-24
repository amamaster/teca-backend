"""Configuración de la aplicación (variables de entorno / .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MongoDB (contenedor Docker local por defecto)
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "teca"

    # JWT
    jwt_secret: str = "cambia-este-secreto-en-produccion"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 horas

    # Reglas de negocio
    shipping_cost: float = 25.00           # costo de envío estándar (B/.)
    free_shipping_threshold: float = 300.00  # monto para envío gratis (B/.)

    # CORS: orígenes del frontend separados por coma
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # En modo dev los tokens de verificación/reseteo se devuelven en la respuesta
    # (no hay servidor de correo). Ponlo en False cuando integres emails reales.
    dev_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
