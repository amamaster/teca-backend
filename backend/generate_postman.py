"""Genera la colección de Postman a partir de la especificación OpenAPI.

Uso:  python generate_postman.py

Crea dos archivos en la carpeta postman/:
  - TECA.postman_collection.json   → todas las peticiones, agrupadas por módulo
  - TECA.postman_environment.json  → las variables (baseUrl, token, ids)

La colección guarda el token automáticamente al hacer login, así no hay que
copiarlo y pegarlo en cada petición.

Como se genera desde el código, basta con volver a ejecutar este script cuando
se agregue o cambie un endpoint para tener la colección al día.
"""
import json
import re
from pathlib import Path
from typing import Any

from app.main import app

DESTINO = Path(__file__).parent / "postman"

# Script que se ejecuta tras el login para guardar el token automáticamente
GUARDAR_TOKEN = [
    "// Guarda el token para que el resto de peticiones lo usen solas",
    "if (pm.response.code === 200) {",
    "    const datos = pm.response.json();",
    "    if (datos.access_token) {",
    "        pm.collectionVariables.set('token', datos.access_token);",
    "        console.log('Token guardado. Rol: ' + datos.user.role);",
    "    }",
    "}",
]

# Script que guarda el número de pedido tras el checkout
GUARDAR_PEDIDO = [
    "// Guarda el número de pedido para usarlo en las siguientes peticiones",
    "if (pm.response.code === 201) {",
    "    const pedido = pm.response.json();",
    "    pm.collectionVariables.set('orderNumber', pedido.order_number);",
    "    console.log('Pedido creado: ' + pedido.order_number);",
    "}",
]

# Script que guarda el id del primer producto del catálogo. Así las peticiones
# del carrito y del checkout funcionan sin tener que copiar ids a mano.
GUARDAR_PRODUCTO = [
    "// Guarda el id del primer producto para las peticiones que lo necesiten",
    "if (pm.response.code === 200) {",
    "    const datos = pm.response.json();",
    "    if (datos.items && datos.items.length > 0) {",
    "        pm.collectionVariables.set('productId', datos.items[0].id);",
    "        console.log('productId guardado: ' + datos.items[0].name);",
    "    }",
    "}",
]

# El id de ejemplo de los esquemas se reemplaza por la variable, para que las
# peticiones del carrito y del checkout funcionen apenas se lista el catálogo.
ID_DE_EJEMPLO = "6650f1a2b3c4d5e6f7a8b9c0"


def resolver_ref(spec: dict, esquema: dict) -> dict:
    """Sigue una referencia $ref hasta el esquema real."""
    ref = esquema.get("$ref")
    if not ref:
        return esquema
    nombre = ref.rsplit("/", 1)[1]
    return spec.get("components", {}).get("schemas", {}).get(nombre, {})


def cuerpo_de_archivos(spec: dict, operacion: dict) -> dict | None:
    """Arma el cuerpo tipo formulario para los endpoints que reciben archivos.

    Postman muestra un selector de archivo cuando el campo es de tipo `file`,
    así se pueden elegir las imágenes desde el explorador.
    """
    contenido = operacion.get("requestBody", {}).get("content", {}).get("multipart/form-data")
    if not contenido:
        return None

    esquema = resolver_ref(spec, contenido.get("schema", {}))
    campos = []
    for nombre, propiedad in esquema.get("properties", {}).items():
        # Un arreglo de binarios significa "varios archivos"
        es_lista = propiedad.get("type") == "array"
        interno = propiedad.get("items", {}) if es_lista else propiedad
        if interno.get("format") == "binary":
            campos.append(
                {
                    "key": nombre,
                    "type": "file",
                    "src": [],
                    "description": limpiar(propiedad.get("description", ""))
                    + (" (puedes elegir varios archivos)" if es_lista else ""),
                }
            )
        else:
            campos.append({"key": nombre, "type": "text", "value": ""})

    return {"mode": "formdata", "formdata": campos} if campos else None


def ejemplo_de_cuerpo(spec: dict, operacion: dict) -> str | None:
    """Devuelve el JSON de ejemplo del cuerpo de la petición, si lo hay."""
    contenido = operacion.get("requestBody", {}).get("content", {}).get("application/json")
    if not contenido:
        return None

    esquema = resolver_ref(spec, contenido.get("schema", {}))
    ejemplo = esquema.get("example")

    if ejemplo is None:
        # Sin ejemplo definido: se arma uno con los campos obligatorios
        propiedades = esquema.get("properties", {})
        obligatorios = esquema.get("required", list(propiedades))
        ejemplo = {campo: "" for campo in propiedades if campo in obligatorios}

    crudo = json.dumps(ejemplo, indent=2, ensure_ascii=False)
    return crudo.replace(ID_DE_EJEMPLO, "{{productId}}")


