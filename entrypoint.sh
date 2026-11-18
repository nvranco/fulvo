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
#
# --proxy-headers y --forwarded-allow-ips: en Render el HTTPS lo atiende el
# proxy de Render, que le pasa el pedido a uvicorn por HTTP y avisa en el
# encabezado X-Forwarded-Proto que el original era HTTPS. Uvicorn solo cree
# ese encabezado si viene de una IP permitida; si no, arma las URLs con
# http:// (por ejemplo las redirecciones), y el navegador las bloquea o
# pierde el HTTPS. Se permite '*' porque al contenedor solo llega el proxy
# de Render. Va entre comillas para que bash no lo tome como comodín.
exec uvicorn --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips='*' \
    fulvo.app:app
