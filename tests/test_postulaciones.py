from datetime import timedelta
from http import HTTPStatus

import pytest

from fulvo.models import EstadoPartido, EstadoPostulacion, ahora_argentina
from tests.datos import con_token
from tests.factories import (
    guardar_partido,
    guardar_postulacion,
    guardar_usuario_comun,
)

MIS_POSTULACIONES = '/postulaciones'
EMPEZADO = 'El partido ya empezó'


@pytest.fixture
def partido(session, usuario):
    """Partido abierto de `usuario` (el organizador), con 2 cupos."""
    return guardar_partido(session, usuario, cupos_faltantes=2)


def de_partido(partido) -> str:
    return f'/partidos/{partido.id}/postulaciones'


def postular(client, partido, jugador):
    return client.post(de_partido(partido), headers=con_token(jugador))


def responder(client, partido, postulacion_id, estado, organizador):
    return client.patch(
        f'{de_partido(partido)}/{postulacion_id}',
        json={'estado': estado},
        headers=con_token(organizador),
    )


def retirar(client, postulacion_id, jugador, estado='retirada'):
    return client.patch(
        f'{MIS_POSTULACIONES}/{postulacion_id}',
        json={'estado': estado},
        headers=con_token(jugador),
    )


def cancelar(client, partido, usuario, estado='cancelado'):
    return client.patch(
        f'/partidos/{partido.id}',
        json={'estado': estado},
        headers=con_token(usuario),
    )


def leer_partido(client, partido, usuario) -> dict:
    return client.get(
        f'/partidos/{partido.id}', headers=con_token(usuario)
    ).json()


def nuevo_jugador(session, usuario, **cambios):
    return guardar_usuario_comun(session, usuario.rol_id, **cambios)


def test_postularse_devuelve_creado_en_espera_y_sin_whatsapp(
    client, partido, otro_usuario
):
    respuesta = postular(client, partido, otro_usuario)

    assert respuesta.status_code == HTTPStatus.CREATED
    cuerpo = respuesta.json()
    assert cuerpo['estado'] == 'en_espera'
    assert cuerpo['respondida_at'] is None
    assert cuerpo['partido']['id'] == partido.id
    assert cuerpo['whatsapp_organizador'] is None


