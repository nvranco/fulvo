from http import HTTPStatus

import pytest

# Las cinco rutas de escritura que solo puede usar el admin (RQ10):
# (método, ruta, cuerpo, código que devuelve cuando el pedido sale bien).
ZONA = {'nombre': 'Colegiales', 'provincia': 'CABA'}
COMPLEJO = {
    'zona': 'Belgrano',
    'localidad': 'Belgrano',
    'nombre': 'Cancha de Prueba',
    'direccion': 'Calle Falsa 123',
    'tipo': 'Campo de fútbol',
    'latitud': -34.56,
    'longitud': -58.45,
}
RUTAS_DE_ADMIN = [
    ('POST', '/zonas', ZONA, HTTPStatus.CREATED),
    ('PUT', '/zonas/1', ZONA, HTTPStatus.OK),
    ('POST', '/complejos', COMPLEJO, HTTPStatus.CREATED),
    ('PUT', '/complejos/1', COMPLEJO, HTTPStatus.OK),
    ('DELETE', '/complejos/1', None, HTTPStatus.OK),
]


@pytest.mark.parametrize(('metodo', 'ruta', 'cuerpo', 'exito'), RUTAS_DE_ADMIN)
def test_admin_puede_usar_las_rutas_de_escritura(
    client_admin, metodo, ruta, cuerpo, exito
):
    respuesta = client_admin.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == exito


@pytest.mark.parametrize(('metodo', 'ruta', 'cuerpo', 'exito'), RUTAS_DE_ADMIN)
def test_usuario_comun_recibe_prohibido_en_las_rutas_de_escritura(
    client_usuario, metodo, ruta, cuerpo, exito
):
    respuesta = client_usuario.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Esta acción es solo para administradores'
    )


@pytest.mark.parametrize(('metodo', 'ruta', 'cuerpo', 'exito'), RUTAS_DE_ADMIN)
def test_sin_token_recibe_no_autenticado_en_las_rutas_de_escritura(
    client, metodo, ruta, cuerpo, exito
):
    respuesta = client.request(metodo, ruta, json=cuerpo)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_usuario_comun_no_logra_borrar_un_complejo(client_usuario):
    client_usuario.delete('/complejos/1')

    # Afirmar que el 403 no tuvo efecto: el complejo sigue existiendo.
    assert client_usuario.get('/complejos/1').status_code == HTTPStatus.OK


def test_las_lecturas_siguen_abiertas_sin_token(client):
    assert client.get('/zonas').status_code == HTTPStatus.OK
    assert client.get('/complejos').status_code == HTTPStatus.OK
    assert client.get('/complejos/1').status_code == HTTPStatus.OK
