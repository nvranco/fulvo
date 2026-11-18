

# fulvo

<p align="center">
  <img src="docs/img/fulvo.png" alt="fulvo?" width="300">
</p>

Aplicación para completar equipos de fútbol. 

Proyecto final de la materia **Programación II** de la **Licenciatura en Ciencia de Datos** de la **UNSAM**.

**API publicada:** https://fulvo-api.onrender.com, con la documentación interactiva en https://fulvo-api.onrender.com/docs. Está en el plan gratis de Render: si nadie la usó en los últimos 15 minutos, el primer pedido tarda cerca de un minuto mientras arranca. Ver [Deploy en Render](#deploy-en-render).

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
- [`docs/diagramas/`](docs/diagramas/): diagramas de secuencia y diagrama de clases UML ([`clases.svg`](docs/diagramas/clases.svg), editable en [`clases.drawio`](docs/diagramas/clases.drawio)).
- [`docs/clases.md`](docs/clases.md): clases del dominio y patrones de diseño (Observer y Factory).
- [`docs/base-de-datos.md`](docs/base-de-datos.md): esquema de la base de datos (10 tablas: zonas, complejos, roles, usuarios, partidos, postulaciones, notificaciones, votaciones, sanciones y reclamos) y decisiones de diseño.
- [`docs/entorno.md`](docs/entorno.md): cómo preparar la máquina para desarrollar.
- [`CLAUDE.md`](CLAUDE.md): convenciones y decisiones del proyecto.

## Stack

Se usa el stack de la cátedra:

