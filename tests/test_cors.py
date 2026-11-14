"""CORS: desde qué orígenes un navegador puede usar la API.

Estos tests mandan lo mismo que un navegador: el encabezado `Origin` y,
antes de un pedido con el token o con JSON, un OPTIONS de consulta
(preflight). El origen permitido lo define `tests/__init__.py` en
CORS_ORIGINS, como lo haría el `.env` de quien levanta el front.
"""

from http import HTTPStatus

from tests import ORIGEN_DEL_FRONT

ORIGEN_AJENO = 'http://sitio-ajeno.test'


def consulta_previa(origen: str) -> dict[str, str]:
    """Encabezados del OPTIONS que manda el navegador antes del pedido real.

    Pide permiso para un POST con el token y con JSON, como haría el front
    al publicar un partido.
    """
    return {
        'Origin': origen,
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'authorization, content-type',
    }


def test_consulta_previa_del_front_permitido_da_permiso(client):
    respuesta = client.options(
        '/partidos', headers=consulta_previa(ORIGEN_DEL_FRONT)
    )

    assert respuesta.status_code == HTTPStatus.OK
    cabeceras = respuesta.headers
    assert cabeceras['access-control-allow-origin'] == ORIGEN_DEL_FRONT
    # Solo los métodos que usa la API: con `allow_methods=['*']` el
    # middleware también habilitaría otros, como HEAD u OPTIONS.
    metodos = cabeceras['access-control-allow-methods'].split(', ')
    assert set(metodos) == {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}
    encabezados_permitidos = cabeceras['access-control-allow-headers']
    assert 'authorization' in encabezados_permitidos.lower()


def test_consulta_previa_desde_otro_origen_se_rechaza(client):
    respuesta = client.options(
        '/partidos', headers=consulta_previa(ORIGEN_AJENO)
    )

    assert respuesta.status_code == HTTPStatus.BAD_REQUEST
    assert 'access-control-allow-origin' not in respuesta.headers


def test_pedido_del_front_permitido_lleva_el_permiso(client, token):
    respuesta = client.get(
        '/usuarios/yo',
        headers={
            'Origin': ORIGEN_DEL_FRONT,
            'Authorization': f'Bearer {token}',
        },
    )

    assert respuesta.status_code == HTTPStatus.OK
    permiso = respuesta.headers['access-control-allow-origin']
    assert permiso == ORIGEN_DEL_FRONT


def test_pedido_desde_otro_origen_responde_sin_el_permiso(client):
    respuesta = client.get('/zonas', headers={'Origin': ORIGEN_AJENO})

    # La API responde igual: CORS no la protege de otros clientes. Sin el
    # permiso, es el navegador el que no deja que la página lea la respuesta.
    assert respuesta.status_code == HTTPStatus.OK
    assert 'access-control-allow-origin' not in respuesta.headers
