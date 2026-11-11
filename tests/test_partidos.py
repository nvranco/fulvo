from datetime import timedelta
from http import HTTPStatus

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from fulvo.models import (
    DURACION_PARTIDO_MINUTOS,
    Complejo,
    EstadoPartido,
    Partido,
    TipoPartido,
    ahora_argentina,
)
from fulvo.security import crear_token_acceso
from tests.factories import PartidoFactory

PARTIDOS = '/partidos'
# Momento fijo para los tests que congelan el reloj: freezegun lo toma en
# UTC, así que en Argentina (UTC-3) son las 12:00 del 20 de noviembre.
AHORA_UTC = '2026-11-20 15:00:00'
CUPOS_MAXIMOS = {'F5': 9, 'F7': 13, 'F8': 15, 'F11': 21}


def en_dias(dias: float) -> str:
    """Fecha y hora de Argentina dentro de `dias` días, como texto ISO."""
    momento = ahora_argentina().replace(microsecond=0)
    return (momento + timedelta(days=dias)).isoformat()


def datos_de_partido(**cambios) -> dict:
    """Cuerpo válido para POST /partidos; `cambios` pisa campos."""
    datos = {
        'complejo_id': 1,
        'inicio': en_dias(7),
        'tipo': 'F5',
        'cupos_faltantes': 2,
    }
    return datos | cambios


def guardar_partido(session, organizador, **cambios) -> Partido:
    """Guarda un partido del organizador, en el complejo 1 salvo cambios."""
    datos = {'organizador_id': organizador.id, 'complejo_id': 1} | cambios
    partido = PartidoFactory(**datos)
    session.add(partido)
    session.commit()
    return partido


def con_token(usuario) -> dict:
    """Encabezado con un token creado en este momento.

    Los tests que congelan el reloj lo crean adentro del `freeze_time`: un
    token de la fixture estaría vencido en la fecha congelada.
    """
    token = crear_token_acceso({'sub': usuario.email})
    return {'Authorization': f'Bearer {token}'}


def ids(respuesta) -> list[int]:
    """Ids de los partidos de un listado, en el orden en que vinieron."""
    return [partido['id'] for partido in respuesta.json()['partidos']]


def test_publicar_partido_devuelve_creado_y_abierto(client_usuario, usuario):
    datos = datos_de_partido(inicio=en_dias(3))

    respuesta = client_usuario.post(PARTIDOS, json=datos)

    assert respuesta.status_code == HTTPStatus.CREATED
    partido = respuesta.json()
    assert partido['estado'] == 'abierto'
    assert partido['inicio'] == datos['inicio']
    assert partido['duracion_minutos'] == DURACION_PARTIDO_MINUTOS
    assert partido['tipo'] == datos['tipo']
    assert partido['cupos_faltantes'] == datos['cupos_faltantes']
    assert partido['organizador']['id'] == usuario.id
    assert partido['complejo']['id'] == datos['complejo_id']


def test_publicar_partido_calcula_el_fin_con_60_minutos(client_usuario):
    respuesta = client_usuario.post(
        PARTIDOS, json=datos_de_partido(inicio='2999-01-01T20:00:00')
    )

    assert respuesta.json()['fin'] == '2999-01-01T21:00:00'


def test_publicar_partido_muestra_solo_el_perfil_publico_del_organizador(
    client_usuario, usuario
):
    respuesta = client_usuario.post(PARTIDOS, json=datos_de_partido())

    assert respuesta.json()['organizador'] == {
        'id': usuario.id,
        'nombre': 'Ana',
        'posicion': 'Delantera',
        'puntuacion_promedio': None,
        'partidos_jugados': 0,
    }


def test_publicar_partido_sin_token_devuelve_no_autenticado(client):
    respuesta = client.post(PARTIDOS, json=datos_de_partido())

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_publicar_partido_en_complejo_inexistente_devuelve_no_encontrado(
    client_usuario,
):
    respuesta = client_usuario.post(
        PARTIDOS, json=datos_de_partido(complejo_id=9999)
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Complejo no encontrado'


def test_publicar_partido_con_inicio_pasado_devuelve_error(client, usuario):
    with freeze_time(AHORA_UTC):
        respuesta = client.post(
            PARTIDOS,
            json=datos_de_partido(inicio='2026-11-20T11:59:00'),
            headers=con_token(usuario),
        )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert respuesta.json()['detail'] == (
        'El partido tiene que empezar en el futuro'
    )


def test_publicar_partido_que_empieza_justo_ahora_devuelve_error(
    client, usuario
):
    with freeze_time(AHORA_UTC):
        respuesta = client.post(
            PARTIDOS,
            json=datos_de_partido(inicio='2026-11-20T12:00:00'),
            headers=con_token(usuario),
        )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_publicar_partido_un_minuto_despues_es_valido(client, usuario):
    with freeze_time(AHORA_UTC):
        respuesta = client.post(
            PARTIDOS,
            json=datos_de_partido(inicio='2026-11-20T12:01:00'),
            headers=con_token(usuario),
        )

    assert respuesta.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    'inicio', ['2026-11-25T23:00:00Z', '2026-11-25T20:00:00-03:00']
)
def test_publicar_partido_con_zona_horaria_lo_guarda_en_hora_argentina(
    client, usuario, inicio
):
    with freeze_time(AHORA_UTC):
        respuesta = client.post(
            PARTIDOS,
            json=datos_de_partido(inicio=inicio),
            headers=con_token(usuario),
        )

    assert respuesta.json()['inicio'] == '2026-11-25T20:00:00'


