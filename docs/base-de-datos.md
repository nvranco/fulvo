# Base de datos — Fulvo (MVP)

Documento de trabajo del esquema de la base de datos. Igual que [`clases.md`](clases.md), se arma de a poco y cada decisión queda anotada acá.

**Alcance de hoy: solo `zonas` y `complejos`**, que son las dos entidades que ya tienen endpoints (RQ3 y RQ10). El resto de las clases de [`clases.md`](clases.md) (`Usuario`, `Partido`, `Postulacion`, etc.) todavía no tiene tabla: se agregan una por una, con una migración de Alembic cada vez, a medida que se hagan sus endpoints.

Diagrama: [`diagramas/base-de-datos.drawio`](diagramas/base-de-datos.drawio) (editable en draw.io) y [`diagramas/base-de-datos.svg`](diagramas/base-de-datos.svg).

![Esquema de la base de datos](diagramas/base-de-datos.svg)

## 1. Cómo se relaciona con el resto del código

La tabla se declara con un **modelo** SQLAlchemy (`fulvo/models.py`). El modelo es la clase de dominio y la tabla a la vez (`mapped_as_dataclass`). No reemplaza a los schemas Pydantic de `fulvo/schemas.py`: el modelo describe lo que se guarda y el schema describe lo que entra y sale por HTTP.

```
JSON -> ZonaEntrada / ComplejoEntrada (valida) -> modelo Zona / Complejo (BD) -> ZonaPublica / ComplejoPublico (JSON)
```

Los schemas de entrada y salida **no cambian**: la API sigue devolviendo lo mismo que hoy.

## 2. Tablas

Los nombres de tablas y columnas van en español, en plural las tablas y sin tildes, como indica `CLAUDE.md`.

### `zonas`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | entero | clave primaria |
| `nombre` | texto | obligatorio, único |
| `provincia` | texto | obligatorio |

Una zona es un partido o un barrio (Vicente López, Belgrano). Ver `clases.md`.

### `complejos`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | entero | clave primaria |
| `zona_id` | entero | obligatorio, clave foránea a `zonas.id` |
| `localidad` | texto | obligatorio |
| `nombre` | texto | obligatorio |
| `direccion` | texto | obligatorio |
| `telefono_contacto` | texto | opcional |
| `tipo` | texto | obligatorio |
| `reserva_online` | booleano | obligatorio, por defecto falso |
| `sitio_web` | texto | opcional |
| `calificacion_maps` | decimal | opcional |
| `latitud` | decimal | obligatorio |
| `longitud` | decimal | obligatorio |
| `link_maps` | texto | opcional |

Restricción de tabla: `UNIQUE (nombre, direccion)`.

### Relación

Una zona tiene muchos complejos y cada complejo pertenece a una sola zona (`complejos.zona_id` apunta a `zonas.id`).

## 3. Decisiones

- **Solo las columnas que usa la API hoy.** Quedan afuera `puntuacion_promedio`, `cantidad_puntuaciones`, `whatsapp_contacto` y `email_contacto`, que `clases.md` prevé para `Complejo`. Se agregan con una migración cuando llegue el RQ que las necesite (la puntuación llega con RQ8). Así cada columna tiene un endpoint que la justifica, y se practica la migración incremental.
- **Sin `created_at` ni `updated_at` por ahora.** Ningún RQ los pide para zonas y complejos. Se suman cuando haya una tabla que los necesite (por ejemplo `Notificacion` ya los define en `clases.md`).
- **La provincia vive solo en `zonas`.** El complejo no la guarda: la API la devuelve leyéndola de su zona. Así un complejo no puede contradecir a su zona. Es lo mismo que hace hoy `crear_complejo`, que copia la provincia de la zona.
- **`zona_id` es una clave foránea por id, no por nombre.** Hoy un complejo apunta a su zona por el nombre. Con la base de datos es una referencia al `id`, y el nombre se obtiene con la relación `Complejo.zona`.
- **Relación en un solo sentido.** El modelo `Complejo` tiene `zona` (muchos a uno). `Zona` no tiene `complejos`, porque ninguna ruta lo necesita. Si hace falta se agrega después sin tocar la tabla.
- **`tipo` es texto libre.** Los valores del CSV son pocos (Campo de fútbol, Cancha de fútbol sala, Club deportivo, etc.) y ninguna regla depende de ellos. No se arma una tabla ni un `Enum` hasta que haga falta filtrar o validar por tipo.
- **Coordenadas como decimal de punto flotante (`Float`).** Alcanza para ubicar un complejo en un mapa. La distancia se sigue calculando en Python con haversine (`distancia_km`), igual en SQLite y PostgreSQL.
- **Unicidad.**
  - `zonas.nombre` único y `complejos (nombre, direccion)` único. Reflejan las reglas de `409` que ya tiene la API.
  - La base distingue mayúsculas (`Belgrano` y `belgrano` son valores distintos para SQLite y PostgreSQL). Por eso las rutas siguen comparando sin mayúsculas antes de insertar, como hoy con `buscar_zona`. La restricción de la base es la última red de seguridad, no el chequeo principal.
- **Ids que no se reutilizan.** Hoy `Secuencia` evita que, al borrar el último complejo, un complejo nuevo herede su id. En PostgreSQL la secuencia lo garantiza sola. SQLite sí reutiliza el id del último registro borrado, así que `Complejo` usa `sqlite_autoincrement=True` para comportarse igual. Con eso `secuencia.py` deja de hacer falta.
- **Borrado.** `DELETE /complejos/{id}` borra la fila. Cuando exista `Partido` (que referencia a `Complejo`), hay que decidir qué pasa con los partidos de un complejo borrado (rechazar el borrado o marcarlo inactivo). Queda anotado y no se resuelve hoy. `zonas` no tiene endpoint de borrado.
- **Traducción modelo a schema.** `ComplejoPublico` expone `zona` como el nombre (texto) y `provincia`, pero el modelo guarda `zona_id`. La ruta arma el schema con una función chica (`complejo_publico`) que lee `complejo.zona.nombre` y `complejo.zona.provincia`. `ZonaPublica` se lee directo del modelo con `from_attributes=True`.

## 4. Configuración y datos iniciales

- **Conexión.** `DATABASE_URL` en `.env`, leída con `pydantic-settings` (`fulvo/settings.py`). En desarrollo es un archivo SQLite (`sqlite:///fulvo.db`, ignorado por git con `*.db`). En contenedor, CI y producción es PostgreSQL con `postgresql+psycopg://...`.
- **Esquema.** Lo crea Alembic (`alembic upgrade head`), nunca `create_all` fuera de los tests. Los tests sí usan `create_all` sobre SQLite en memoria, como `codigo_aulas/07`.
- **Carga inicial.** Script manual e idempotente: `python -m fulvo.carga_inicial` lee `fulvo/datos/complejos.csv` e inserta las zonas y complejos que todavía no existen. Se puede correr las veces que haga falta, y `entrypoint.sh` lo corre después de `alembic upgrade head` en el deploy. Las zonas se crean en el orden en que aparecen en el CSV, y los complejos en el orden de las filas, así que los ids quedan iguales a los de la lista en memoria de hoy.

## 5. Pendiente

- Tablas del resto de las clases (`Usuario`, `Rol`, `Partido`, `Postulacion`, `Votacion`, `Notificacion`, `Reclamo`, `Sancion`), de a una con su migración. Este documento y el diagrama se amplían en cada paso.
- Estrategia de datos de prueba en los tests: los tests actuales usan los 51 complejos del CSV. Hay que decidir entre cargar el CSV en cada test o armar los datos con `factory-boy`.
