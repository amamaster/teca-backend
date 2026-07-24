"""Exporta la especificación OpenAPI a openapi.json (sin necesidad de MongoDB).

Uso:  python export_openapi.py

El archivo resultante se puede importar en Postman, Insomnia, Swagger Editor
(https://editor.swagger.io) o usarse para generar el cliente del frontend.
"""
import json
from pathlib import Path

from app.main import app

destination = Path(__file__).parent / "openapi.json"
spec = app.openapi()
destination.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

operations = sum(len(methods) for methods in spec["paths"].values())
print(f"OpenAPI {spec['openapi']} exportado a {destination}")
print(f"{len(spec['paths'])} rutas · {operations} operaciones documentadas")
