from datetime import timedelta

import jwt
import pytest

from fulvo.security import (
    configuracion,
    crear_token_acceso,
    decodificar_token_acceso,
    hashear_contrasena,
    verificar_contrasena,
)


def test_el_hash_no_es_la_contrasena_y_es_argon2():
    contrasena = 'secreta123'

    contrasena_hash = hashear_contrasena(contrasena)

    assert contrasena_hash != contrasena
    assert contrasena_hash.startswith('$argon2')


def test_verificar_contrasena_correcta_devuelve_verdadero():
    contrasena_hash = hashear_contrasena('secreta123')

    assert verificar_contrasena('secreta123', contrasena_hash) is True


def test_verificar_contrasena_incorrecta_devuelve_falso():
    contrasena_hash = hashear_contrasena('secreta123')

    assert verificar_contrasena('otra-cosa', contrasena_hash) is False


def test_misma_contrasena_genera_hashes_distintos():
    # Cada hash lleva su propia sal.
    assert hashear_contrasena('secreta123') != hashear_contrasena('secreta123')


def test_token_conserva_los_datos_y_agrega_vencimiento():
    datos = {'sub': 'ana@ejemplo.com'}

    token = crear_token_acceso(datos)
    decodificado = decodificar_token_acceso(token)

    assert decodificado['sub'] == 'ana@ejemplo.com'
    assert 'exp' in decodificado
    assert 'exp' not in datos  # no se modifica el diccionario original


def test_token_vencido_levanta_excepcion():
    token = crear_token_acceso(
        {'sub': 'ana@ejemplo.com'}, expira_en=timedelta(minutes=-1)
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decodificar_token_acceso(token)


def test_token_firmado_con_otra_clave_levanta_excepcion():
    falso = jwt.encode(
        {'sub': 'ana@ejemplo.com'},
        'otra-clave-distinta-de-al-menos-32-bytes',
        algorithm='HS256',
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decodificar_token_acceso(falso)


def test_token_mal_formado_levanta_excepcion():
    with pytest.raises(jwt.DecodeError):
        decodificar_token_acceso('esto-no-es-un-token')


def test_token_con_otro_algoritmo_es_rechazado():
    # Un token firmado con HS512 no se acepta aunque la clave sea la nuestra.
    otro = jwt.encode(
        {'sub': 'x'}, configuracion.SECRET_KEY, algorithm='HS512'
    )

    with pytest.raises(jwt.InvalidAlgorithmError):
        decodificar_token_acceso(otro)
