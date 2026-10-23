from http import HTTPStatus


def test_raiz_devuelve_ok_y_hola_mundo(client):
    # Organizar: el cliente llega armado desde la fixture de conftest.py

    # Actuar
    respuesta = client.get('/')

    # Afirmar
    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == {'mensaje': 'Hola Mundo!'}
