# Se construye en dos etapas: la primera arma el entorno con Poetry y la
# segunda, la que se despliega, solo copia ese entorno. Así la imagen final
# tiene exactamente lo que fija poetry.lock y no lleva Poetry adentro.

# --- Etapa 1: dependencias ---------------------------------------------------
# Misma versión de Python que en local y en CI (CLAUDE.md, sección 4).
FROM python:3.13-slim AS dependencias

WORKDIR /app

# Poetry crea el entorno en /app/.venv, igual que en las máquinas del grupo
# (virtualenvs.in-project), e instala lo que fija poetry.lock. Solo el grupo
# principal: pytest, ruff y testcontainers no hacen falta para correr la API.
# --no-root porque fulvo no se instala como paquete (package-mode = false).
RUN pip install --no-cache-dir poetry==2.5.1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

# --- Etapa 2: la imagen que se despliega ------------------------------------
FROM python:3.13-slim

# Sin archivos .pyc y con la salida de Python sin buffer, para ver los logs
# del contenedor en el momento.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Se copia el entorno ya armado. Tiene que quedar en la misma ruta que en la
# etapa 1 (/app/.venv), porque sus ejecutables apuntan a esa ruta. Con el
# PATH, `alembic`, `python` y `uvicorn` de entrypoint.sh salen del entorno.
COPY --from=dependencias /app/.venv ./.venv
ENV PATH="/app/.venv/bin:$PATH"

# Se copia solo lo que la API necesita, archivo por archivo, en vez de
# `COPY . .`: así nunca entran a la imagen el `.env` (con la SECRET_KEY),
# el `.venv` local, la base `fulvo.db` ni los reportes de cobertura.
COPY alembic.ini entrypoint.sh ./
COPY fulvo ./fulvo
COPY migrations ./migrations

# En Windows git no guarda el permiso de ejecución: se da acá.
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