def test_postularse_sin_token_devuelve_no_autenticado(client, partido):
    respuesta = client.post(de_partido(partido))

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_postularse_a_un_partido_inexistente_devuelve_no_encontrado(
    client, otro_usuario
):
    respuesta = client.post(
        '/partidos/9999/postulaciones', headers=con_token(otro_usuario)
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND


def test_el_organizador_no_puede_postularse_y_recibe_conflicto(
    client, partido, usuario
):
    respuesta = postular(client, partido, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'El organizador no puede postularse a su propio partido'
    )


def test_postularse_dos_veces_devuelve_conflicto(
    client, partido, otro_usuario
):
    postular(client, partido, otro_usuario)

    respuesta = postular(client, partido, otro_usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'El jugador ya se postuló a este partido'
    )


@pytest.mark.parametrize(
    'caso',
    [
        ({'estado': EstadoPartido.cancelado}, 'El partido no está abierto'),
        (
            {'inicio': ahora_argentina() - timedelta(minutes=30)},
            'El partido ya empezó',
        ),
        (
            {'inicio': ahora_argentina() - timedelta(hours=3)},
            'El partido no está abierto',
        ),
    ],
    ids=['cancelado', 'empezado', 'terminado'],
)
def test_postularse_a_un_partido_que_no_lo_permite_devuelve_conflicto(
    client, session, usuario, otro_usuario, caso
):
    cambios, detalle = caso
    partido = guardar_partido(session, usuario, **cambios)

    respuesta = postular(client, partido, otro_usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == detalle


def test_la_lista_de_espera_va_por_puntuacion_y_despues_por_llegada(
    client, session, usuario, partido
):
    # Llegan en este orden: sin puntuación, 3 estrellas, 4.5 y otro 4.5.
    sin_puntos = nuevo_jugador(session, usuario)
    tres = nuevo_jugador(session, usuario, puntuacion_promedio=3.0)
    primero = nuevo_jugador(session, usuario, puntuacion_promedio=4.5)
    segundo = nuevo_jugador(session, usuario, puntuacion_promedio=4.5)
    for jugador in (sin_puntos, tres, primero, segundo):
        postular(client, partido, jugador)

    respuesta = client.get(de_partido(partido), headers=con_token(usuario))

    assert respuesta.status_code == HTTPStatus.OK
    orden = [p['jugador']['id'] for p in respuesta.json()['postulaciones']]
    assert orden == [primero.id, segundo.id, tres.id, sin_puntos.id]


def test_el_organizador_ve_el_whatsapp_solo_de_los_aceptados(
    client, session, usuario, partido, otro_usuario
):
    en_espera = nuevo_jugador(session, usuario)
    aceptada = postular(client, partido, otro_usuario).json()
    postular(client, partido, en_espera)
    responder(client, partido, aceptada['id'], 'aceptada', usuario)

    respuesta = client.get(de_partido(partido), headers=con_token(usuario))

    whatsapps = {
        p['jugador']['id']: p['whatsapp_jugador']
        for p in respuesta.json()['postulaciones']
    }
    assert whatsapps == {
        otro_usuario.id: otro_usuario.whatsapp,
        en_espera.id: None,
    }


def test_listar_postulaciones_filtra_por_estado(
    client, session, usuario, partido, otro_usuario
):
    rechazada = postular(client, partido, otro_usuario).json()
    en_espera = postular(client, partido, nuevo_jugador(session, usuario))
    responder(client, partido, rechazada['id'], 'rechazada', usuario)

    respuesta = client.get(
        de_partido(partido),
        params={'estado': 'en_espera'},
        headers=con_token(usuario),
    )

    ids = [p['id'] for p in respuesta.json()['postulaciones']]
    assert ids == [en_espera.json()['id']]


def test_solo_el_organizador_ve_las_postulaciones(
    client, partido, otro_usuario
):
    respuesta = client.get(
        de_partido(partido), headers=con_token(otro_usuario)
    )

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Solo el organizador del partido puede hacer esto'
    )


def test_listar_postulaciones_de_un_partido_inexistente_es_no_encontrado(
    client, usuario
):
    respuesta = client.get(
        '/partidos/9999/postulaciones', headers=con_token(usuario)
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND


def test_aceptar_resta_un_cupo_y_muestra_el_whatsapp_del_jugador(
    client, partido, usuario, otro_usuario
):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = responder(
        client, partido, postulacion['id'], 'aceptada', usuario
    )

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['estado'] == 'aceptada'
    assert respuesta.json()['respondida_at'] is not None
    assert respuesta.json()['whatsapp_jugador'] == otro_usuario.whatsapp
    assert leer_partido(client, partido, usuario)['cupos_faltantes'] == 1


def test_aceptar_el_ultimo_cupo_completa_el_partido_y_rechaza_al_resto(
    client, session, usuario, otro_usuario
):
    partido = guardar_partido(session, usuario, cupos_faltantes=1)
    aceptada = postular(client, partido, otro_usuario).json()
    otra = postular(client, partido, nuevo_jugador(session, usuario)).json()

    responder(client, partido, aceptada['id'], 'aceptada', usuario)

    assert leer_partido(client, partido, usuario)['estado'] == 'completo'
    estados = {
        p['id']: p['estado']
        for p in client.get(
            de_partido(partido), headers=con_token(usuario)
        ).json()['postulaciones']
    }
    assert estados == {aceptada['id']: 'aceptada', otra['id']: 'rechazada'}


def test_rechazar_una_postulacion_en_espera(
    client, partido, usuario, otro_usuario
):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = responder(
        client, partido, postulacion['id'], 'rechazada', usuario
    )

    assert respuesta.json()['estado'] == 'rechazada'
    assert respuesta.json()['whatsapp_jugador'] is None


def test_revocar_a_un_aceptado_libera_el_cupo_y_reabre_el_partido(
    client, session, usuario, otro_usuario
):
    partido = guardar_partido(session, usuario, cupos_faltantes=1)
    postulacion = postular(client, partido, otro_usuario).json()
    responder(client, partido, postulacion['id'], 'aceptada', usuario)

    respuesta = responder(
        client, partido, postulacion['id'], 'revocada', usuario
    )

    assert respuesta.json()['estado'] == 'revocada'
    assert respuesta.json()['whatsapp_jugador'] is None
    actualizado = leer_partido(client, partido, usuario)
    assert actualizado['estado'] == 'abierto'
    assert actualizado['cupos_faltantes'] == 1


def test_un_cambio_imposible_devuelve_conflicto_con_el_motivo(
    client, partido, usuario, otro_usuario
):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = responder(
        client, partido, postulacion['id'], 'revocada', usuario
    )

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'Solo se puede revocar una postulación aceptada'
    )


@pytest.mark.parametrize('estado', ['retirada', 'en_espera', 'cualquiera'])
def test_el_organizador_solo_puede_aceptar_rechazar_o_revocar(
    client, partido, usuario, otro_usuario, estado
):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = responder(client, partido, postulacion['id'], estado, usuario)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_solo_el_organizador_puede_responder(client, partido, otro_usuario):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = responder(
        client, partido, postulacion['id'], 'aceptada', otro_usuario
    )

    assert respuesta.status_code == HTTPStatus.FORBIDDEN


def test_responder_una_postulacion_de_otro_partido_es_no_encontrado(
    client, session, usuario, partido, otro_usuario
):
    otro_partido = guardar_partido(session, usuario)
    postulacion = postular(client, otro_partido, otro_usuario).json()

    respuesta = responder(
        client, partido, postulacion['id'], 'aceptada', usuario
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Postulación no encontrada'


def test_mis_postulaciones_traen_el_whatsapp_del_organizador_si_acepto(
    client, session, usuario, partido, otro_usuario
):
    otro_partido = guardar_partido(session, usuario)
    aceptada = postular(client, partido, otro_usuario).json()
    en_espera = postular(client, otro_partido, otro_usuario).json()
    responder(client, partido, aceptada['id'], 'aceptada', usuario)

    respuesta = client.get(MIS_POSTULACIONES, headers=con_token(otro_usuario))

    assert respuesta.status_code == HTTPStatus.OK
    mias = respuesta.json()['postulaciones']
    # De la más nueva a la más vieja.
    assert [p['id'] for p in mias] == [en_espera['id'], aceptada['id']]
    assert mias[0]['whatsapp_organizador'] is None
    assert mias[1]['whatsapp_organizador'] == usuario.whatsapp


def test_mis_postulaciones_no_muestran_las_de_otros(
    client, session, usuario, partido, otro_usuario
):
    postular(client, partido, nuevo_jugador(session, usuario))

    respuesta = client.get(MIS_POSTULACIONES, headers=con_token(otro_usuario))

    assert respuesta.json() == {'postulaciones': []}


def test_mis_postulaciones_se_paginan(client, session, usuario, otro_usuario):
    for _ in range(3):
        postular(client, guardar_partido(session, usuario), otro_usuario)

    respuesta = client.get(
        MIS_POSTULACIONES,
        params={'offset': 1, 'limit': 1},
        headers=con_token(otro_usuario),
    )

    assert len(respuesta.json()['postulaciones']) == 1


def test_mis_postulaciones_sin_token_devuelve_no_autenticado(client):
    respuesta = client.get(MIS_POSTULACIONES)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_retirar_una_postulacion_en_espera(client, partido, otro_usuario):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = retirar(client, postulacion['id'], otro_usuario)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['estado'] == 'retirada'


def test_la_baja_de_un_aceptado_libera_el_cupo_y_reabre_el_partido(
    client, session, usuario, otro_usuario
):
    partido = guardar_partido(session, usuario, cupos_faltantes=1)
    postulacion = postular(client, partido, otro_usuario).json()
    responder(client, partido, postulacion['id'], 'aceptada', usuario)

    retirar(client, postulacion['id'], otro_usuario)

    actualizado = leer_partido(client, partido, usuario)
    assert actualizado['estado'] == 'abierto'
    assert actualizado['cupos_faltantes'] == 1


def test_solo_el_jugador_puede_retirar_su_postulacion(
    client, partido, usuario, otro_usuario
):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = retirar(client, postulacion['id'], usuario)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Solo el jugador de la postulación puede retirarla'
    )


def test_retirar_una_postulacion_inexistente_es_no_encontrado(
    client, otro_usuario
):
    respuesta = retirar(client, 9999, otro_usuario)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND


def test_el_jugador_solo_puede_pedir_retirada(client, partido, otro_usuario):
    postulacion = postular(client, partido, otro_usuario).json()

    respuesta = retirar(client, postulacion['id'], otro_usuario, 'aceptada')

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_retirar_dos_veces_devuelve_conflicto(client, partido, otro_usuario):
    postulacion = postular(client, partido, otro_usuario).json()
    retirar(client, postulacion['id'], otro_usuario)

    respuesta = retirar(client, postulacion['id'], otro_usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT


def test_cancelar_el_partido_lo_saca_del_listado(client, partido, usuario):
    respuesta = cancelar(client, partido, usuario)

    assert respuesta.status_code == HTTPStatus.OK
    assert respuesta.json()['estado'] == 'cancelado'
    listado = client.get('/partidos', headers=con_token(usuario)).json()
    assert listado == {'partidos': []}


def test_al_cancelar_el_whatsapp_deja_de_verse_para_los_dos(
    client, partido, usuario, otro_usuario
):
    postulacion = postular(client, partido, otro_usuario).json()
    responder(client, partido, postulacion['id'], 'aceptada', usuario)

    cancelar(client, partido, usuario)

    del_organizador = client.get(
        de_partido(partido), headers=con_token(usuario)
    ).json()['postulaciones'][0]
    del_jugador = client.get(
        MIS_POSTULACIONES, headers=con_token(otro_usuario)
    ).json()['postulaciones'][0]
    assert del_organizador['estado'] == 'aceptada'
    assert del_organizador['whatsapp_jugador'] is None
    assert del_jugador['whatsapp_organizador'] is None


def test_solo_el_organizador_puede_cancelar(client, partido, otro_usuario):
    respuesta = cancelar(client, partido, otro_usuario)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN


def test_cancelar_dos_veces_devuelve_conflicto(client, partido, usuario):
    cancelar(client, partido, usuario)

    respuesta = cancelar(client, partido, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == (
        'El partido ya se jugó o fue cancelado'
    )


def test_cancelar_un_partido_terminado_devuelve_conflicto(
    client, session, usuario
):
    partido = guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(hours=3)
    )

    respuesta = cancelar(client, partido, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize('estado', ['abierto', 'jugado', 'completo'])
def test_un_partido_solo_se_puede_cambiar_a_cancelado(
    client, partido, usuario, estado
):
    respuesta = cancelar(client, partido, usuario, estado)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_cancelar_un_partido_inexistente_es_no_encontrado(client, usuario):
    respuesta = client.patch(
        '/partidos/9999',
        json={'estado': 'cancelado'},
        headers=con_token(usuario),
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND


@pytest.fixture
def empezado(session, usuario):
    """Partido de `usuario` que empezó hace media hora y todavía no terminó."""
    return guardar_partido(
        session, usuario, inicio=ahora_argentina() - timedelta(minutes=30)
    )


def estados_en_el_partido(client, partido, organizador) -> list[str]:
    """Estados de las postulaciones del partido, como los ve el organizador."""
    postulaciones = client.get(
        de_partido(partido), headers=con_token(organizador)
    ).json()['postulaciones']
    return [postulacion['estado'] for postulacion in postulaciones]


@pytest.mark.parametrize(
    'caso',
    [
        (EstadoPostulacion.en_espera, 'aceptada'),
        (EstadoPostulacion.en_espera, 'rechazada'),
        (EstadoPostulacion.aceptada, 'revocada'),
    ],
    ids=['aceptar', 'rechazar', 'revocar'],
)
def test_con_el_partido_empezado_el_organizador_no_responde_postulaciones(
    client, session, empezado, otro_usuario, caso
):
    estado, pedido = caso
    organizador = empezado.organizador
    postulacion = guardar_postulacion(session, empezado, otro_usuario, estado)

    respuesta = responder(
        client, empezado, postulacion.id, pedido, organizador
    )

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == EMPEZADO
    estados = estados_en_el_partido(client, empezado, organizador)
    assert estados == [estado.value]


@pytest.mark.parametrize(
    'estado',
    [EstadoPostulacion.en_espera, EstadoPostulacion.aceptada],
    ids=['retirarse', 'bajarse'],
)
def test_con_el_partido_empezado_el_jugador_no_se_retira_ni_se_baja(
    client, session, empezado, otro_usuario, estado
):
    postulacion = guardar_postulacion(session, empezado, otro_usuario, estado)

    respuesta = retirar(client, postulacion.id, otro_usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == EMPEZADO
    estados = estados_en_el_partido(client, empezado, empezado.organizador)
    assert estados == [estado.value]


def test_con_el_partido_empezado_el_organizador_no_lo_cancela(
    client, empezado, usuario
):
    respuesta = cancelar(client, empezado, usuario)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == EMPEZADO
    assert leer_partido(client, empezado, usuario)['estado'] == 'abierto'
