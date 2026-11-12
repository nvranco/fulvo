from datetime import datetime, timedelta
from http import HTTPStatus

import pytest

from fulvo.models import EstadoPartido, EstadoPostulacion, ahora_argentina
from tests.datos import CONTRASENA, con_token
from tests.factories import (
    guardar_aceptado,
    guardar_partido,
    guardar_partido_jugado,
    guardar_usuario_comun,
)

MOTIVO = 'Insultó a otros jugadores'
NO_A_UN_ADMIN = 'No se puede bloquear a un administrador'

# Las tres rutas de sanciones, que solo puede usar el admin (RQ10):
# (método, lo que va después de /usuarios/{id}/sanciones, cuerpo).
RUTAS_DE_SANCIONES = [
    ('POST', '', {'motivo': MOTIVO}),
    ('GET', '', None),
    ('PATCH', '/1', {'activa': False}),
]


def sanciones_de(usuario) -> str:
    return f'/usuarios/{usuario.id}/sanciones'


def bloquear(client, usuario, admin, motivo=MOTIVO):
    return client.post(
        sanciones_de(usuario),
        json={'motivo': motivo},
        headers=con_token(admin),
    )


def desbloquear(client, usuario, sancion_id, admin, cuerpo=None):
    return client.patch(
        f'{sanciones_de(usuario)}/{sancion_id}',
        json={'activa': False} if cuerpo is None else cuerpo,
        headers=con_token(admin),
    )


def historial(client, usuario, admin, **params) -> list[dict]:
    respuesta = client.get(
        sanciones_de(usuario), params=params, headers=con_token(admin)
    )
    assert respuesta.status_code == HTTPStatus.OK
    return respuesta.json()['sanciones']


def iniciar_sesion(client, usuario):
    return client.post(
        '/auth/token',
        data={'username': usuario.email, 'password': CONTRASENA},
    )


def ver_partido(client, partido, quien_pregunta) -> dict:
    return client.get(
        f'/partidos/{partido.id}', headers=con_token(quien_pregunta)
    ).json()


def avisos(client, usuario) -> list[str]:
    """Tipos de las notificaciones del usuario, de la más nueva a la vieja."""
    respuesta = client.get('/notificaciones', headers=con_token(usuario))
    return [aviso['tipo'] for aviso in respuesta.json()['notificaciones']]


def postularse(client, partido, jugador):
    return client.post(
        f'/partidos/{partido.id}/postulaciones', headers=con_token(jugador)
    )


def test_bloquear_devuelve_la_sancion_activa(client, usuario, admin):
    antes = ahora_argentina()

    respuesta = bloquear(client, usuario, admin)

    assert respuesta.status_code == HTTPStatus.CREATED
    sancion = respuesta.json()
    assert sancion['usuario_id'] == usuario.id
    assert sancion['motivo'] == MOTIVO
    assert sancion['activa'] is True
    assert sancion['hasta'] is None
    assert sancion['aplicada_por']['id'] == admin.id
    assert antes <= datetime.fromisoformat(sancion['desde'])
    assert datetime.fromisoformat(sancion['desde']) <= ahora_argentina()


def test_el_motivo_se_guarda_sin_espacios_en_los_bordes(
    client, usuario, admin
):
    respuesta = bloquear(client, usuario, admin, motivo=f'  {MOTIVO}  ')

    assert respuesta.json()['motivo'] == MOTIVO


def test_el_bloqueado_no_puede_iniciar_sesion(client, usuario, admin):
    bloquear(client, usuario, admin)

    respuesta = iniciar_sesion(client, usuario)

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


def test_el_token_que_ya_tenia_el_bloqueado_deja_de_servir(
    client, usuario, admin
):
    token_previo = con_token(usuario)
    bloquear(client, usuario, admin)

    respuesta = client.get('/usuarios/yo', headers=token_previo)

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == 'Usuario bloqueado'


