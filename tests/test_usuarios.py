from http import HTTPStatus

from sqlalchemy import select

from fulvo.models import EDAD_MINIMA, ROL_USUARIO, Usuario
from tests.datos import (
    EMAIL,
    cumple_en_un_dia,
    datos_de_registro,
    hoy_menos_anios,
)


def test_registrar_usuario_devuelve_creado_sin_datos_sensibles(client):
    # Actuar
    respuesta = client.post('/usuarios', json=datos_de_registro())

    # Afirmar
    assert respuesta.status_code == HTTPStatus.CREATED
    cuerpo = respuesta.json()
    assert cuerpo['email'] == EMAIL
    assert cuerpo['nombre'] == 'Ana'
    assert 'contrasena' not in cuerpo
    assert 'contrasena_hash' not in cuerpo
    assert 'whatsapp' not in cuerpo


def test_registrar_usuario_guarda_hash_y_rol_usuario(client, session):
    client.post('/usuarios', json=datos_de_registro())

    guardado = session.scalars(select(Usuario)).one()
    assert guardado.contrasena_hash != 'secreta123'
    assert guardado.contrasena_hash.startswith('$argon2')
    assert guardado.tiene_rol(ROL_USUARIO)
    assert guardado.bloqueado is False


def test_registrar_usuario_con_email_repetido_devuelve_conflicto(client):
    client.post('/usuarios', json=datos_de_registro())

    respuesta = client.post('/usuarios', json=datos_de_registro())

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'Ya existe un usuario con ese email'


def test_registrar_usuario_con_email_en_otras_mayusculas_es_conflicto(client):
    client.post('/usuarios', json=datos_de_registro())

    respuesta = client.post(
        '/usuarios', json=datos_de_registro(email='ANA@Ejemplo.com')
    )

    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_registrar_menor_de_16_devuelve_error_de_validacion(client, session):
    nacimiento = cumple_en_un_dia(EDAD_MINIMA).isoformat()

    respuesta = client.post(
        '/usuarios', json=datos_de_registro(fecha_nacimiento=nacimiento)
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert str(EDAD_MINIMA) in respuesta.json()['detail']
    assert session.scalars(select(Usuario)).all() == []


def test_registrar_con_exactamente_16_anios_es_valido(client):
    nacimiento = hoy_menos_anios(EDAD_MINIMA).isoformat()

    respuesta = client.post(
        '/usuarios', json=datos_de_registro(fecha_nacimiento=nacimiento)
    )

    assert respuesta.status_code == HTTPStatus.CREATED


def test_registrar_con_fecha_de_nacimiento_futura_es_rechazado(client):
    respuesta = client.post(
        '/usuarios',
        json=datos_de_registro(fecha_nacimiento='2999-01-01'),
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_registrar_con_email_invalido_devuelve_error_de_validacion(client):
    respuesta = client.post(
        '/usuarios', json=datos_de_registro(email='no-es-un-email')
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_registrar_con_contrasena_corta_devuelve_error_de_validacion(client):
    respuesta = client.post(
        '/usuarios', json=datos_de_registro(contrasena='corta')
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_registrar_no_deja_elegir_el_rol(client, session):
    # Un campo de más en el cuerpo no tiene efecto: el rol es `usuario`.
    client.post('/usuarios', json=datos_de_registro() | {'rol_id': 2})

    guardado = session.scalars(select(Usuario)).one()
    assert guardado.tiene_rol(ROL_USUARIO)
