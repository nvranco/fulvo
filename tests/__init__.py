import os

# Este archivo corre antes que cualquier import de `fulvo`, y `Settings`
# exige SECRET_KEY. Es una clave falsa solo para tests; `setdefault` respeta
# una que ya esté definida en el entorno.
# Larga a propósito (64 bytes o más): pyjwt avisa si la clave es corta.
CLAVE_DE_PRUEBA = 'clave-solo-para-tests-' + 'x' * 64
os.environ.setdefault('SECRET_KEY', CLAVE_DE_PRUEBA)
