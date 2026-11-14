#!/bin/bash
# Arranque del contenedor: prepara la base y después levanta la API.

# Si un paso falla, el script se corta y el contenedor no arranca: es
# mejor un error visible que una API corriendo sin tablas o sin roles.
set -e

# 1. Crea o actualiza las tablas hasta la última migración.
alembic upgrade head

# 2. Carga los roles y el primer admin si faltan, y las zonas y complejos
# del CSV solo la primera vez (en una base sin zonas). En un reinicio no
# duplica nada ni vuelve a crear lo que el admin borró o renombró.
python -m fulvo.carga_inicial

# 3. Levanta la API. `exec` reemplaza este script por uvicorn, así las
# señales de Docker (por ejemplo al hacer stop) le llegan directo.
# 0.0.0.0 para que se pueda acceder desde fuera del contenedor.
exec uvicorn --host 0.0.0.0 --port 8000 fulvo.app:app
