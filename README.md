<p align="center">
  <img src="docs/img/fulvo.png" alt="fulvo?" width="150">
</p>

# Fulvo

API RESTful para armar partidos de fútbol y conseguir jugadores que completen los lugares que faltan.

> **Proyecto académico.** Este trabajo es el proyecto final de **Programación 2** de la **Licenciatura en Ciencia de Datos** de la **UNSAM**. Tiene fines **únicamente introductorios y educativos**: no es un producto terminado ni está pensado para uso real en producción.

## Qué es Fulvo

Fulvo es un **MVP** (producto mínimo viable) pensado para validar una hipótesis:

> ¿Las personas están dispuestas a solicitar jugadores extra para completar un partido?

Por eso el alcance es chico a propósito. Solo implementa lo necesario para probar ese comportamiento.

## Idea principal

1. Los usuarios **se registran** en el sistema.
2. Un usuario **organiza un partido** y define cuántos lugares (slots) le faltan.
3. Otros usuarios **se postulan** para ocupar los lugares libres.
4. El organizador **acepta** a los postulantes que quiera.
5. Al aceptar, el organizador **recibe el número de WhatsApp** del jugador aceptado para coordinar con él por fuera de la aplicación.

La coordinación final (horario exacto, llegada, pago de la cancha) se hace por WhatsApp. Fulvo solo conecta a las personas.

## Requerimientos de alto nivel

| RQ | Descripción |
|---|---|
| RQ1 | Los usuarios podrán registrarse e iniciar sesión. |
| RQ2 | Los usuarios podrán crear partidos indicando fecha, lugar y cantidad de lugares libres. |
| RQ3 | Los usuarios podrán ver los partidos que todavía tienen lugares libres. |
| RQ4 | Los usuarios podrán postularse a un partido para ocupar un lugar. |
| RQ5 | El organizador podrá aceptar o rechazar las postulaciones de su partido. |
| RQ6 | Al aceptar una postulación, el organizador recibirá el número de WhatsApp del jugador aceptado. |

El detalle de casos de uso y endpoints se irá completando en `docs/`.

## Estado

En desarrollo. Todavía no hay código de la API: por ahora el repositorio contiene la consigna y la documentación base.

## Stack

Se usa el stack de la cátedra:

- **FastAPI** como framework de la API
- **SQLAlchemy** (async) y **Alembic** para base de datos y migraciones
- **JWT** (`pyjwt`) y **argon2** (`pwdlib`) para autenticación segura
- **SQLite** en desarrollo y **PostgreSQL** en contenedor y producción
- **pytest** para los tests
- **Ruff** y **Typos** para calidad de código
- **Poetry** y **poethepoet** para dependencias y tareas
- **Docker** y **Docker Compose**
- **GitHub Actions** para la integración continua
- **Fly.io** para el deploy

## Cómo desplegar y probar

> Esta sección se completa a medida que se implementa la API.

```bash
# Instalar dependencias
poetry install

# Levantar la API en desarrollo
poetry serve

# Correr lint, tests y cobertura
poetry test

# Levantar API y PostgreSQL con Docker
docker compose up --build
```

La documentación interactiva de la API queda disponible en `/docs` (Swagger) y `/redoc` cuando el servidor está corriendo.

## Documentación

- [`docs/consigna.pdf`](docs/consigna.pdf): consigna del trabajo práctico.
- [`CLAUDE.md`](CLAUDE.md): convenciones y decisiones del proyecto.

## Créditos

Proyecto realizado en el marco de la materia **Programación 2 (LCD) - UNSAM**. El stack y la estructura siguen el material de la cátedra: https://rmatuk.github.io/prog2