- **FastAPI** como framework de la API
- **SQLAlchemy** (síncrono) y **Alembic** para base de datos y migraciones
- **JWT** (`pyjwt`) y **argon2** (`pwdlib`) para autenticación segura
- **SQLite** en desarrollo y **PostgreSQL** en contenedor y producción
- **pytest** para los tests
- **Ruff** y **Typos** para calidad de código
- **Poetry** y **poethepoet** para dependencias y tareas
- **Docker** y **Docker Compose**
- **GitHub Actions** para la integración continua
- **Render** para el deploy (la cátedra usa Fly.io; el porqué del cambio está en [Deploy en Render](#deploy-en-render))

## Librerías

Están declaradas en `pyproject.toml`, y las versiones exactas, en `poetry.lock`: `poetry install` instala esas mismas, y la imagen de Docker también.

Las que necesita la API para correr:

| Librería | Para qué |
|---|---|
| `fastapi[standard]` | Framework de la API: rutas, validación de los datos con Pydantic y documentación automática en `/docs`. El extra `standard` trae el servidor (`uvicorn`), el comando `fastapi dev`, `python-multipart` (para el formulario del login) y `email-validator` (para validar los emails). |
| `sqlalchemy` | ORM, en modo síncrono: cada modelo de `fulvo/models.py` es a la vez una clase del dominio y una tabla. |
| `alembic` | Migraciones: crea y actualiza las tablas (`alembic upgrade head`). |
| `pydantic-settings` | Lee la configuración (`DATABASE_URL`, `SECRET_KEY` y demás) del `.env` o de variables de entorno. |
| `psycopg[binary]` | Driver de PostgreSQL, la base del contenedor, de los tests y de producción. |
| `pyjwt` | Firma y verifica los tokens JWT de la sesión. |
| `pwdlib[argon2]` | Guarda las contraseñas como hash argon2, nunca en claro. |

Las de desarrollo (grupo `dev`), para testear y revisar el código:

| Librería | Para qué |
|---|---|
| `pytest` | Corre los tests. |
| `pytest-cov` | Mide la cobertura de los tests, incluidas las ramas de cada `if`. |
| `pytest-random-order` | Corre los tests en orden aleatorio, para que ninguno dependa de otro. |
| `factory-boy` | Arma usuarios y partidos de prueba (`tests/factories.py`). |
| `freezegun` | Fija el reloj en los tests que dependen de la hora: tokens vencidos o partidos que terminan. |
| `testcontainers` | Levanta un PostgreSQL 16 en Docker para que los tests usen la misma base que producción. |
| `ruff` | Linter y formateador. |
| `typos` | Revisa la ortografía del código. |

Fuera de `pyproject.toml` hacen falta Poetry (que maneja las dependencias y el entorno virtual), su plugin `poethepoet` (las tareas `poetry serve`, `poetry lint`, `poetry format` y `poetry test`) y Docker Desktop. Cómo instalarlos: [`docs/entorno.md`](docs/entorno.md).

## Cómo correrlo

Prerrequisitos: Python 3.13, Git, Docker, pipx y Poetry. Guía completa en [`docs/entorno.md`](docs/entorno.md).

```bash
git clone https://github.com/nvranco/fulvo.git
cd fulvo
poetry config virtualenvs.in-project true
poetry env use 3.13
poetry install
pipx inject poetry 'poethepoet[poetry_plugin]'
cp .env.example .env                       # y completar SECRET_KEY (ver abajo)
poetry run alembic upgrade head            # crea las tablas
poetry run python -m fulvo.carga_inicial   # roles, zonas, complejos y admin
poetry serve
```

**El `.env` es obligatorio.** `fulvo/settings.py` exige `SECRET_KEY`, la clave con la que se firman los tokens JWT, y no le da un valor por defecto a propósito: una clave publicada en el repo permitiría falsificar tokens. Sin `.env` no arrancan la API, Alembic ni la carga inicial: fallan con `SECRET_KEY Field required`.

Cada integrante genera su propia clave y la pega en `SECRET_KEY` dentro del `.env`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Para tener un usuario admin local, completar también `ADMIN_EMAIL` y `ADMIN_PASSWORD`: la carga inicial lo crea. El `.env` no se commitea (está en `.gitignore`). Los pasos detallados están en [`docs/entorno.md`](docs/entorno.md#7-crear-el-env).

Para usar la API desde un front web que corre en otra dirección (por ejemplo, Vite en `http://localhost:5173`), agregar esa dirección en `CORS_ORIGINS` dentro del `.env`, como lista JSON: `CORS_ORIGINS=["http://localhost:5173"]`. Por defecto la lista está vacía y el navegador no deja que una página de otra dirección lea las respuestas de la API (CORS). Swagger, Postman y curl no la necesitan.

Otras tareas: `poetry lint`, `poetry format` y `poetry test`. **`poetry test` necesita Docker Desktop abierto**: los tests corren contra un PostgreSQL 16 que levanta `testcontainers` en un contenedor y borra al terminar (la suite tarda unos 5 minutos). Los tests no necesitan el `.env`: usan una clave falsa definida en `tests/__init__.py`.

La API queda en http://127.0.0.1:8000 y la documentación automática en http://127.0.0.1:8000/docs.

### Con Docker

Levanta la API y un PostgreSQL 16 en contenedores, como en producción. Solo hace falta Docker Desktop abierto y el `.env` con `SECRET_KEY` (no hace falta Poetry):

```bash
cp .env.example .env         # y completar SECRET_KEY (ver arriba)
docker compose up --build
```

- `compose.yaml` arma dos servicios: la base (`fulvo_database`), con un volumen para que los datos queden entre corridas, y la API (`fulvo_app`), que espera a que la base acepte conexiones.
- Al arrancar, `entrypoint.sh` aplica las migraciones, corre la carga inicial y levanta la API en http://127.0.0.1:8000. La carga crea los roles y el admin si faltan, y las zonas y complejos del CSV solo la primera vez (en una base sin zonas): un reinicio no duplica nada ni deshace lo que el admin editó o borró.
- La `SECRET_KEY` sale del `.env`: si falta, `docker compose up` avisa y no arranca. Con `ADMIN_EMAIL` y `ADMIN_PASSWORD` la carga inicial crea el admin, y `CORS_ORIGINS` también sale de ahí. La `DATABASE_URL` del `.env` no se usa acá: `compose.yaml` apunta a la base del contenedor.
- `docker compose down` apaga los contenedores y conserva la base; `docker compose down -v` también la borra.
- La imagen instala exactamente las versiones de `poetry.lock`, así corre lo mismo que se testea. Se arma en dos etapas: Poetry instala las dependencias en la primera, y la imagen final copia solo ese entorno, sin Poetry (ver los comentarios del `Dockerfile`).

## Deploy en Render

La API está publicada en **https://fulvo-api.onrender.com** (documentación en [`/docs`](https://fulvo-api.onrender.com/docs)), con una base PostgreSQL 16 de Render.

**Por qué Render y no Fly.io**, que es lo que usa la cátedra: Fly.io ya no tiene plan gratis. En una cuenta sin tarjeta apaga cada máquina a los 5 minutos, y no acepta tarjetas prepagas. Render tiene plan gratis para la API y para la base. La imagen es la misma que la de `docker compose`: Render la construye con el mismo `Dockerfile` y arranca con el mismo `entrypoint.sh`.

[`render.yaml`](render.yaml) describe los dos recursos. Render lo lee del repositorio y los crea:

- **`fulvo-db`**: PostgreSQL 16, plan gratis. No acepta conexiones desde afuera de Render; la API la usa por la red interna.
- **`fulvo-api`**: la API en Docker, plan gratis (512 MB y una sola instancia). Al arrancar aplica las migraciones y la carga inicial. Render la da por viva cuando `GET /` responde.

### Cómo desplegarla desde cero

1. Entrar a https://render.com con la cuenta de GitHub. El plan gratis no pide tarjeta.
2. **New** → **Blueprint** → elegir este repositorio y la rama a desplegar. Render lee `render.yaml` y muestra los dos recursos.
3. Completar los valores que pide:
   - `ADMIN_EMAIL` y `ADMIN_PASSWORD`, el admin que crea la carga inicial.
   - `SECRET_KEY` no hace falta: Render la genera al azar.
4. **Apply**. El primer arranque de la API todavía no tiene base: usa SQLite, el valor por defecto, y se descarta en el paso siguiente.
5. Cuando `fulvo-db` diga *Available*:
   1. Ir a **Connect** → **Internal** y copiar la *Internal Database URL*.
   2. Cambiarle el prefijo `postgresql://` por **`postgresql+psycopg://`**. Con `postgresql://`, SQLAlchemy busca el driver `psycopg2`, que no está instalado (el proyecto usa `psycopg`), y la API no arranca.
   3. En `fulvo-api` → **Environment**, agregar la variable `DATABASE_URL` con esa URL.
   4. **Save, rebuild, and deploy**.
6. En **Logs** tienen que aparecer:
   - las migraciones de Alembic;
   - `Roles creados: 2.`
   - `Zonas creadas: 8. Complejos creados: 51.`
   - `Admin: creado.`
   - `Your service is live`.

Cada push a la rama del Blueprint vuelve a desplegar la API. Un redeploy no duplica datos: las migraciones ya aplicadas no se repiten y la carga inicial solo crea lo que falta.

**Límites del plan gratis:**
- La API se duerme a los 15 minutos sin tráfico, y el pedido que la despierta tarda cerca de un minuto.
- Tiene 0,1 CPU, así que el login tarda unos segundos: argon2 es lento a propósito.
- La base gratis vence a los 30 días de creada.

## Probar la API

### Desde el navegador

Con la API levantada (con Poetry o con Docker), http://127.0.0.1:8000/docs muestra todos los endpoints y permite probarlos. Sin instalar nada, lo mismo está en la API publicada: https://fulvo-api.onrender.com/docs. Para los que piden sesión, el botón **Authorize** pide el email en `username` y la contraseña en `password` (`client_id` y `client_secret` quedan vacíos). Con el admin del `.env` se prueban también las rutas de administración.

### Un recorrido con curl

Prueba la idea del MVP de punta a punta: Ana publica un partido, Beto se postula, Ana lo acepta y los dos se ven el WhatsApp. Los comandos son para bash (en Windows, Git Bash) y usan Python para leer el token del login. Sobre una base recién creada, el partido y la postulación tienen id 1; si no, hay que usar el `id` que devuelve cada respuesta. Contra la API publicada, el recorrido es el mismo con `API=https://fulvo-api.onrender.com`. Ojo: ahí los datos quedan guardados, así que el segundo intento de registrar a Ana da 409.

```bash
API=http://127.0.0.1:8000

# 1. Registrarse (RQ1). Responde 201, sin la contraseña ni el WhatsApp.
curl -s -X POST $API/usuarios -H 'Content-Type: application/json' \
  -d '{"email": "ana@ejemplo.com", "contrasena": "clave-de-ana", "nombre": "Ana",
       "apellido": "Gomez", "whatsapp": "+54 9 11 1111-1111",
       "fecha_nacimiento": "1998-04-02", "posicion": "defensora"}'
curl -s -X POST $API/usuarios -H 'Content-Type: application/json' \
  -d '{"email": "beto@ejemplo.com", "contrasena": "clave-de-beto", "nombre": "Beto",
       "apellido": "Ruiz", "whatsapp": "+54 9 11 2222-2222",
       "fecha_nacimiento": "2001-09-15", "posicion": "delantero"}'

# 2. Iniciar sesión (RQ1). Es un formulario OAuth2, con el email en username.
token() {
  curl -s -X POST $API/auth/token -d "username=$1" -d "password=$2" |
    python -c "import json, sys; print(json.load(sys.stdin)['access_token'])"
}
ANA=$(token ana@ejemplo.com clave-de-ana)
BETO=$(token beto@ejemplo.com clave-de-beto)

# 3. Complejos a menos de 2 km de un punto de Belgrano (RQ3). No pide sesión.
curl -s "$API/complejos/cercanos?latitud=-34.5627&longitud=-58.4565&radio_km=2"

# 4. Ana publica un partido de fútbol 5 al que le falta un jugador (RQ4).
curl -s -X POST $API/partidos -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' \
  -d '{"complejo_id": 1, "inicio": "2030-03-01T20:00:00", "tipo": "F5", "cupos_faltantes": 1}'

# 5. Beto busca partidos abiertos de fútbol 5 y se postula (RQ5).
curl -s "$API/partidos?tipo=F5" -H "Authorization: Bearer $BETO"
curl -s -X POST $API/partidos/1/postulaciones -H "Authorization: Bearer $BETO"

# 6. Ana ve la lista de espera y acepta a Beto (RQ6). La respuesta trae el WhatsApp de Beto.
curl -s $API/partidos/1/postulaciones -H "Authorization: Bearer $ANA"
curl -s -X PATCH $API/partidos/1/postulaciones/1 -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' -d '{"estado": "aceptada"}'

# 7. Beto ve el WhatsApp de Ana en sus postulaciones, y el aviso en sus notificaciones (RQ9).
curl -s $API/postulaciones -H "Authorization: Bearer $BETO"
curl -s $API/notificaciones -H "Authorization: Bearer $BETO"
```

Algunos errores para probar: registrarse de nuevo con el mismo email da 409, una fecha de nacimiento de hace menos de 16 años da 422, postularse dos veces al mismo partido da 409, y `GET /usuarios/yo` sin token da 401.

### Endpoints

| RQ | Endpoint | Qué hace | Quién |
|---|---|---|---|
| RQ1 | `POST /usuarios` | Registrarse | cualquiera |
| RQ1 | `POST /auth/token` | Iniciar sesión (formulario, con el email en `username`) | cualquiera |
| RQ2 | `GET /usuarios/yo`, `PATCH /usuarios/yo` | Ver y editar el perfil propio, con la deuda de votaciones | usuario |
| RQ2 | `GET /usuarios/{id}` | Perfil público de otro usuario | usuario |
| RQ3 | `GET /zonas`, `GET /complejos`, `GET /complejos/{id}` | Zonas y complejos (filtro `zona`) | cualquiera |
| RQ3 | `GET /complejos/cercanos` | Complejos a menos de `radio_km` de un punto, del más cercano al más lejano | cualquiera |
| RQ4 | `POST /partidos`, `GET /partidos/{id}` | Publicar un partido y verlo | usuario |
| RQ5 | `GET /partidos` | Partidos abiertos que no empezaron (filtros `zona`, `complejo_id` y `tipo`) | usuario |
| RQ5 | `POST /partidos/{id}/postulaciones`, `GET /postulaciones` | Postularse y ver las postulaciones propias | usuario |
| RQ6 | `GET /partidos/{id}/postulaciones` | Lista de espera, ordenada por puntuación | organizador |
| RQ6 a RQ8 | `PATCH /partidos/{id}/postulaciones/{id}` | Aceptar, rechazar o revocar (`{"estado": ...}`), o marcar un no-show (`{"no_show": true}`) | organizador |
| RQ7 | `PATCH /postulaciones/{id}` | Retirarse o bajarse (`{"estado": "retirada"}`) | el jugador |
| RQ7 | `PATCH /partidos/{id}` | Cancelar el partido (`{"estado": "cancelado"}`) | organizador |
| RQ8 | `GET /votaciones`, `PATCH /votaciones/{id}` | Votaciones propias, y votar de 0 a 5 estrellas (`{"estrellas": n}`) | usuario |
| RQ9 | `GET /notificaciones`, `PATCH /notificaciones/{id}` | Avisos propios, y marcarlos como leídos (`{"leida": true}`) | usuario |
| RQ10 | `POST /zonas`, `PUT /zonas/{id}`, `POST /complejos`, `PUT /complejos/{id}`, `DELETE /complejos/{id}` | Cargar y editar zonas y complejos | admin |
| RQ10 | `POST /usuarios/{id}/sanciones`, `GET /usuarios/{id}/sanciones`, `PATCH /usuarios/{id}/sanciones/{id}` | Bloquear a un usuario (`{"motivo": ...}`), ver su historial y desbloquearlo (`{"activa": false}`) | admin |
| RQ11 | `POST /reclamos`, `GET /reclamos` | Reclamar por un no-show o una votación, o denunciar a un usuario o un complejo, y ver los reclamos propios | usuario |
| RQ11 | `PATCH /reclamos/{id}` | Resolver o rechazar un reclamo (`{"estado": ..., "resolucion": ...}`) | admin |
| RQ11 | `GET /votaciones?recibidas=true` | Votos recibidos, sin saber quién votó | usuario |

Las reglas de cada requerimiento, con sus errores, están en [`docs/requerimientos.md`](docs/requerimientos.md), y qué tests cubren cada uno, en la sección 3 de [`CLAUDE.md`](CLAUDE.md).

## Créditos

El stack y la estructura siguen el material de la cátedra: el sitio https://rmatuk.github.io/prog2/ y el código de cada clase en el repositorio https://github.com/rmatuk/prog2.

Integrantes:

- Agustín Sigales ([@aseasigal](https://github.com/aseasigal))
- Julián Rieznik ([@julianrieznik](https://github.com/julianrieznik))
- Tomás Sirne ([@tomassirne](https://github.com/tomassirne))
- Nicolás Vrancovich ([@nvranco](https://github.com/nvranco))