def limpiar(texto: str) -> str:
    """Quita el markdown de las descripciones para que se lean bien en Postman."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)   # negritas
    texto = re.sub(r"`(.+?)`", r"\1", texto)         # código
    return texto.strip()


def construir_url(ruta: str, parametros: list[dict]) -> dict:
    """Arma el objeto URL de Postman, con los parámetros de ruta y de consulta."""
    # Postman usa :nombre para los parámetros de ruta
    ruta_postman = re.sub(r"\{(\w+)\}", r":\1", ruta)
    segmentos = [s for s in ruta_postman.strip("/").split("/") if s]

    consulta = [
        {
            "key": p["name"],
            "value": str(p.get("schema", {}).get("default", "")),
            "description": limpiar(p.get("description", "")),
            # Los filtros van desactivados para no forzarlos en la primera prueba
            "disabled": True,
        }
        for p in parametros
        if p["in"] == "query"
    ]

    variables = [
        {
            "key": p["name"],
            # Los ids de producto y los números de pedido se rellenan solos con
            # las variables que guardan los scripts de la colección
            "value": {
                "product_id": "{{productId}}",
                "order_number": "{{orderNumber}}",
            }.get(p["name"], ""),
            "description": limpiar(p.get("description", "")),
        }
        for p in parametros
        if p["in"] == "path"
    ]

    crudo = "{{baseUrl}}/" + "/".join(segmentos)
    if consulta:
        crudo += "?" + "&".join(f"{c['key']}={c['value']}" for c in consulta)

    url: dict[str, Any] = {"raw": crudo, "host": ["{{baseUrl}}"], "path": segmentos}
    if consulta:
        url["query"] = consulta
    if variables:
        url["variable"] = variables
    return url


def construir_peticion(spec: dict, ruta: str, metodo: str, operacion: dict) -> dict:
    """Convierte una operación de OpenAPI en una petición de Postman."""
    protegida = "🔒" in operacion.get("description", "") or ruta.startswith(
        ("/admin", "/account", "/cart")
    )

    archivos = cuerpo_de_archivos(spec, operacion)

    peticion: dict[str, Any] = {
        "method": metodo.upper(),
        # En multipart no se fija Content-Type: Postman lo calcula solo,
        # igual que hace el navegador con FormData
        "header": [] if archivos else [{"key": "Content-Type", "value": "application/json"}],
        "url": construir_url(ruta, operacion.get("parameters", [])),
        "description": limpiar(operacion.get("description", "")),
    }

    # Las rutas públicas no envían el token
    if not protegida:
        peticion["auth"] = {"type": "noauth"}

    if archivos:
        peticion["body"] = archivos
    elif cuerpo := ejemplo_de_cuerpo(spec, operacion):
        peticion["body"] = {
            "mode": "raw",
            "raw": cuerpo,
            "options": {"raw": {"language": "json"}},
        }

    item: dict[str, Any] = {
        "name": operacion.get("summary", f"{metodo.upper()} {ruta}"),
        "request": peticion,
        "response": [],
    }

    # Scripts que guardan valores automáticamente
    script = None
    if ruta == "/auth/login":
        script = GUARDAR_TOKEN
    elif ruta == "/orders/checkout":
        script = GUARDAR_PEDIDO
    elif ruta == "/products" and metodo == "get":
        script = GUARDAR_PRODUCTO
    if script:
        item["event"] = [
            {"listen": "test", "script": {"type": "text/javascript", "exec": script}}
        ]

    return item


def main() -> None:
    spec = app.openapi()
    orden_tags = [t["name"] for t in spec.get("tags", [])]
    carpetas: dict[str, list] = {tag: [] for tag in orden_tags}

    for ruta, metodos in spec["paths"].items():
        for metodo, operacion in metodos.items():
            tag = (operacion.get("tags") or ["Otros"])[0]
            carpetas.setdefault(tag, []).append(
                construir_peticion(spec, ruta, metodo, operacion)
            )

    descripciones = {t["name"]: limpiar(t.get("description", "")) for t in spec.get("tags", [])}

    coleccion = {
        "info": {
            "name": "TECA API",
            "description": (
                "Colección para probar el backend del e-commerce TECA.\n\n"
                "CÓMO EMPEZAR:\n"
                "1. Asegúrate de que el backend esté corriendo "
                "(uvicorn app.main:app --reload).\n"
                "2. Ejecuta «Iniciar sesión y obtener el token JWT» en la carpeta "
                "Autenticación. El token se guarda solo.\n"
                "3. Ejecuta «Listar productos del catálogo». Eso guarda el id del primer "
                "producto, que usan las peticiones del carrito y del checkout.\n"
                "4. Ya puedes ejecutar cualquier otra petición.\n\n"
                "Los parámetros de filtro vienen desactivados: actívalos con la casilla "
                "de la pestaña Params cuando quieras usarlos."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        # Todas las peticiones heredan el token, salvo las marcadas como públicas
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]},
        "item": [
            {
                "name": nombre,
                "description": descripciones.get(nombre, ""),
                "item": items,
            }
            for nombre, items in carpetas.items()
            if items
        ],
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8000", "type": "string"},
            {"key": "token", "value": "", "type": "string"},
            {"key": "productId", "value": "", "type": "string"},
            {"key": "orderNumber", "value": "", "type": "string"},
        ],
    }

    entorno = {
        "name": "TECA - Local",
        "values": [
            {"key": "baseUrl", "value": "http://localhost:8000", "enabled": True},
            {"key": "token", "value": "", "enabled": True},
            {"key": "productId", "value": "", "enabled": True},
            {"key": "orderNumber", "value": "", "enabled": True},
        ],
        "_postman_variable_scope": "environment",
    }

    DESTINO.mkdir(exist_ok=True)
    (DESTINO / "TECA.postman_collection.json").write_text(
        json.dumps(coleccion, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (DESTINO / "TECA.postman_environment.json").write_text(
        json.dumps(entorno, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = sum(len(c["item"]) for c in coleccion["item"])
    print(f"Colección generada en {DESTINO}")
    print(f"{len(coleccion['item'])} carpetas · {total} peticiones")


if __name__ == "__main__":
    main()
