# Entorno de desarrollo — Fulvo (MVP)

Guía para dejar la máquina lista y que el proyecto corra igual en cualquier computadora. Sigue la [lección 01 de la cátedra](https://rmatuk.github.io/prog2/01/) hasta "Instalando las herramientas de desarrollo".

## Decisiones

- **Python 3.13** en todos lados (`.python-version`, `requires-python`, Dockerfile y CI). Se eligió una sola versión para evitar diferencias entre máquinas, contenedor y CI. La cátedra usa 3.12 en CI y 3.14 en el Dockerfile; acá se unifica.
- **Entorno virtual dentro del proyecto** (`.venv/`): el editor lo detecta solo y es fácil de borrar y recrear.
- `package-mode = false` en `pyproject.toml`: fulvo es una aplicación, no una librería que se publica.

## Prerrequisitos

| Herramienta | Para qué | Cómo instalar (Windows) |
|---|---|---|
| Python 3.13 | lenguaje | https://www.python.org/downloads/ o `poetry python install 3.13` (ver abajo) |
| Git | control de versiones | `winget install Git.Git` |
| GitHub CLI (opcional) | PRs y repo desde la terminal | `winget install GitHub.cli` |
| Docker Desktop | contenedores (se usa más adelante) | `winget install -e --id Docker.DockerDesktop` |
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

### 3. Python 3.13 (solo si la máquina no lo tiene)

```bash
poetry python install 3.13
poetry python list
```

### 4. Entorno virtual local

Configuración global de Poetry, se hace una vez por máquina:

```bash
poetry config virtualenvs.in-project true
```

### 5. Clonar e instalar el proyecto

```bash
git clone https://github.com/nvranco/fulvo.git
cd fulvo
poetry env use 3.13
poetry install
```

`poetry install` lee `poetry.lock`, así que todos instalan exactamente las mismas versiones.

### 6. Comprobar que funciona

```bash
poetry run fastapi dev fulvo/app.py
```

Abrir http://127.0.0.1:8000 (debe responder `{"mensaje": "Hola Mundo!"}`) y http://127.0.0.1:8000/docs (documentación automática). Cortar con `Ctrl+C`.

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
