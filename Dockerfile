# Misma versión de Python que en local y en CI (CLAUDE.md, sección 4).
# "slim" es la imagen oficial sin herramientas extra: pesa mucho menos.
FROM python:3.13-slim

# Sin archivos .pyc y con la salida de Python sin buffer, para ver los logs
# del contenedor en el momento.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Se copia solo lo que la API necesita, archivo por archivo, en vez de
# `COPY . .`: así nunca entran a la imagen el `.env` (con la SECRET_KEY),
# el `.venv`, la base local `fulvo.db` ni los reportes de cobertura.
# README.md hace falta porque pyproject.toml lo declara como `readme`.
COPY pyproject.toml poetry.lock README.md alembic.ini entrypoint.sh ./
COPY fulvo ./fulvo
COPY migrations ./migrations

# Se instala con pip, sin Poetry: pip lee las dependencias de [project] en
# pyproject.toml (formato PEP 621) y usa poetry-core solo para armar el
# paquete. Instala únicamente las dependencias principales, no las de dev
# (pytest, ruff, testcontainers), que en producción no hacen falta.
RUN pip install --no-cache-dir .

# En Windows git no guarda el permiso de ejecución: se da acá.
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
