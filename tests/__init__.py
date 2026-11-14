import json
import os

# Este archivo corre antes que cualquier import de `fulvo`, y `Settings`
# exige SECRET_KEY. Es una clave falsa solo para tests; `setdefault` respeta
# una que ya esté definida en el entorno.
# Larga a propósito (64 bytes o más): pyjwt avisa si la clave es corta.
CLAVE_DE_PRUEBA = 'clave-solo-para-tests-' + 'x' * 64
os.environ.setdefault('SECRET_KEY', CLAVE_DE_PRUEBA)

# Origen del front que permiten los tests de CORS (`tests/test_cors.py`),
# como lo haría el `.env` de quien levanta el front. Se asigna sin
# `setdefault`: esos tests comprueban justo este origen, y otro definido en
# el entorno de la máquina los haría fallar.
ORIGEN_DEL_FRONT = 'http://localhost:5173'
os.environ['CORS_ORIGINS'] = json.dumps([ORIGEN_DEL_FRONT])
