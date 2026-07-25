"""Subida de imágenes de productos.

Los archivos se guardan en la carpeta `static/products/` y en la base de datos
solo se almacena **la ruta** (ej. `/static/products/a1b2c3.jpg`), nunca el archivo.

Flujo desde el formulario de creación de productos:

    1. El usuario selecciona las imágenes  →  POST /admin/uploads/images
    2. El backend devuelve las rutas       →  ["/static/products/a1b2.jpg", ...]
    3. Esas rutas se envían en el campo `images` al crear o editar el producto
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from ..config import get_settings
from ..security import log_audit, require_product_editor

router = APIRouter(prefix="/admin/uploads", tags=["Imágenes"])

# Solo formatos de imagen raster. El SVG queda fuera a propósito: puede contener
# JavaScript y se serviría desde el mismo dominio de la API (XSS almacenado).
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Firmas de los primeros bytes de cada formato, para verificar que el archivo
# es realmente una imagen y no un ejecutable renombrado.
FIRMAS = (
    b"\xff\xd8\xff",       # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"GIF87a",             # GIF
    b"GIF89a",
    b"RIFF",               # WEBP (RIFF....WEBP)
)


def carpeta_destino() -> Path:
    """Carpeta donde se guardan las imágenes, creándola si no existe."""
    ruta = Path(__file__).resolve().parents[2] / get_settings().upload_dir
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _validar_nombre(filename: str) -> str:
    """Devuelve la extensión validada del archivo."""
    extension = Path(filename or "").suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        permitidas = ", ".join(sorted(EXTENSIONES_PERMITIDAS))
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Formato no permitido en «{filename}». Solo se aceptan: {permitidas}",
        )
    return extension


async def _guardar(archivo: UploadFile, limite_bytes: int) -> str:
    """Guarda un archivo en disco y devuelve su ruta pública."""
    extension = _validar_nombre(archivo.filename)

    if archivo.content_type and not archivo.content_type.startswith("image/"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{archivo.filename}» no es una imagen",
        )

    # Nombre único: evita colisiones y que alguien sobrescriba archivos ajenos
    # usando nombres con rutas (../) o repetidos.
    destino = carpeta_destino() / f"{uuid.uuid4().hex}{extension}"

    escrito = 0
    primer_bloque = True
    try:
        with destino.open("wb") as salida:
            # Se escribe por bloques para no cargar archivos grandes en memoria
            while bloque := await archivo.read(1024 * 1024):
                if primer_bloque:
                    if not bloque.startswith(FIRMAS):
                        raise HTTPException(
                            status.HTTP_400_BAD_REQUEST,
                            f"El contenido de «{archivo.filename}» no es una imagen válida",
                        )
                    primer_bloque = False

                escrito += len(bloque)
                if escrito > limite_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"«{archivo.filename}» supera el máximo de "
                        f"{get_settings().max_image_mb} MB",
                    )
                salida.write(bloque)
    except Exception:
        destino.unlink(missing_ok=True)  # no dejar archivos a medias
        raise

    if escrito == 0:
        destino.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{archivo.filename}» está vacío")

    return f"/{get_settings().upload_dir}/{destino.name}"


@router.post(
    "/images",
    status_code=status.HTTP_201_CREATED,
    summary="Subir imágenes de un producto",
    description=(
        "Sube una o varias imágenes y devuelve **las rutas** con las que se guardan.\n\n"
        "Este es el endpoint que usa el formulario *Nuevo producto*: primero se suben "
        "los archivos y después esas rutas se envían en el campo `images` de "
        "`POST /admin/products`.\n\n"
        "**Cómo enviarlo:** con `multipart/form-data`, no con JSON. El campo debe "
        "llamarse `files` y puede repetirse para mandar varias imágenes a la vez.\n\n"
        "**Respuesta:**\n"
        "```json\n"
        '{\n  "images": ["/static/products/a1b2c3.jpg", "/static/products/d4e5f6.png"]\n}\n'
        "```\n\n"
        "El frontend arma la dirección completa anteponiendo la URL de la API: "
        "`http://localhost:8000/static/products/a1b2c3.jpg`.\n\n"
        "**Validaciones:** solo `.jpg`, `.jpeg`, `.png`, `.webp` y `.gif`; se verifica "
        "que el contenido sea realmente una imagen; máximo 5 MB por archivo.\n\n"
        "🔒 Roles: **admin**, **editor**, **encargado**."
    ),
    responses={
        400: {"description": "Formato no permitido o el archivo no es una imagen"},
        413: {"description": "La imagen supera el tamaño máximo"},
    },
)
async def subir_imagenes(
    files: list[UploadFile] = File(description="Una o varias imágenes del producto"),
    actor: dict = Depends(require_product_editor),
):
    settings = get_settings()

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se envió ninguna imagen")
    if len(files) > settings.max_images_per_upload:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Máximo {settings.max_images_per_upload} imágenes por vez",
        )

    limite = int(settings.max_image_mb * 1024 * 1024)
    rutas: list[str] = []
    try:
        for archivo in files:
            rutas.append(await _guardar(archivo, limite))
    except Exception:
        # Si una falla, se borran las que ya se habían guardado en esta petición
        for ruta in rutas:
            eliminar_archivo(ruta)
        raise

    await log_audit(actor, "subir", "imagen", f"{len(rutas)} archivo(s)")
    return {"images": rutas}


def eliminar_archivo(ruta: str) -> bool:
    """Borra del disco la imagen correspondiente a una ruta guardada.

    Solo actúa sobre archivos que estén dentro de la carpeta de subidas, para que
    una ruta manipulada (`/static/products/../../app/main.py`) no pueda borrar
    nada fuera de ella.
    """
    if not ruta:
        return False
    carpeta = carpeta_destino()
    try:
        archivo = (carpeta / Path(ruta).name).resolve()
        archivo.relative_to(carpeta.resolve())  # lanza ValueError si se sale
    except (ValueError, OSError):
        return False
    if archivo.is_file():
        archivo.unlink(missing_ok=True)
        return True
    return False


@router.delete(
    "/images",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una imagen subida",
    description=(
        "Borra del disco una imagen que ya no se usa. Se envía la ruta tal como la "
        "devolvió la subida:\n\n"
        "```\nDELETE /admin/uploads/images?path=/static/products/a1b2c3.jpg\n```\n\n"
        "Útil cuando el usuario quita una imagen del formulario antes de guardar. "
        "Si el archivo ya no existe responde igual, sin error.\n\n"
        "Al eliminar un producto sus imágenes se borran solas, no hace falta llamar aquí.\n\n"
        "🔒 Roles: **admin**, **editor**, **encargado**."
    ),
)
async def eliminar_imagen(
    path: str = Query(description="Ruta de la imagen. Ej. «/static/products/a1b2c3.jpg»"),
    actor: dict = Depends(require_product_editor),
):
    if eliminar_archivo(path):
        await log_audit(actor, "eliminar", "imagen", Path(path).name)
