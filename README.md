

# Fulvo

<p align="center">
  <img src="docs/img/fulvo.png" alt="fulvo?" width="150">
</p>

API RESTful para armar partidos de fútbol y conseguir jugadores que completen los lugares que faltan.

> Este trabajo es el proyecto final de **Programación 2** de la **Licenciatura en Ciencia de Datos** de la **UNSAM**.

Fulvo es un **MVP** cuyo proposito es validar la siguiente hipótesis:

> ¿Las personas están dispuestas a solicitar jugadores extra para completar un partido a través de una plataforma?

## Secuencia

1. Los usuarios **se registran** en el sistema.
2. Un usuario **organiza un partido** y define cuántos lugares (slots) le faltan.
3. Otros usuarios **se postulan** para ocupar los lugares libres.
4. El organizador **acepta** a los postulantes que quiera.
5. Al aceptar, organizador y jugador **se ven el número de WhatsApp** para coordinar por fuera de la aplicación.

La coordinación final (horario exacto, llegada, pago de la cancha) se hace por WhatsApp. Fulvo solo conecta a las personas.

## Requerimientos

| RQ | Descripción |
|---|---|
| RQ1 | Registrarse e iniciar sesión (edad mínima 16). |
| RQ2 | Perfil de usuario con puntuación promedio y partidos jugados. |
| RQ3 | Ver zonas y complejos. |
| RQ4 | Publicar partidos indicando complejo, fecha, hora, tipo y cupos faltantes. |
| RQ5 | Listar partidos abiertos con filtros y postularse. |
| RQ6 | El organizador acepta, rechaza o revoca postulantes. Al aceptar, ambos se ven el WhatsApp. |
| RQ7 | Cancelar postulación, baja de un aceptado, revocación y cancelación del partido. |
| RQ8 | Votar después del partido, no-show y bloqueo por votaciones pendientes. |
| RQ9 | Notificaciones dentro de la app. |
| RQ10 | Admin: bloquear usuarios y editar zonas y complejos. |
| RQ11 | Reclamos por no-show o votación, resueltos por el admin. |

El detalle está en [`docs/requerimientos.md`](docs/requerimientos.md) y los diagramas de secuencia en [`docs/diagramas/`](docs/diagramas/).

## Estado

En desarrollo. Todavía no hay código de la API: por ahora el repositorio contiene la consigna, los requerimientos y los diagramas de secuencia.

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

## Despliegue

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
- [`docs/requerimientos.md`](docs/requerimientos.md): requerimientos del MVP e ideas post-MVP.
- [`docs/diagramas/`](docs/diagramas/): diagramas de secuencia.
- [`CLAUDE.md`](CLAUDE.md): convenciones y decisiones del proyecto.

## Créditos

Proyecto realizado en el marco de la materia **Programación 2 (LCD) - UNSAM**. El stack y la estructura siguen el material de la cátedra: https://rmatuk.github.io/prog2
