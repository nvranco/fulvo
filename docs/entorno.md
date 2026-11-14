# Entorno de desarrollo — Fulvo (MVP)

Guía para dejar la máquina lista y que el proyecto corra igual en cualquier computadora. Sigue la [lección 01 de la cátedra](https://rmatuk.github.io/prog2/01/) hasta "Instalando las herramientas de desarrollo".

## Decisiones

- **Python 3.13** en todos lados (`.python-version`, `requires-python`, Dockerfile y CI). Se eligió una sola versión para evitar diferencias entre máquinas, contenedor y CI. La cátedra usa 3.12 en CI y 3.14 en el Dockerfile; acá se unifica.
- **Entorno virtual dentro del proyecto** (`.venv/`): el editor lo detecta solo y es fácil de borrar y recrear.
- `package-mode = false` en `pyproject.toml`: fulvo es una aplicación, no una librería, así que `poetry install` instala solo las dependencias. El `Dockerfile` también instala con Poetry, desde `poetry.lock`, para que la imagen tenga las mismas versiones que los tests.
- **Tests contra PostgreSQL real, no SQLite en memoria.** `testcontainers` levanta un `postgres:16` (la misma versión de `compose.yaml`) en un contenedor al empezar `poetry test` y lo borra al terminar. Por eso **Docker es obligatorio** para desarrollar y testear. Para `poetry serve` en local se sigue usando SQLite (`fulvo.db`).
- **Configuración local en `.env`**, que no se commitea. Cada máquina tiene su propia `SECRET_KEY` (paso 7).

## Prerrequisitos

| Herramienta | Para qué | Cómo instalar (Windows) |
|---|---|---|
| Python 3.13 | lenguaje | https://www.python.org/downloads/ o `poetry python install 3.13` (ver abajo) |
| Git | control de versiones | `winget install Git.Git` |
| GitHub CLI (opcional) | PRs y repo desde la terminal | `winget install GitHub.cli` |
| Docker Desktop | **obligatorio**: los tests levantan PostgreSQL en un contenedor, y `docker compose` corre la API con PostgreSQL. Tiene que estar abierto (corriendo de fondo) | `winget install -e --id Docker.DockerDesktop` |
| pipx | instalar Poetry aislado | ver abajo |
| Poetry | dependencias y entorno | ver abajo |

## Pasos

### 1. pipx

```bash
pip install --user pipx
pipx ensurepath
```

Reiniciar la terminal después de `ensurepath` para que el `PATH` se actualice.

### 2. Poetry

```bash
pipx install poetry
poetry --version
```

### 3. Poe the Poet (plugin de Poetry)

Se instala una vez por máquina, dentro del entorno de Poetry. Agrega las tareas (`poetry lint`, `poetry format`, `poetry test`, `poetry serve`) definidas en `pyproject.toml`:

```bash
pipx inject poetry 'poethepoet[poetry_plugin]'
```

### 4. Python 3.13 (solo si la máquina no lo tiene)

```bash
poetry python install 3.13
poetry python list
```

### 5. Entorno virtual local

Configuración global de Poetry, se hace una vez por máquina:

```bash
poetry config virtualenvs.in-project true
```

### 6. Clonar e instalar el proyecto

```bash
git clone https://github.com/nvranco/fulvo.git
cd fulvo
poetry env use 3.13
poetry install
```

`poetry install` lee `poetry.lock`, así que todos instalan exactamente las mismas versiones.

### 7. Crear el `.env`

`fulvo/settings.py` exige `SECRET_KEY`, la clave con la que se firman los tokens JWT. No tiene valor por defecto a propósito: una clave publicada en el repo permitiría falsificar tokens. Sin `.env` no arrancan la API, Alembic ni la carga inicial: fallan con `SECRET_KEY Field required`. Se hace una vez por máquina, desde la carpeta del proyecto.

```bash
cp .env.example .env
git status --short --ignored .env
```

El segundo comando tiene que mostrar `!! .env`: git lo ignora y no se va a commitear.

Generar una clave propia y una contraseña para el admin local:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

Abrir `.env` con el editor (`code .env` o `notepad .env`) y completar estas tres líneas, sin comillas ni espacios alrededor del `=`:

```
SECRET_KEY=la-clave-de-64-caracteres
ADMIN_EMAIL=admin@ejemplo.com
ADMIN_PASSWORD=la-contraseña-generada
```

- Cada integrante genera su propia clave. No se comparte ni se commitea.
- `ADMIN_EMAIL` y `ADMIN_PASSWORD` son opcionales. Sin ellas la carga inicial no crea un admin, y no se pueden probar las altas, ediciones y bajas de zonas y complejos.
- El resto de las variables queda como en `.env.example`.

Comprobar que se lee bien (el comando no muestra la clave):

```bash
poetry run python -c "from fulvo.settings import Settings; s = Settings(); print('SECRET_KEY:', len(s.SECRET_KEY), 'caracteres'); print('Admin:', s.ADMIN_EMAIL)"
```

Tiene que mostrar `SECRET_KEY: 64 caracteres` y el email del admin.

### 8. Crear la base y cargar los datos iniciales

```bash
poetry run alembic upgrade head
poetry run python -m fulvo.carga_inicial
```

Alembic crea las tablas, o agrega las que faltan si la base ya existía. La carga inicial crea los roles `usuario` y `admin`, las zonas y complejos del CSV y el admin del `.env`. Es idempotente: la segunda vez no duplica nada. Las zonas y los complejos los carga solo en una base sin zonas: después los maneja el admin con la API, y volver a correr la carga no deshace sus cambios. En una base nueva muestra:

```
Roles creados: 2.
Zonas creadas: 8. Complejos creados: 51.
Admin: creado.
```

Sin este paso, registrar un usuario da 500 porque falta el rol `usuario`.

### 9. Comprobar que funciona

```bash
poetry run fastapi dev fulvo/app.py
```

También funciona `poetry serve` (atajo definido en `pyproject.toml`). Abrir http://127.0.0.1:8000 (debe responder `{"mensaje": "Hola Mundo!"}`) y http://127.0.0.1:8000/docs (documentación automática). Cortar con `Ctrl+C`.

Para probar las rutas del admin desde `/docs`: botón **Authorize**, con `ADMIN_EMAIL` en `username` y `ADMIN_PASSWORD` en `password` (`client_id` y `client_secret` quedan vacíos). Sin autorizarse, `POST /zonas` da 401; con el admin, 201.

## Herramientas de desarrollo

Instaladas en el grupo `dev` de Poetry (`poetry add --group dev pytest pytest-cov ruff typos pytest-random-order`) y configuradas en `pyproject.toml`:

| Herramienta | Qué hace | Configuración |
|---|---|---|
| Ruff | linter y formateador (línea de 79, comillas simples, reglas `I F E W PL PT`) | `[tool.ruff*]` |
| Typos | revisa ortografía en inglés; excluye `*.md`, `docs`, `poetry.lock` y `migrations` porque están en español | `[tool.typos.files]` |
| pytest + pytest-cov | tests con cobertura del paquete `fulvo`, incluidas las ramas (`--cov-branch`) | `[tool.pytest]` |
| testcontainers | levanta un PostgreSQL 16 en Docker para los tests (fixture `engine` de `tests/conftest.py`) | `tests/conftest.py` |
| pytest-random-order | corre los tests en orden aleatorio (`--random-order`) para detectar tests que dependen de otros; imprime la semilla para repetir un orden | `[tool.pytest]` |
| Poe the Poet | tareas cortas | `[tool.poe.tasks]` |

Tareas:

```bash
poetry lint     # typos + ruff check
poetry format   # ruff check --fix + ruff format
poetry serve    # fastapi dev fulvo/app.py
poetry test     # lint + pytest con cobertura + reporte html (htmlcov/index.html)
```

Los tests siguen el patrón AAA (Organizar, Actuar, Afirmar). La fixture `client` vive en `tests/conftest.py` y el primer test (`tests/test_app.py`) comprueba la ruta `/`.

Antes de `poetry test`, Docker Desktop tiene que estar corriendo: la fixture `engine` levanta un PostgreSQL en un contenedor (la primera vez descarga la imagen `postgres:16`). Las tablas se crean y se borran en cada test, por eso la suite tarda unos 5 minutos.

Los tests no necesitan el `.env`: `tests/__init__.py` define una `SECRET_KEY` falsa antes de importar `fulvo`, y los tests de `Settings` lo ignoran con `_env_file=None`. Por eso el CI corre sin secrets.

Si typos marca una palabra en español dentro del código, se agrega la excepción en `[tool.typos.default]` en vez de renombrar (ya están `cliente` y `clientes`).

## Cómo se creó el proyecto (referencia)

La cátedra usa `poetry new --flat fast_zero`. Acá el repositorio ya existía, así que se crearon a mano los archivos equivalentes:

- `pyproject.toml` (formato PEP 621) con `requires-python = ">=3.13,<4.0"`.
- `fulvo/__init__.py` y `tests/__init__.py` vacíos.
- `poetry add 'fastapi[standard]'` para la primera dependencia.
- `fulvo/app.py` con el "Hola Mundo".

## Problemas comunes

- `poetry: command not found` tras instalar: no se reinició la terminal después de `pipx ensurepath`.
- Poetry usa otro Python: correr `poetry env use 3.13` y verificar con `poetry env info`.
- `docker: command not found`: abrir Docker Desktop una vez y reiniciar la terminal.
- `poetry test` falla al empezar con un error de conexión a Docker (por ejemplo `Error while fetching server API version` o `DockerException`): Docker Desktop no está abierto. Abrirlo, esperar a que diga que está corriendo y repetir.
- `SECRET_KEY Field required`: no hay `.env` en la carpeta desde la que se corre el comando, o quedó guardado como `.env.txt`. Correr los comandos desde la raíz del proyecto y revisar con `git status --short --ignored .env` (paso 7).
- Registrar un usuario da 500: faltan los roles. Correr `poetry run python -m fulvo.carga_inicial` (paso 8).
- `Admin: no creado (faltan ADMIN_EMAIL y ADMIN_PASSWORD)`: esas líneas faltan o están vacías en el `.env`.
- `Admin: ya existía` y no se recuerda la contraseña: la carga inicial no cambia la contraseña de un admin que ya existe. En desarrollo, borrar `fulvo.db` y repetir el paso 8.
