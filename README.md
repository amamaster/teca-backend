# TECA — Proyecto e-commerce de muebles

Proyecto de la asignatura **Programación 7**. Tienda en línea de muebles TECA
*(Para toda la vida)*, con catálogo, carrito, checkout, área del cliente y panel de
administración.

## Estructura del repositorio

| Carpeta | Tecnología | Descripción |
|---|---|---|
| [`backend/`](backend/) | Python · FastAPI · MongoDB | API REST que consume el frontend |
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

```bash
docker run -d --name teca-mongo -p 27017:27017 -v teca-mongo-data:/data/db mongo:7
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python seed.py
uvicorn app.main:app --reload
```

Abre **http://localhost:8000/docs** para ver la documentación interactiva de la API,
donde puedes probar cada endpoint desde el navegador.

| Dato de prueba | Valor |
|---|---|
| Administrador | `admin@teca.com` / `Admin1234!` |
| Cupón de descuento | `TECA10` (10 %) |
