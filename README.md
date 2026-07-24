# TECA — Proyecto e-commerce de muebles

Proyecto de la asignatura **Programación 7**. Tienda en línea de muebles TECA
*(Para toda la vida)*, con catálogo, carrito, checkout, área del cliente y panel de
administración.

## Estructura del repositorio

| Archivo / carpeta | Tecnología | Descripción |
|---|---|---|
| [`backend/`](backend/) | Python · FastAPI · MongoDB | API REST que consume el frontend |
| [`docker-compose.yml`](docker-compose.yml) | Docker | Levanta MongoDB y su visor web |
| *(frontend)* | React · Next.js | Interfaz de la tienda *(en desarrollo)* |

## Empezar

Toda la información para instalar, ejecutar y **conectar el frontend de Next.js** está en:

### 👉 [backend/README.md](backend/README.md)

Ahí encontrarás:

- Instalación paso a paso (Windows, Mac y Linux)
- Cómo levantar MongoDB con Docker
- **Guía de integración con Next.js** con código listo para copiar
- Referencia completa de todos los endpoints
- Las reglas de negocio que aplica el servidor
- Solución de los errores más comunes

## Arranque rápido

Con **Docker Desktop abierto**, desde la raíz del repositorio:

```bash
docker compose up -d
```

Eso levanta MongoDB. Luego, el backend:

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python seed.py
uvicorn app.main:app --reload
```

### Direcciones

| Servicio | URL | Para qué sirve |
|---|---|---|
| **Documentación de la API** | http://localhost:8000/docs | Probar los endpoints desde el navegador |
| **API** | http://localhost:8000 | Lo que consume el frontend |
| **Visor de la base de datos** | http://localhost:8081 | Ver las colecciones y los documentos |

| Dato de prueba | Valor |
|---|---|
| Administrador | `admin@teca.com` / `Admin1234!` |
| Cupón de descuento | `TECA10` (10 %) |

Para apagar la base de datos conservando los datos: `docker compose down`