def test_bloquear_a_un_usuario_inexistente_devuelve_404(client, admin):
    respuesta = client.post(
        '/usuarios/999/sanciones',
        json={'motivo': MOTIVO},
        headers=con_token(admin),
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Usuario no encontrado'


def test_bloquear_a_otro_admin_devuelve_409(client, session, admin):
    otro_admin = guardar_usuario_comun(session, admin.rol_id)

    respuesta = bloquear(client, otro_admin, admin)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == NO_A_UN_ADMIN
    assert iniciar_sesion(client, otro_admin).status_code == HTTPStatus.OK


def test_el_admin_no_puede_bloquearse_a_si_mismo(client, admin):
    respuesta = bloquear(client, admin, admin)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == NO_A_UN_ADMIN
    assert historial(client, admin, admin) == []


def test_bloquear_dos_veces_devuelve_409(client, usuario, admin):
    bloquear(client, usuario, admin)

    respuesta = bloquear(client, usuario, admin, motivo='Otro motivo')

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'El usuario ya está bloqueado'
    assert len(historial(client, usuario, admin)) == 1


@pytest.mark.parametrize(
    'cuerpo', [{}, {'motivo': ''}, {'motivo': '   '}, {'motivo': None}]
)
def test_bloquear_sin_motivo_devuelve_422(client, usuario, admin, cuerpo):
    respuesta = client.post(
        sanciones_de(usuario), json=cuerpo, headers=con_token(admin)
    )

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert iniciar_sesion(client, usuario).status_code == HTTPStatus.OK


@pytest.mark.parametrize(('metodo', 'sufijo', 'cuerpo'), RUTAS_DE_SANCIONES)
def test_las_rutas_de_sanciones_piden_token(
    client, usuario, metodo, sufijo, cuerpo
):
    respuesta = client.request(
        metodo, sanciones_de(usuario) + sufijo, json=cuerpo
    )

    assert respuesta.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(('metodo', 'sufijo', 'cuerpo'), RUTAS_DE_SANCIONES)
def test_un_usuario_comun_no_puede_usar_las_rutas_de_sanciones(
    client_usuario, otro_usuario, metodo, sufijo, cuerpo
):
    respuesta = client_usuario.request(
        metodo, sanciones_de(otro_usuario) + sufijo, json=cuerpo
    )

    assert respuesta.status_code == HTTPStatus.FORBIDDEN
    assert respuesta.json()['detail'] == (
        'Esta acción es solo para administradores'
    )
    assert iniciar_sesion(client_usuario, otro_usuario).status_code == (
        HTTPStatus.OK
    )


def test_bloquear_cancela_sus_partidos_que_no_empezaron(
    client, session, usuario, otro_usuario, admin
):
    abierto = guardar_partido(session, usuario)
    completo = guardar_partido(
        session, usuario, cupos_faltantes=0, estado=EstadoPartido.completo
    )

    bloquear(client, usuario, admin)

    assert ver_partido(client, abierto, otro_usuario)['estado'] == 'cancelado'
    assert ver_partido(client, completo, otro_usuario)['estado'] == (
        'cancelado'
    )


def test_bloquear_avisa_a_los_aceptados_que_se_cancelo_el_partido(
    client, session, usuario, otro_usuario, admin
):
    partido = guardar_partido(session, usuario)
    guardar_aceptado(session, partido, otro_usuario)

    bloquear(client, usuario, admin)

    assert avisos(client, otro_usuario) == ['partido_cancelado']


def test_bloquear_lo_saca_de_un_partido_ajeno_y_libera_el_cupo(
    client, session, usuario, otro_usuario, admin
):
    partido = guardar_partido(
        session, otro_usuario, cupos_faltantes=0, estado=EstadoPartido.completo
    )
    postulacion = guardar_aceptado(session, partido, usuario)

    bloquear(client, usuario, admin)

    visto = ver_partido(client, partido, otro_usuario)
    assert visto['estado'] == 'abierto'
    assert visto['cupos_faltantes'] == 1
    assert postulacion.estado == EstadoPostulacion.retirada
    assert avisos(client, otro_usuario) == ['postulacion_retirada']


def test_bloquear_retira_tambien_sus_postulaciones_en_espera(
    client, session, usuario, otro_usuario, admin
):
    partido = guardar_partido(session, otro_usuario)
    postulacion_id = postularse(client, partido, usuario).json()['id']

    bloquear(client, usuario, admin)

    postulaciones = client.get(
        f'/partidos/{partido.id}/postulaciones',
        headers=con_token(otro_usuario),
    ).json()['postulaciones']
    assert [(p['id'], p['estado']) for p in postulaciones] == [
        (postulacion_id, 'retirada')
    ]
    assert avisos(client, otro_usuario) == [
        'postulacion_retirada',
        'postulacion_recibida',
    ]


def test_bloquear_no_toca_los_partidos_que_ya_empezaron(
    client, session, usuario, otro_usuario, admin
):
    hace_media_hora = ahora_argentina() - timedelta(minutes=30)
    propio = guardar_partido(session, usuario, inicio=hace_media_hora)
    ajeno = guardar_partido(session, otro_usuario, inicio=hace_media_hora)
    postulacion = guardar_aceptado(session, ajeno, usuario)

    bloquear(client, usuario, admin)

    assert ver_partido(client, propio, otro_usuario)['estado'] == 'abierto'
    assert postulacion.estado == EstadoPostulacion.aceptada
    assert avisos(client, otro_usuario) == []


def test_bloquear_no_toca_los_partidos_jugados_ni_los_cancelados(
    client, session, usuario, otro_usuario, admin
):
    jugado = guardar_partido_jugado(session, usuario, [otro_usuario])
    cancelado = guardar_partido(
        session, usuario, estado=EstadoPartido.cancelado
    )

    respuesta = bloquear(client, usuario, admin)

    assert respuesta.status_code == HTTPStatus.CREATED
    assert ver_partido(client, jugado, otro_usuario)['estado'] == 'jugado'
    assert ver_partido(client, cancelado, otro_usuario)['estado'] == (
        'cancelado'
    )
    # Los demás todavía pueden votar al bloqueado en el partido jugado.
    pendientes = client.get(
        '/votaciones',
        params={'estado': 'pendiente'},
        headers=con_token(otro_usuario),
    ).json()['votaciones']
    receptores = {
        v['receptor_usuario']['id']
        for v in pendientes
        if v['receptor_usuario'] is not None
    }
    assert usuario.id in receptores


def test_el_historial_va_de_la_sancion_mas_nueva_a_la_mas_vieja(
    client, usuario, admin
):
    primera = bloquear(client, usuario, admin).json()
    desbloquear(client, usuario, primera['id'], admin)
    segunda = bloquear(client, usuario, admin, motivo='Volvió').json()

    sanciones = historial(client, usuario, admin)

    assert [s['id'] for s in sanciones] == [segunda['id'], primera['id']]
    assert [s['activa'] for s in sanciones] == [True, False]
    assert [s['motivo'] for s in sanciones] == ['Volvió', MOTIVO]


def test_el_historial_de_un_usuario_sin_sanciones_esta_vacio(
    client, usuario, admin
):
    assert historial(client, usuario, admin) == []


def test_el_historial_muestra_solo_las_sanciones_de_ese_usuario(
    client, usuario, otro_usuario, admin
):
    bloquear(client, otro_usuario, admin)

    assert historial(client, usuario, admin) == []


def test_el_historial_se_pagina_con_offset_y_limit(client, usuario, admin):
    ids = []
    for motivo in ('Primero', 'Segundo', 'Tercero'):
        sancion = bloquear(client, usuario, admin, motivo=motivo).json()
        desbloquear(client, usuario, sancion['id'], admin)
        ids.append(sancion['id'])

    pagina = historial(client, usuario, admin, offset=1, limit=1)

    assert [s['id'] for s in pagina] == [ids[1]]


def test_el_historial_de_un_usuario_inexistente_devuelve_404(client, admin):
    respuesta = client.get('/usuarios/999/sanciones', headers=con_token(admin))

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Usuario no encontrado'


def test_desbloquear_cierra_la_sancion(client, usuario, admin):
    sancion = bloquear(client, usuario, admin).json()
    antes = ahora_argentina()

    respuesta = desbloquear(client, usuario, sancion['id'], admin)

    assert respuesta.status_code == HTTPStatus.OK
    cerrada = respuesta.json()
    assert cerrada['id'] == sancion['id']
    assert cerrada['activa'] is False
    assert cerrada['desde'] == sancion['desde']
    assert antes <= datetime.fromisoformat(cerrada['hasta'])
    assert datetime.fromisoformat(cerrada['hasta']) <= ahora_argentina()


def test_el_desbloqueado_vuelve_a_iniciar_sesion(client, usuario, admin):
    sancion = bloquear(client, usuario, admin).json()

    desbloquear(client, usuario, sancion['id'], admin)

    assert iniciar_sesion(client, usuario).status_code == HTTPStatus.OK


def test_desbloquear_no_devuelve_los_partidos_cancelados(
    client, session, usuario, otro_usuario, admin
):
    partido = guardar_partido(session, usuario)
    sancion = bloquear(client, usuario, admin).json()

    desbloquear(client, usuario, sancion['id'], admin)

    assert ver_partido(client, partido, otro_usuario)['estado'] == 'cancelado'


def test_desbloquear_una_sancion_cerrada_devuelve_409(client, usuario, admin):
    sancion = bloquear(client, usuario, admin).json()
    desbloquear(client, usuario, sancion['id'], admin)

    respuesta = desbloquear(client, usuario, sancion['id'], admin)

    assert respuesta.status_code == HTTPStatus.CONFLICT
    assert respuesta.json()['detail'] == 'La sanción ya estaba cerrada'


def test_desbloquear_con_la_sancion_de_otro_usuario_devuelve_404(
    client, usuario, otro_usuario, admin
):
    sancion = bloquear(client, otro_usuario, admin).json()

    respuesta = desbloquear(client, usuario, sancion['id'], admin)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Sanción no encontrada'
    assert iniciar_sesion(client, otro_usuario).status_code == (
        HTTPStatus.UNAUTHORIZED
    )


def test_desbloquear_una_sancion_inexistente_devuelve_404(
    client, usuario, admin
):
    respuesta = desbloquear(client, usuario, 999, admin)

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Sanción no encontrada'


def test_desbloquear_a_un_usuario_inexistente_devuelve_404(client, admin):
    respuesta = client.patch(
        '/usuarios/999/sanciones/1',
        json={'activa': False},
        headers=con_token(admin),
    )

    assert respuesta.status_code == HTTPStatus.NOT_FOUND
    assert respuesta.json()['detail'] == 'Usuario no encontrado'


@pytest.mark.parametrize('cuerpo', [{}, {'activa': True}, {'activa': None}])
def test_desbloquear_sin_pedir_activa_false_devuelve_422(
    client, usuario, admin, cuerpo
):
    sancion = bloquear(client, usuario, admin).json()

    respuesta = desbloquear(client, usuario, sancion['id'], admin, cuerpo)

    assert respuesta.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert iniciar_sesion(client, usuario).status_code == (
        HTTPStatus.UNAUTHORIZED
    )
