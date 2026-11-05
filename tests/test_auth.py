from datetime import timedelta
from http import HTTPStatus

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fulvo.database import get_session
from fulvo.security import UsuarioActual, crear_token_acceso
from tests.datos import CONTRASENA, EMAIL, datos_de_registro

MENSAJE_GENERICO = 'Email o contraseña incorrectos'


def iniciar_sesion(client, email=EMAIL, contrasena=CONTRASENA):
    # OAuth2 manda un formulario, no JSON; el email va en `username`.
    return client.post(
        '/auth/token', data={'username': email, 'password': contrasena}
    )


def test_login_correcto_devuelve_un_token_bearer(client, usuario):
    respuesta = iniciar_sesion(client)

    assert respuesta.status_code == HTTPStatus.OK
    cuerpo = respuesta.json()
    assert cuerpo['token_type'] == 'bearer'
    assert cuerpo['access_token']


def test_login_acepta_el_email_en_otras_mayusculas(client, usuario):
    respuesta = iniciar_sesion(client, email='ANA@ejemplo.COM')

    assert respuesta.status_code == HTTPStatus.OK


def test_login_con_contrasena_incorrecta_devuelve_mensaje_generico(
    client, usuario
):
    respuesta = iniciar_sesion(client, contrasena='incorrecta')

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED
    assert respuesta.json()['detail'] == MENSAJE_GENERICO


def test_login_con_email_inexistente_devuelve_el_mismo_mensaje(client):
    respuesta = iniciar_sesion(client, email='nadie@ejemplo.com')

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED
    assert respuesta.json()['detail'] == MENSAJE_GENERICO


def test_login_de_usuario_bloqueado_devuelve_el_mismo_mensaje(
    client, session, usuario
):
    usuario.bloqueado = True
    session.commit()

    # La contraseña es correcta: aun así no entra, y no se le dice por qué.
    respuesta = iniciar_sesion(client)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED
    assert respuesta.json()['detail'] == MENSAJE_GENERICO


def test_registro_y_login_de_un_usuario_nuevo(client):
    # Flujo completo de RQ1: primero el registro y después el login.
    client.post('/usuarios', json=datos_de_registro())

    respuesta = iniciar_sesion(client)

    assert respuesta.status_code == HTTPStatus.OK


# --- UsuarioActual -------------------------------------------------------
# Todavía no hay una ruta real protegida, así que se prueba la dependencia
# en una app mínima armada solo para estos tests.


@pytest.fixture
def cliente_protegido(session):
    app = FastAPI()

    @app.get('/protegida')
    def ruta_protegida(usuario: UsuarioActual):
        return {'email': usuario.email}

    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def con_token(token):
    return {'Authorization': f'Bearer {token}'}


def test_usuario_actual_con_token_valido_devuelve_al_usuario(
    cliente_protegido, usuario, token
):
    respuesta = cliente_protegido.get('/protegida', headers=con_token(token))

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {'email': EMAIL}


def test_usuario_actual_sin_token_devuelve_no_autenticado(cliente_protegido):
    respuesta = cliente_protegido.get('/protegida')

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_actual_con_token_invalido_devuelve_no_autenticado(
    cliente_protegido,
):
    respuesta = cliente_protegido.get(
        '/protegida', headers=con_token('esto-no-es-un-token')
    )

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_actual_con_token_vencido_devuelve_no_autenticado(
    cliente_protegido, usuario
):
    vencido = crear_token_acceso({'sub': EMAIL}, timedelta(minutes=-1))

    respuesta = cliente_protegido.get('/protegida', headers=con_token(vencido))

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_actual_con_token_sin_sub_devuelve_no_autenticado(
    cliente_protegido, usuario
):
    sin_sub = crear_token_acceso({'otro': 'dato'})

    respuesta = cliente_protegido.get('/protegida', headers=con_token(sin_sub))

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_actual_de_usuario_inexistente_devuelve_no_autenticado(
    cliente_protegido, usuario
):
    de_otro = crear_token_acceso({'sub': 'nadie@ejemplo.com'})

    respuesta = cliente_protegido.get('/protegida', headers=con_token(de_otro))

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_actual_bloqueado_con_token_valido_devuelve_prohibido(
    cliente_protegido, session, usuario, token
):
    # El bloqueo vale aunque el token siga sin vencer.
    usuario.bloqueado = True
    session.commit()

    respuesta = cliente_protegido.get('/protegida', headers=con_token(token))

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