def test_publicar_partido_con_tipo_invalido_devuelve_error_de_validacion(
    client_usuario,
):
    respuesta = client_usuario.post(PARTIDOS, json=datos_de_partido(tipo='F6'))

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(('tipo', 'maximo'), CUPOS_MAXIMOS.items())
def test_publicar_partido_con_el_maximo_de_cupos_del_tipo_es_valido(
    client_usuario, tipo, maximo
):
    respuesta = client_usuario.post(
        PARTIDOS, json=datos_de_partido(tipo=tipo, cupos_faltantes=maximo)
    )

    assert respuesta.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(('tipo', 'maximo'), CUPOS_MAXIMOS.items())
def test_publicar_partido_con_un_cupo_de_mas_devuelve_error(
    client_usuario, tipo, maximo
):
    respuesta = client_usuario.post(
        PARTIDOS,
        json=datos_de_partido(tipo=tipo, cupos_faltantes=maximo + 1),
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert respuesta.json()['detail'] == (
        f'Un partido {tipo} admite hasta {maximo} cupos faltantes'
    )


def test_publicar_partido_sin_cupos_devuelve_error_de_validacion(
    client_usuario,
):
    respuesta = client_usuario.post(
        PARTIDOS, json=datos_de_partido(cupos_faltantes=0)
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_publicar_partido_ignora_duracion_estado_y_organizador_enviados(
    client_usuario, usuario, otro_usuario
):
    # La duración es fija, todo partido nace abierto y el organizador sale
    # del token: mandarlos en el cuerpo no tiene efecto.
    respuesta = client_usuario.post(
        PARTIDOS,
        json=datos_de_partido(
            duracion_minutos=90,
            estado='completo',
            organizador_id=otro_usuario.id,
        ),
    )

    partido = respuesta.json()
    assert partido['duracion_minutos'] == DURACION_PARTIDO_MINUTOS
    assert partido['estado'] == 'abierto'
    assert partido['organizador']['id'] == usuario.id


def test_listar_partidos_muestra_solo_los_abiertos_que_no_empezaron(
    client_usuario, session, usuario
):
    abierto = guardar_partido(session, usuario)
    guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(minutes=30)
    )
    for estado in ('completo', 'cancelado', 'jugado'):
        guardar_partido(session, usuario, estado=EstadoPartido(estado))

    respuesta = client_usuario.get(PARTIDOS)

    assert respuesta.status_code == HTTPStatus.OK
    assert ids(respuesta) == [abierto.id]


def test_listar_partidos_va_del_mas_proximo_al_mas_lejano(
    client_usuario, session, usuario
):
    lejano = guardar_partido(
        session, usuario, inicio=ahora_argentina() + timedelta(days=9)
    )
    proximo = guardar_partido(
        session, usuario, inicio=ahora_argentina() + timedelta(days=1)
    )

    respuesta = client_usuario.get(PARTIDOS)

    assert ids(respuesta) == [proximo.id, lejano.id]


def test_listar_partidos_filtra_por_tipo(client_usuario, session, usuario):
    guardar_partido(session, usuario, tipo=TipoPartido.F5)
    f11 = guardar_partido(session, usuario, tipo=TipoPartido.F11)

    respuesta = client_usuario.get(PARTIDOS, params={'tipo': 'F11'})

    assert ids(respuesta) == [f11.id]


def test_listar_partidos_filtra_por_complejo(client_usuario, session, usuario):
    guardar_partido(session, usuario, complejo_id=1)
    en_el_2 = guardar_partido(session, usuario, complejo_id=2)

    respuesta = client_usuario.get(PARTIDOS, params={'complejo_id': 2})

    assert ids(respuesta) == [en_el_2.id]


def test_listar_partidos_filtra_por_zona_sin_distinguir_mayusculas(
    client_usuario, session, usuario
):
    primero = session.get(Complejo, 1)
    de_otra_zona = session.scalars(
        select(Complejo).where(Complejo.zona_id != primero.zona_id)
    ).first()
    en_la_zona = guardar_partido(session, usuario, complejo_id=primero.id)
    guardar_partido(session, usuario, complejo_id=de_otra_zona.id)

    respuesta = client_usuario.get(
        PARTIDOS, params={'zona': primero.zona.nombre.upper()}
    )

    assert ids(respuesta) == [en_la_zona.id]


def test_listar_partidos_de_una_zona_inexistente_devuelve_lista_vacia(
    client_usuario, session, usuario
):
    guardar_partido(session, usuario)

    respuesta = client_usuario.get(PARTIDOS, params={'zona': 'Narnia'})

    assert respuesta.json() == {'partidos': []}


def test_listar_partidos_combina_filtros(client_usuario, session, usuario):
    guardar_partido(session, usuario, complejo_id=2, tipo=TipoPartido.F5)
    buscado = guardar_partido(
        session, usuario, complejo_id=2, tipo=TipoPartido.F7
    )
    guardar_partido(session, usuario, complejo_id=1, tipo=TipoPartido.F7)

    respuesta = client_usuario.get(
        PARTIDOS, params={'complejo_id': 2, 'tipo': 'F7'}
    )

    assert ids(respuesta) == [buscado.id]


def test_listar_partidos_pagina_con_offset_y_limit(
    client_usuario, session, usuario
):
    # Cinco partidos de una vez, como `create_batch` del aula 10. Si dos
    # empiezan a la misma hora, el listado los ordena por id, así que el
    # orden es el de creación.
    partidos = PartidoFactory.create_batch(
        5, organizador_id=usuario.id, complejo_id=1
    )
    session.add_all(partidos)
    session.commit()

    respuesta = client_usuario.get(PARTIDOS, params={'offset': 1, 'limit': 2})

    assert ids(respuesta) == [partidos[1].id, partidos[2].id]


@pytest.mark.parametrize(
    'params', [{'limit': 0}, {'limit': 101}, {'offset': -1}, {'tipo': 'F6'}]
)
def test_listar_partidos_con_parametros_invalidos_devuelve_error(
    client_usuario, params
):
    respuesta = client_usuario.get(PARTIDOS, params=params)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_listar_partidos_sin_token_devuelve_no_autenticado(client):
    respuesta = client.get(PARTIDOS)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_leer_partido_devuelve_sus_datos(client_usuario, session, usuario):
    partido = guardar_partido(session, usuario, tipo=TipoPartido.F8)

    respuesta = client_usuario.get(f'{PARTIDOS}/{partido.id}')

    assert respuesta.status_code == HTTPStatus.OK
    cuerpo = respuesta.json()
    assert cuerpo['id'] == partido.id
    assert cuerpo['tipo'] == 'F8'
    assert cuerpo['complejo']['zona'] == partido.complejo.zona.nombre


def test_leer_partido_inexistente_devuelve_no_encontrado(client_usuario):
    respuesta = client_usuario.get(f'{PARTIDOS}/9999')

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Partido no encontrado'


def test_leer_partido_sin_token_devuelve_no_autenticado(
    client, session, usuario
):
    partido = guardar_partido(session, usuario)

    respuesta = client.get(f'{PARTIDOS}/{partido.id}')

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize('estado', ['abierto', 'completo'])
def test_leer_partido_terminado_lo_pasa_a_jugado(
    client_usuario, session, usuario, estado
):
    partido = guardar_partido(
        session,
        usuario,
        inicio=ahora_argentina() - timedelta(hours=2),
        estado=EstadoPartido(estado),
    )

    respuesta = client_usuario.get(f'{PARTIDOS}/{partido.id}')

    assert respuesta.json()['estado'] == 'jugado'
    # La ruta usa esta misma sesión: el rollback descarta lo que no se haya
    # confirmado con commit. Si el estado sigue en jugado, quedó guardado.
    session.rollback()
    assert partido.estado == EstadoPartido.jugado


def test_leer_partido_cancelado_terminado_sigue_cancelado(
    client_usuario, session, usuario
):
    partido = guardar_partido(
        session,
        usuario,
        inicio=ahora_argentina() - timedelta(hours=2),
        estado=EstadoPartido.cancelado,
    )

    respuesta = client_usuario.get(f'{PARTIDOS}/{partido.id}')

    assert respuesta.json()['estado'] == 'cancelado'


def test_leer_partido_en_juego_sigue_abierto(client_usuario, session, usuario):
    partido = guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(minutes=30)
    )

    respuesta = client_usuario.get(f'{PARTIDOS}/{partido.id}')

    assert respuesta.json()['estado'] == 'abierto'
