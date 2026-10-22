

# fulvo

<p align="center">
  <img src="docs/img/fulvo.png" alt="fulvo?" width="300">
</p>

Aplicación para completar equipos de fútbol. 
Proyecto final de la materia **Programación II** de la **Licenciatura en Ciencia de Datos** de la **UNSAM**.

## Secuencia

1. Los usuarios **se registran** en el sistema.
2. Un usuario **organiza un partido** y define cuántos lugares (slots) le faltan.
3. Otros usuarios **se postulan** para ocupar los lugares libres.
4. El organizador **acepta** a los postulantes que quiera.
5. Al aceptar, organizador y jugador **se ven el número de WhatsApp** para coordinar por fuera de la aplicación.

La coordinación final (horario exacto, llegada, pago de la cancha) se hace por WhatsApp. Fulvo solo conecta a las personas.

Además, después del partido los participantes se votan entre sí y al complejo, el organizador puede marcar ausencias (no-show) y cualquier usuario puede presentar un reclamo que resuelve un administrador.

## Documentación

- [`docs/consigna.pdf`](docs/consigna.pdf): consigna del trabajo práctico.
- [`docs/requerimientos.md`](docs/requerimientos.md): requerimientos del MVP e ideas post-MVP.
- [`docs/diagramas/`](docs/diagramas/): diagramas de secuencia y diagrama de clases (draw.io y SVG).
- [`docs/clases.md`](docs/clases.md): clases del dominio y patrones de diseño.
- [`CLAUDE.md`](CLAUDE.md): convenciones y decisiones del proyecto.

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


## Créditos

El stack y la estructura siguen el material de la cátedra en el repositorio https://rmatuk.github.io/prog2.

Integrantes:

- Agustín Sigales ([@aseasigal](https://github.com/aseasigal))
- Julián Rieznik ([@julianrieznik](https://github.com/julianrieznik))
- Tomás Sirne ([@tomassirne](https://github.com/tomassirne))
- Nicolás Vrancovich ([@nvranco](https://github.com/nvranco))

