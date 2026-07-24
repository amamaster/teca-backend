# TECA API — Backend del e-commerce de muebles

API REST construida con **Python + FastAPI + MongoDB** para la tienda TECA *(Para toda la vida)*.

Este backend expone todos los endpoints que consume el frontend hecho en **Next.js / React**:
catálogo con filtros, carrito, checkout (con o sin cuenta), área del cliente y panel de
administración.

> **¿Eres estudiante y vas a conectar el frontend?**
> Salta directo a [Cómo conectar el frontend de Next.js](#cómo-conectar-el-frontend-de-nextjs).
> Ahí está todo lo que necesitas con código listo para copiar.

---

## Índice

1. [Requisitos previos](#1-requisitos-previos)
2. [Instalación paso a paso](#2-instalación-paso-a-paso)
3. [Documentación interactiva (Swagger)](#3-documentación-interactiva-swagger)
4. [Cómo funciona la autenticación](#4-cómo-funciona-la-autenticación)
5. [Cómo conectar el frontend de Next.js](#cómo-conectar-el-frontend-de-nextjs)
6. [Referencia de endpoints](#6-referencia-de-endpoints)
7. [Reglas de negocio importantes](#7-reglas-de-negocio-importantes)
8. [Estructura del proyecto](#8-estructura-del-proyecto)
9. [Solución de problemas](#9-solución-de-problemas)

---

## 1. Requisitos previos

Antes de empezar necesitas tener instalado:

| Herramienta | Versión | Cómo verificar |
|---|---|---|
| **Python** | 3.11 o superior | `python --version` |
| **Docker Desktop** | cualquiera reciente | `docker compose version` |
| **Git** | cualquiera | `git --version` |

> Si `python --version` te muestra 3.10 o menos, descarga la última versión desde
> [python.org](https://www.python.org/downloads/). Al instalar en Windows, **marca la
> casilla «Add Python to PATH»**.

---

## 2. Instalación paso a paso

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/amamaster/teca-backend.git
```

Luego entra a la carpeta del backend:

```bash
cd teca-backend/backend
```

### Paso 2 — Levantar MongoDB en Docker

La base de datos corre en un contenedor, así no tienes que instalar MongoDB en tu máquina.
Asegúrate de que **Docker Desktop esté abierto** y ejecuta, desde la **raíz del repositorio**
(la carpeta que contiene `docker-compose.yml`, no dentro de `backend/`):

```bash
docker compose up -d
```

Eso es todo. El archivo [`docker-compose.yml`](../docker-compose.yml) ya trae la
configuración, así que no tienes que recordar ningún parámetro.

Levanta dos contenedores:

| Contenedor | Puerto | Para qué sirve |
|---|---|---|
| `teca-mongo` | 27017 | La base de datos que usa el backend |
| `teca-mongo-express` | 8081 | Interfaz web para **ver los datos** en el navegador |

Verifica que quedaron corriendo:

```bash
docker compose ps
```

Debes ver `teca-mongo` con el estado **`Up (healthy)`**. La palabra *healthy* significa que
Mongo ya terminó de arrancar y acepta conexiones.

> 💡 **Truco útil:** abre **http://localhost:8081** en el navegador para ver las colecciones
> y los documentos guardados sin instalar ningún programa. Es muy práctico para entender qué
> está grabando el backend mientras desarrollas el frontend.

#### Comandos del día a día

| Qué quieres hacer | Comando |
|---|---|
| Encender la base de datos | `docker compose up -d` |
| Apagarla (los datos **se conservan**) | `docker compose down` |
| Ver si está corriendo | `docker compose ps` |
| Ver los mensajes de Mongo | `docker compose logs mongo` |
| Borrar **todos** los datos y empezar de cero | `docker compose down -v` |

> Los datos se guardan en un volumen de Docker llamado `teca-mongo-data`, así que sobreviven
> aunque apagues la computadora o borres los contenedores. Solo `docker compose down -v`
> (con la `-v`) los elimina de verdad.

### Paso 3 — Crear el entorno virtual de Python

El entorno virtual aísla las librerías de este proyecto de las de tu sistema.

**En Windows (PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**En Mac o Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Sabrás que funcionó porque tu terminal mostrará `(.venv)` al inicio de la línea.

> **Error común en Windows:** si PowerShell dice *«la ejecución de scripts está
> deshabilitada»*, ejecuta esto una sola vez y vuelve a intentar:
> ```bash
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### Paso 4 — Instalar las dependencias

```bash
pip install -r requirements.txt
```

### Paso 5 — Configurar las variables de entorno

Copia el archivo de ejemplo:

**Windows:**
```bash
copy .env.example .env
```

**Mac o Linux:**
```bash
cp .env.example .env
```

El archivo `.env` que se crea ya viene con valores que funcionan para desarrollo local.
Solo tendrías que tocarlo si tu Mongo usa otro puerto o si tu frontend corre en un
puerto distinto:

| Variable | Para qué sirve | Valor por defecto |
|---|---|---|
| `MONGO_URI` | Dirección de MongoDB | `mongodb://localhost:27017` |
| `MONGO_DB` | Nombre de la base de datos | `teca` |
| `JWT_SECRET` | Clave para firmar los tokens | *(cámbiala en producción)* |
| `SHIPPING_COST` | Costo del envío en B/. | `25.00` |
| `FREE_SHIPPING_THRESHOLD` | Monto para envío gratis | `300.00` |
| `CORS_ORIGINS` | Direcciones del frontend autorizadas | `http://localhost:3000,http://localhost:5173` |

> ⚠️ **`CORS_ORIGINS` es la causa #1 de errores al conectar el frontend.** Next.js corre en
> `http://localhost:3000` por defecto, que ya está incluido. Si tu Next corre en otro
> puerto, agrégalo aquí separado por coma.

> 🔒 El archivo `.env` **no se sube a GitHub** (está en el `.gitignore`), porque contiene
> claves. Por eso cada quien crea el suyo a partir de `.env.example`.

### Paso 6 — Cargar datos de ejemplo

```bash
python seed.py
```

Esto crea 8 productos del catálogo, un usuario administrador y el cupón de descuento.
Es seguro ejecutarlo varias veces: no duplica nada.

| Dato | Valor |
|---|---|
| Correo del admin | `admin@teca.com` |
| Contraseña | `Admin1234!` |
| Cupón de prueba | `TECA10` (10 % de descuento) |

### Paso 7 — Arrancar el servidor

```bash
uvicorn app.main:app --reload
```

Si todo salió bien verás:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

Abre **http://localhost:8000/docs** en el navegador. Si ves la documentación
interactiva, ya está funcionando. 🎉

> `--reload` reinicia el servidor solo cada vez que guardas un archivo. Úsalo mientras
> desarrollas.

---

## 3. Documentación interactiva (Swagger)

Con el servidor corriendo tienes tres formas de explorar la API:

| Recurso | URL | Para qué sirve |
|---|---|---|
| **Swagger UI** | http://localhost:8000/docs | Explorar y **probar** endpoints desde el navegador |
| **ReDoc** | http://localhost:8000/redoc | Lectura corrida, ideal para el documento del proyecto |
| **OpenAPI JSON** | http://localhost:8000/openapi.json | Importar en Postman o generar el cliente del front |

Cada endpoint explica qué hace, **a qué pantalla del diseño corresponde**, sus parámetros,
las reglas de negocio, el rol necesario y los errores que puede devolver. Todo está en
español y se genera solo desde el código, así que nunca queda desactualizado.

### Cómo probar un endpoint protegido en Swagger

1. Busca `POST /auth/login` → botón **Try it out**.
2. Envía `{"email": "admin@teca.com", "password": "Admin1234!"}`.
3. Copia el valor de `access_token` de la respuesta.
4. Pulsa **Authorize** (arriba a la derecha) y pega el token.
5. Ya puedes probar cualquier endpoint con el candado 🔒.

### Exportar la documentación a un archivo

```bash
python export_openapi.py
```

Genera `openapi.json` (no necesita que Mongo esté corriendo). Ese archivo lo puedes
importar en **Postman**, **Insomnia** o abrirlo en https://editor.swagger.io.

---

## 4. Cómo funciona la autenticación

La API usa **JWT (JSON Web Token)**. El flujo es:

```
1. El usuario envía correo y contraseña  →  POST /auth/login
2. El backend responde con un access_token
3. El frontend guarda ese token
4. En cada petición protegida envía:  Authorization: Bearer <token>
```

El token dura **24 horas** por defecto y lleva dentro el `id` y el `rol` del usuario.

### Roles del sistema

| Rol | Qué puede hacer |
|---|---|
| `cliente` | Comprar, ver sus pedidos, gestionar su cuenta, dejar reseñas |
| `admin` | Todo el panel de administración |
| `editor` | Gestionar productos |
| `encargado` | Productos, pedidos y devoluciones |
| `vendedor` | Pedidos (y ver productos) |
| `soporte` | Devoluciones y ver pedidos |
| `finanzas` | Reportes financieros |

Si un usuario intenta algo que su rol no permite, la API responde **403**.

---

## Cómo conectar el frontend de Next.js

Esta es la parte que necesitas para integrar tu proyecto de React/Next con el backend.

### Paso 1 — Guardar la dirección del backend

En la raíz de tu proyecto de Next.js crea el archivo **`.env.local`**:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> El prefijo `NEXT_PUBLIC_` es obligatorio para que la variable esté disponible en el
> navegador. Sin él, solo funcionaría del lado del servidor.

Después de crear o modificar este archivo, **reinicia `npm run dev`** — Next solo lee las
variables de entorno al arrancar.

### Paso 2 — Crear un cliente de API reutilizable

Crea el archivo **`lib/api.js`** (o `lib/api.ts` si usas TypeScript). Este archivo centraliza
todas las llamadas, así no repites la URL ni la lógica del token en cada componente:

```javascript
const API_URL = process.env.NEXT_PUBLIC_API_URL;

/** Lee el token guardado tras el login. */
function getToken() {
  if (typeof window === "undefined") return null; // no existe en el servidor
  return localStorage.getItem("token");
}

/**
 * Hace una petición al backend.
 * Agrega el token automáticamente si existe y convierte los errores
 * de la API en excepciones con el mensaje en español.
 */
export async function api(endpoint, options = {}) {
  const token = getToken();

  const respuesta = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  // 204 = operación exitosa sin contenido (por ejemplo, un DELETE)
  if (respuesta.status === 204) return null;

  const datos = await respuesta.json();

  if (!respuesta.ok) {
    // La API devuelve los errores como { "detail": "mensaje" }
    throw new Error(datos.detail || "Ocurrió un error inesperado");
  }

  return datos;
}
```

### Paso 3 — Usarlo en tus componentes

#### Listar el catálogo con filtros

```javascript
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Catalogo() {
  const [productos, setProductos] = useState([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    // Los filtros del diseño se arman como query params
    const params = new URLSearchParams({
      category: "sofa,silla",   // varias categorías separadas por coma
      material: "madera",
      min_price: "0",
      max_price: "500",
      sort: "price_asc",        // precio de menor a mayor
      page: "1",
      page_size: "8",
    });

    api(`/products?${params}`)
      .then((datos) => {
        setProductos(datos.items);
        setTotal(datos.total);
      })
      .catch((error) => alert(error.message))
      .finally(() => setCargando(false));
  }, []);

  if (cargando) return <p>Cargando...</p>;

  return (
    <div>
      <p>Mostrando {productos.length} de {total} productos</p>
      {productos.map((producto) => (
        <article key={producto.id}>
          <h3>{producto.name}</h3>
          <p>${producto.price}</p>
          <small>Material: {producto.material}</small>
        </article>
      ))}
    </div>
  );
}
```

#### Iniciar sesión y guardar el token

```javascript
"use client";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function FormularioLogin() {
  const router = useRouter();

  async function manejarEnvio(evento) {
    evento.preventDefault();
    const formulario = new FormData(evento.target);

    try {
      const datos = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: formulario.get("email"),
          password: formulario.get("password"),
        }),
      });

      // Guardamos el token para las siguientes peticiones
      localStorage.setItem("token", datos.access_token);
      localStorage.setItem("usuario", JSON.stringify(datos.user));

      // Si es un usuario interno con contraseña temporal, lo mandamos a cambiarla
      if (datos.must_change_password) {
        router.push("/cambiar-contrasena");
      } else {
        router.push("/");
      }
    } catch (error) {
      alert(error.message); // "Correo o contraseña incorrectos"
    }
  }

  return (
    <form onSubmit={manejarEnvio}>
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <button type="submit">Iniciar sesión</button>
    </form>
  );
}
```

#### Agregar al carrito

```javascript
async function agregarAlCarrito(productoId, cantidad) {
  try {
    const carrito = await api("/cart/items", {
      method: "POST",
      body: JSON.stringify({ product_id: productoId, quantity: cantidad }),
    });

    // La respuesta ya trae el carrito completo con los totales recalculados,
    // así que puedes actualizar todo el resumen con esta única llamada
    console.log("Subtotal:", carrito.subtotal);
    console.log("Envío:", carrito.shipping);
    console.log("Total:", carrito.total);
    console.log("Falta para envío gratis:", carrito.missing_for_free_shipping);
  } catch (error) {
    // Ej: "No puedes seleccionar más de 3 unidades"
    alert(error.message);
  }
}
```

#### Finalizar la compra (funciona con o sin cuenta)

```javascript
async function finalizarCompra() {
  const pedido = await api("/orders/checkout", {
    method: "POST",
    body: JSON.stringify({
      email: "cliente@correo.com",       // obligatorio, también para invitados
      items: [{ product_id: "...", quantity: 1 }],
      shipping_address: {
        full_name: "Aldair Gallardo",
        phone: "6000-0000",
        province: "Chiriquí",
        city: "David",
        address_line: "Ave. Álvarez, casa 12",
        reference: "Frente al parque",
      },
      payment_method: "yappy",           // card | paypal | bitcoin | yappy
      coupon_code: "TECA10",             // opcional
    }),
  });

  // Datos para la pantalla de confirmación
  console.log(pedido.order_number); // "TEC-2026-001"
  console.log(pedido.total);
}
```

> **Importante:** este endpoint funciona **con y sin token**. Si el usuario está logueado,
> el pedido queda asociado a su cuenta; si no, se registra como compra de invitado. Por eso
> el campo `email` siempre es obligatorio: es con lo que después podrá consultar su pedido
> en `POST /orders/lookup`.

### Paso 4 — Proteger rutas según el rol

```javascript
"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export function useUsuario() {
  const [usuario, setUsuario] = useState(null);
  const router = useRouter();

  useEffect(() => {
    const guardado = localStorage.getItem("usuario");
    if (!guardado) {
      router.push("/login");
      return;
    }
    setUsuario(JSON.parse(guardado));
  }, [router]);

  return usuario;
}

// Uso en una página del panel:
// const usuario = useUsuario();
// if (usuario && usuario.role !== "admin") return <p>No tienes permiso</p>;
```

> ⚠️ Esta validación en el frontend es solo para **mostrar u ocultar** la interfaz.
> La seguridad real la aplica el backend: aunque alguien manipule el `localStorage`,
> la API responderá **403** si su rol no tiene permiso.

### Errores comunes al integrar

| Síntoma | Causa | Solución |
|---|---|---|
| `Failed to fetch` / error de CORS en la consola | El puerto de tu frontend no está en `CORS_ORIGINS` | Agrégalo en el `.env` del backend y reinicia uvicorn |
| `401 No autenticado` | No se envió el token o expiró (dura 24 h) | Vuelve a hacer login |
| `403 No tienes permisos` | El rol del usuario no alcanza | Entra con un usuario con el rol correcto |
| `422 Unprocessable Entity` | Falta un campo o tiene el tipo equivocado | Revisa el esquema del endpoint en `/docs` |
| `process.env.NEXT_PUBLIC_API_URL` es `undefined` | No reiniciaste Next tras crear `.env.local` | Detén y vuelve a correr `npm run dev` |
| `ECONNREFUSED` al llamar a la API | El backend no está corriendo | Arranca `uvicorn app.main:app --reload` |

---

## 6. Referencia de endpoints

> Todos los endpoints marcados con 🔒 requieren el header `Authorization: Bearer <token>`.

### Autenticación — `/auth`

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Registrar un cliente nuevo |
| GET | `/auth/verify-email/{token}` | Verificar el correo |
| POST | `/auth/login` | Iniciar sesión y obtener el token |
| POST | `/auth/forgot-password` | Solicitar recuperación de contraseña |
| POST | `/auth/reset-password` | Restablecer la contraseña con el token |
| POST | `/auth/change-password` | 🔒 Cambiar la contraseña |
| GET | `/auth/me` | 🔒 Ver mi perfil |
| PATCH | `/auth/me` | 🔒 Editar mi perfil |

### Catálogo — `/products`

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/products` | Listar con filtros, búsqueda, orden y paginación |
| GET | `/products/{id}` | Detalle del producto |
| GET | `/products/{id}/reviews` | Reseñas, promedio y distribución de estrellas |
| POST | `/products/{id}/reviews` | 🔒 Escribir una reseña |

**Filtros de `GET /products`:** `search`, `category`, `material`, `min_price`, `max_price`,
`sort`, `page`, `page_size`.

**Valores de `sort`:** `price_asc` (menor a mayor) · `price_desc` (mayor a menor) ·
`newest` (más nuevos) · `relevance` (más relevantes).

### Carrito — `/cart` 🔒

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/cart` | Ver el carrito con el resumen de totales |
| POST | `/cart/items` | Agregar un producto (suma si ya existe) |
| PUT | `/cart/items/{id}` | Fijar la cantidad exacta |
| DELETE | `/cart/items/{id}` | Quitar un producto |
| POST | `/cart/coupon` | Aplicar un cupón |
| DELETE | `/cart/coupon` | Quitar el cupón |

> Todas estas rutas devuelven el **carrito completo ya recalculado**, así actualizas toda
> la pantalla con una sola llamada.

### Pedidos — `/orders`

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/orders/checkout` | Crear el pedido (con o **sin** cuenta) |
| GET | `/orders/mine` | 🔒 Mis pedidos |
| POST | `/orders/lookup` | Consultar un pedido con número + correo (invitados) |
| GET | `/orders/{numero}` | 🔒 Detalle y seguimiento |

**Estados:** `confirmado` → `en_preparacion` → `en_camino` → `entregado` (o `cancelado`).

### Mi cuenta — `/account` 🔒

| Método | Ruta | Descripción |
|---|---|---|
| GET / POST | `/account/addresses` | Listar / agregar direcciones |
| PUT / DELETE | `/account/addresses/{id}` | Editar / eliminar dirección |
| GET / POST | `/account/payment-methods` | Listar / agregar métodos de pago |
| PUT / DELETE | `/account/payment-methods/{id}` | Editar / eliminar método |
| GET / POST | `/account/returns` | Ver / solicitar devoluciones |

**Estados de devolución:** `en_revision`, `aprobado`, `rechazado`, `completado`.

### Administración — `/admin` 🔒

| Método | Ruta | Rol necesario | Descripción |
|---|---|---|---|
| GET / POST | `/admin/users` | admin | Usuarios internos |
| PATCH / DELETE | `/admin/users/{id}` | admin | Editar / eliminar usuario |
| GET | `/admin/roles` | interno | Matriz de roles y permisos |
| GET / POST | `/admin/products` | admin, editor, encargado | Productos del panel |
| PATCH / DELETE | `/admin/products/{id}` | admin, editor, encargado | Editar / eliminar producto |
| GET | `/admin/orders` | ventas | Todos los pedidos |
| PATCH | `/admin/orders/{numero}/status` | ventas | Cambiar estado y número de guía |
| GET | `/admin/returns` | ventas | Todas las devoluciones |
| PATCH | `/admin/returns/{id}/status` | ventas | Resolver una devolución |
| GET / POST / DELETE | `/admin/coupons` | admin | Cupones de descuento |
| GET | `/admin/audit` | admin | Registro de auditoría |
| GET | `/admin/dashboard` | interno | Métricas del panel |
| GET | `/admin/finance/summary` | admin, finanzas | Ingresos por mes y método de pago |

---

## 7. Reglas de negocio importantes

Estas reglas ya están implementadas en el backend. **No las repliques en el frontend como
única validación**, porque el servidor siempre vuelve a verificarlas:

- **Stock.** No se puede agregar al carrito ni comprar más unidades de las disponibles.
  El backend responde `409` con el mensaje *«No puedes seleccionar más de N unidades»*.
- **Precios.** El checkout **recalcula todos los precios en el servidor**. Nunca confía en
  los totales que envía el frontend, para que nadie pueda manipular el precio final.
- **Envío.** Cuesta `SHIPPING_COST` (B/. 25 por defecto) y es **gratis** al superar
  `FREE_SHIPPING_THRESHOLD` (B/. 300). El campo `missing_for_free_shipping` te dice cuánto
  falta, para el aviso *«Te faltan B/. XX.XX para envío gratis»*.
- **Cupones.** Solo se puede aplicar **uno a la vez**; aplicar otro reemplaza el anterior.
- **Números de pedido.** Se generan solos con un contador atómico por año
  (`TEC-2026-001`, `TEC-2026-002`, …), así que nunca se repiten.
- **Reseñas.** Una por usuario y producto. La etiqueta *«Compra verificada»* se calcula
  automáticamente: aparece si el usuario tiene un pedido **entregado** con ese producto.
- **Contraseñas.** Se guardan cifradas con bcrypt. La API **nunca** devuelve el hash.
- **Métodos de pago.** Solo se almacena la etiqueta (*«Visa terminada en 4821»*), el titular
  y el vencimiento. **Nunca el número completo de la tarjeta ni el CVV.**
- **Auditoría.** Toda acción administrativa queda registrada con quién la hizo y cuándo.

---

## 8. Estructura del proyecto

```
backend/
├── app/
│   ├── main.py          # Aplicación FastAPI, CORS y configuración de Swagger
│   ├── config.py        # Lectura de las variables de entorno (.env)
│   ├── database.py      # Conexión a MongoDB e índices
│   ├── security.py      # JWT, cifrado de contraseñas, roles y auditoría
│   ├── models.py        # Esquemas de validación (Pydantic)
│   └── routers/
│       ├── auth.py      # Registro, login, verificación de correo
│       ├── products.py  # Catálogo público y reseñas
│       ├── cart.py      # Carrito y cupones
│       ├── orders.py    # Checkout y seguimiento de pedidos
│       ├── account.py   # Direcciones, métodos de pago, devoluciones
│       └── admin.py     # Panel de administración
├── seed.py              # Carga datos de ejemplo
├── export_openapi.py    # Exporta la documentación a openapi.json
├── requirements.txt     # Dependencias de Python
├── .env.example         # Plantilla de configuración
└── README.md
```

### Colecciones en MongoDB

| Colección | Qué guarda |
|---|---|
| `users` | Clientes y usuarios internos (con la contraseña cifrada) |
| `products` | Catálogo de muebles |
| `carts` | Carrito de cada usuario autenticado |
| `orders` | Pedidos con su historial de estados |
| `reviews` | Reseñas de productos |
| `addresses` | Direcciones guardadas |
| `payment_methods` | Métodos de pago guardados |
| `returns` | Solicitudes de devolución |
| `coupons` | Cupones de descuento |
| `audit_log` | Registro de acciones administrativas |
| `counters` | Contadores para los números de pedido y devolución |

---

## 9. Solución de problemas

<details>
<summary><b>«No se reconoce uvicorn como comando»</b></summary>

No activaste el entorno virtual. Ejecuta `.venv\Scripts\activate` (Windows) o
`source .venv/bin/activate` (Mac/Linux) y verifica que aparezca `(.venv)` en tu terminal.
</details>

<details>
<summary><b>«ServerSelectionTimeoutError» al arrancar</b></summary>

El backend no encuentra MongoDB. Revisa que el contenedor esté corriendo con
`docker compose ps`. Si no aparece o no dice *healthy*, levántalo desde la raíz del
repositorio con `docker compose up -d`.

Si Docker Desktop no está abierto, ábrelo primero y espera a que el ícono de la ballena
deje de animarse.
</details>

<details>
<summary><b>Error de CORS al llamar desde el frontend</b></summary>

El puerto de tu frontend no está autorizado. Abre el `.env` del backend, agrega tu
dirección a `CORS_ORIGINS` separada por coma y reinicia uvicorn.
</details>

<details>
<summary><b>El catálogo devuelve una lista vacía</b></summary>

No cargaste los datos de ejemplo. Ejecuta `python seed.py`.
</details>

<details>
<summary><b>«Port 8000 is already in use»</b></summary>

Ya tienes otro servidor en ese puerto. Usa uno distinto con
`uvicorn app.main:app --reload --port 8001` y actualiza `NEXT_PUBLIC_API_URL` en el frontend.
</details>

<details>
<summary><b>Quiero borrar todos los datos y empezar de cero</b></summary>

Desde la raíz del repositorio:

```bash
docker compose down -v
docker compose up -d
```

La `-v` elimina el volumen con los datos. Después vuelve a ejecutar `python seed.py`
para recargar los productos de ejemplo.
</details>

<details>
<summary><b>«docker: command not found» o «cannot connect to the Docker daemon»</b></summary>

Docker Desktop no está instalado o no está abierto. Instálalo desde
[docker.com](https://www.docker.com/products/docker-desktop/), ábrelo y espera a que
termine de iniciar antes de ejecutar `docker compose up -d`.
</details>
