from http import HTTPStatus

import pytest

from fulvo.models import EDAD_MINIMA, ROL_ADMIN
from tests.datos import EMAIL, cumple_en_un_dia, hoy_menos_anios

MI_PERFIL = '/usuarios/yo'
TEXTOS_EDITABLES = ['nombre', 'apellido', 'whatsapp', 'posicion']


def test_leer_mi_perfil_devuelve_mis_datos_privados(client_usuario, usuario):
    respuesta = client_usuario.get(MI_PERFIL)

    assert respuesta.status_code == HTTPStatus.OK
    # Se compara el cuerpo completo: si se filtra otro campo (como el hash
    # de la contraseña), el test falla.
    assert respuesta.json() == {
        'id': usuario.id,
        'email': EMAIL,
        'nombre': 'Ana',
        'apellido': 'Pérez',
        'whatsapp': '+5491100000000',
        'fecha_nacimiento': hoy_menos_anios(30).isoformat(),
        'posicion': 'Delantera',
        'puntuacion_promedio': None,
        'partidos_jugados': 0,
        'deuda': 0,
        'habilitado': True,
    }


def test_leer_mi_perfil_sin_token_devuelve_no_autenticado(client):
    respuesta = client.get(MI_PERFIL)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_editar_mi_perfil_cambia_solo_el_campo_enviado(client_usuario):
    respuesta = client_usuario.patch(MI_PERFIL, json={'posicion': 'Arquera'})

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['posicion'] == 'Arquera'
    assert respuesta.json()['nombre'] == 'Ana'
    assert respuesta.json()['whatsapp'] == '+5491100000000'


def test_editar_mi_perfil_cambia_todos_los_datos_editables(client_usuario):
    cambios = {
        'nombre': 'Beto',
        'apellido': 'Gómez',
        'whatsapp': '+5491199999999',
        'fecha_nacimiento': hoy_menos_anios(20).isoformat(),
        'posicion': 'Arquero',
    }

    client_usuario.patch(MI_PERFIL, json=cambios)

    # Se lee con otro pedido para comprobar que quedó guardado.
    perfil = client_usuario.get(MI_PERFIL).json()
    assert {campo: perfil[campo] for campo in cambios} == cambios


def test_editar_mi_perfil_sin_campos_no_cambia_nada(client_usuario):
    antes = client_usuario.get(MI_PERFIL).json()

    respuesta = client_usuario.patch(MI_PERFIL, json={})

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json() == antes


def test_editar_mi_perfil_recorta_los_espacios_del_texto(client_usuario):
    respuesta = client_usuario.patch(MI_PERFIL, json={'nombre': '  Beto  '})

    assert respuesta.json()['nombre'] == 'Beto'


@pytest.mark.parametrize('campo', [*TEXTOS_EDITABLES, 'fecha_nacimiento'])
def test_editar_mi_perfil_con_null_devuelve_error_de_validacion(
    client_usuario, campo
):
    # Son datos obligatorios en la base: guardar un null daría un error 500.
    respuesta = client_usuario.patch(MI_PERFIL, json={campo: None})

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize('campo', TEXTOS_EDITABLES)
def test_editar_mi_perfil_con_texto_vacio_devuelve_error_de_validacion(
    client_usuario, campo
):
    respuesta = client_usuario.patch(MI_PERFIL, json={campo: '   '})

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_editar_fecha_a_menor_de_16_devuelve_error_y_no_guarda_nada(
    client_usuario,
):
    antes = client_usuario.get(MI_PERFIL).json()
    nacimiento = cumple_en_un_dia(EDAD_MINIMA).isoformat()

    respuesta = client_usuario.patch(
        MI_PERFIL, json={'nombre': 'Beto', 'fecha_nacimiento': nacimiento}
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert str(EDAD_MINIMA) in respuesta.json()['detail']
    # Tampoco se guarda el nombre que venía en el mismo pedido.
    assert client_usuario.get(MI_PERFIL).json() == antes


def test_editar_fecha_a_exactamente_16_anios_es_valido(client_usuario):
    nacimiento = hoy_menos_anios(EDAD_MINIMA).isoformat()

    respuesta = client_usuario.patch(
        MI_PERFIL, json={'fecha_nacimiento': nacimiento}
    )

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['fecha_nacimiento'] == nacimiento


def test_editar_fecha_de_nacimiento_futura_es_rechazado(client_usuario):
    respuesta = client_usuario.patch(
        MI_PERFIL, json={'fecha_nacimiento': '2999-01-01'}
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_editar_mi_perfil_ignora_los_campos_no_editables(
    client_usuario, usuario, session
):
    # Un campo de más no tiene efecto: nadie puede hacerse admin, cambiar su
    # email ni ponerse puntuación mandándolo en el cuerpo.
    respuesta = client_usuario.patch(
        MI_PERFIL,
        json={
            'email': 'otra@ejemplo.com',
            'contrasena_hash': 'x',
            'rol_id': 2,
            'bloqueado': True,
            'puntuacion_promedio': 5,
            'partidos_jugados': 99,
        },
    )

    assert respuesta.status_code == HTTPStatus.OK
    session.refresh(usuario)
    assert usuario.email == EMAIL
    assert usuario.contrasena_hash.startswith('$argon2')
    assert not usuario.tiene_rol(ROL_ADMIN)
    assert usuario.bloqueado is False
    assert usuario.puntuacion_promedio is None
    assert usuario.partidos_jugados == 0


def test_editar_mi_perfil_no_cambia_a_otro_usuario(
    client_usuario, otro_usuario, session
):
    client_usuario.patch(MI_PERFIL, json={'nombre': 'Carla'})

    session.refresh(otro_usuario)
    assert otro_usuario.nombre == 'Ana'


def test_editar_mi_perfil_sin_token_devuelve_no_autenticado(client):
    respuesta = client.patch(MI_PERFIL, json={'nombre': 'Beto'})

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_leer_perfil_publico_muestra_solo_los_datos_publicos(
    client_usuario, otro_usuario
):
    respuesta = client_usuario.get(f'/usuarios/{otro_usuario.id}')

    assert respuesta.status_code == HTTPStatus.OK
    # Se compara el cuerpo completo: el apellido, el WhatsApp y el email no
    # pueden aparecer.
    assert respuesta.json() == {
        'id': otro_usuario.id,
        'nombre': 'Ana',
        'posicion': 'Delantera',
        'puntuacion_promedio': None,
        'partidos_jugados': 0,
    }


def test_leer_perfil_publico_muestra_puntuacion_y_partidos_jugados(
    client_usuario, otro_usuario, session
):
    otro_usuario.puntuacion_promedio = 4.5
    otro_usuario.partidos_jugados = 7
    session.commit()

    respuesta = client_usuario.get(f'/usuarios/{otro_usuario.id}')

    cuerpo = respuesta.json()
    assert cuerpo['puntuacion_promedio'] == otro_usuario.puntuacion_promedio
    assert cuerpo['partidos_jugados'] == otro_usuario.partidos_jugados


def test_leer_perfil_publico_inexistente_devuelve_no_encontrado(
    client_usuario,
):
    respuesta = client_usuario.get('/usuarios/9999')

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Usuario no encontrado'


def test_leer_perfil_publico_sin_token_devuelve_no_autenticado(
    client, otro_usuario
):
    respuesta = client.get(f'/usuarios/{otro_usuario.id}')

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED
